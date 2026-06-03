"""
/api/stats and /api/jobs router.
Database visualisation and search endpoints for the dashboard.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from db.queries import (
    get_skill_distribution,
    get_job_count_by_role,
    get_tagged_vs_untagged,
    search_jobs,
    get_available_roles,
)

router = APIRouter(prefix="/api")


@router.get("/roles")
def roles():
    """
    Returns list of available target roles in the database.
    Used to populate the role dropdown in the frontend.
    """
    try:
        available = get_available_roles()
        return {"roles": available}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/stats/tech-distribution")
def tech_distribution():
    """
    Returns top 10 most required skills across all jobs.
    Used for pie chart and horizontal bar chart.
    """
    try:
        demand = get_skill_distribution()
        top = sorted(demand.items(), key=lambda x: -x[1])[:10]
        return {
            "labels": [k for k, v in top],
            "values": [v for k, v in top],
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/stats/jobs-per-role")
def jobs_per_role():
    """
    Returns job count per role.
    Used for bar chart showing role distribution.
    """
    try:
        counts = get_job_count_by_role()
        return {
            "labels": list(counts.keys()),
            "values": list(counts.values()),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/stats/tagged-vs-untagged")
def tagged_vs_untagged():
    """
    Returns count of tagged vs untagged jobs.
    Used for pipeline status bar chart.
    """
    try:
        counts = get_tagged_vs_untagged()
        return {
            "labels": list(counts.keys()),
            "values": list(counts.values()),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/jobs/search")
def search(q: str = "", limit: int = 20):
    """
    Search jobs by keyword in title, description, or tech_stack.

    Query params:
        q: Search keyword (empty returns all up to limit)
        limit: Max results (default 20, max 50)

    Returns list of matching job records.
    """
    limit = min(limit, 50)   # cap at 50
    try:
        results = search_jobs(q, limit)
        return {"results": results, "count": len(results)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})