"""
/analyse router.
Full pipeline: extract skills → compute gaps → generate roadmap.
"""

import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai.extractor import extract_skills, DailyQuotaExceededError, InvalidRequestError
from ai.gap import compute_gaps
from ai.roadmap import generate_roadmap
from ai.models import AnalyseRequest, CareerRoadmap
from db.connection import DB_PATH
from db.queries import get_available_roles

router = APIRouter()


@router.post("/analyse", response_model=CareerRoadmap)
async def analyse(request: AnalyseRequest):
    """
    Full career analysis pipeline.

    Steps:
    1. Extract skills from resume text using Gemini
    2. Compute skill gaps against job database (deterministic)
    3. Generate prioritised learning roadmap using Gemini

    Request body:
        resume_text: Extracted text from resume PDF
        target_role: Target job role (must match a role in the database)

    Returns:
        CareerRoadmap JSON with steps, reasons, estimates, and resources.
    """
    # Validate role exists in DB
    available_roles = get_available_roles()
    role_names_lower = [r.lower() for r in available_roles]

    if request.target_role.lower() not in role_names_lower:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Role '{request.target_role}' not found in database.",
                "available_roles": available_roles,
            },
        )

    # Step 1: Extract skills from resume
    try:
        candidate_skills, extract_tokens = await extract_skills(request.resume_text)
    except DailyQuotaExceededError as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except InvalidRequestError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Skill extraction failed: {str(e)}"},
        )

    if not candidate_skills.skills:
        return JSONResponse(
            status_code=422,
            content={
                "error": (
                    "No technical skills could be extracted from your resume. "
                    "Please ensure your resume contains technical skills and try again."
                )
            },
        )

    print(f"[analyse] Extracted skills: {candidate_skills.skills}")

    # Step 2: Compute skill gaps (deterministic — no AI)
    try:
        gap_result = compute_gaps(candidate_skills, request.target_role, DB_PATH)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Gap computation failed: {str(e)}"},
        )

    print(f"[analyse] Gaps found: {len(gap_result.gaps)}")

    if not gap_result.gaps:
        return CareerRoadmap(
            target_role=request.target_role,
            current_skills=candidate_skills.skills,
            gaps=[],
            steps=[],
            summary=(
                f"Great news! No skill gaps found for the {request.target_role} role. "
                "Your profile already matches the job market requirements."
            ),
            tokens=extract_tokens,
        )

    # Step 3: Generate roadmap
    try:
        roadmap = await generate_roadmap(
            gap_result=gap_result,
            target_role=request.target_role,
            current_skills=candidate_skills.skills,
        )
        roadmap.tokens += extract_tokens
    except DailyQuotaExceededError as e:
        return JSONResponse(status_code=429, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Roadmap generation failed: {str(e)}"},
        )

    return roadmap