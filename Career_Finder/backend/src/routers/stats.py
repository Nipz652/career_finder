"""Stats and search endpoints for the dashboard."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from db.queries import (
    get_skill_distribution, get_job_count_by_role,
    get_tagged_vs_untagged, search_jobs, get_available_roles,
)

router = APIRouter(prefix="/api")


@router.get("/roles")
def roles():
    try:
        return {"roles": get_available_roles()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/stats/tech-distribution")
def tech_distribution():
    try:
        demand = get_skill_distribution()
        top = sorted(demand.items(), key=lambda x: -x[1])[:10]
        return {"labels": [k for k, v in top], "values": [v for k, v in top]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/stats/jobs-per-role")
def jobs_per_role():
    try:
        counts = get_job_count_by_role()
        return {"labels": list(counts.keys()), "values": list(counts.values())}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/stats/tagged-vs-untagged")
def tagged_vs_untagged():
    try:
        counts = get_tagged_vs_untagged()
        return {"labels": list(counts.keys()), "values": list(counts.values())}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/jobs/search")
def search(q: str = "", limit: int = 20):
    try:
        results = search_jobs(q, min(limit, 50))
        return {"results": results, "count": len(results)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
