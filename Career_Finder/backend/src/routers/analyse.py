"""POST /analyse — full pipeline: extract → gap → roadmap."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ai.extractor import extract_skills, DailyQuotaExceededError, InvalidRequestError
from ai.gap import compute_gaps
from ai.roadmap import generate_roadmap
from ai.models import AnalyseRequest, CareerRoadmap
from db.connection import DB_PATH
from db.queries import get_available_roles

router = APIRouter()


@router.post("/analyse", response_model=CareerRoadmap)
async def analyse(request: AnalyseRequest):
    # Validate role exists
    available = get_available_roles()
    if request.target_role.lower() not in [r.lower() for r in available]:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Role '{request.target_role}' not found.",
                "available_roles": available,
            },
        )

    # Step 1: Extract skills
    try:
        candidate_skills, extract_tokens = await extract_skills(request.resume_text)
    except DailyQuotaExceededError as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except (InvalidRequestError, ValueError) as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Extraction failed: {e}"})

    if not candidate_skills.skills:
        return JSONResponse(
            status_code=422,
            content={"error": "No technical skills found in your resume."},
        )

    print(f"[analyse] Skills: {candidate_skills.skills}")

    # Step 2: Compute gaps
    try:
        gap_result = compute_gaps(candidate_skills, request.target_role, DB_PATH)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Gap computation failed: {e}"})

    print(f"[analyse] Gaps: {len(gap_result.gaps)}")

    if not gap_result.gaps:
        return CareerRoadmap(
            target_role=request.target_role,
            current_skills=candidate_skills.skills,
            gaps=[], steps=[],
            summary=f"No skill gaps found for {request.target_role}. Your profile matches well!",
            tokens=extract_tokens,
        )

    # Step 3: Generate roadmap
    try:
        roadmap = await generate_roadmap(gap_result, request.target_role, candidate_skills.skills)
        roadmap.tokens += extract_tokens
    except DailyQuotaExceededError as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Roadmap generation failed: {e}"})

    return roadmap
