"""
Skill gap computation.
Pure deterministic logic — NO AI calls.
Same inputs always produce the same output.
"""

import sqlite3
import time

from ai.models import ResumeSkills, SkillGapResult, SkillStats

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INVALID_SKILLS = {
    "not specified", "n/a", "none",
    "not mentioned", "not available", "various",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_demand_map(tech_stacks: list[str]) -> dict[str, int]:
    """Build skill → job count mapping from list of tech stack strings."""
    demand: dict[str, int] = {}
    for stack in tech_stacks:
        for skill in stack.split(","):
            skill = skill.strip().lower()
            if skill and skill not in INVALID_SKILLS:
                demand[skill] = demand.get(skill, 0) + 1
    return demand


def _build_statistics(
    gaps: list[str],
    demand_map: dict[str, int],
    total_jobs: int,
) -> tuple[list[SkillStats], str, str]:
    """
    Build demand statistics for gap skills.

    Returns:
        (statistics, most_wanted, demand_range)
    """
    if not gaps:
        return [], "", ""

    counts = [demand_map.get(skill, 0) for skill in gaps]
    max_count = max(counts) if counts else 1
    high_threshold = max_count * 0.66
    mid_threshold = max_count * 0.33

    stats = []
    for skill, count in zip(gaps, counts):
        pct = round((count / total_jobs) * 100, 1) if total_jobs > 0 else 0.0
        if count >= high_threshold:
            level = "High"
        elif count >= mid_threshold:
            level = "Medium"
        else:
            level = "Low"
        stats.append(SkillStats(
            skill=skill,
            job_count=count,
            demand_pct=pct,
            demand_level=level,
        ))

    stats.sort(key=lambda x: -x.job_count)

    most_wanted = stats[0].skill if stats else ""
    top = stats[0]
    bottom = stats[-1]
    demand_range = (
        f"{top.skill} ({top.job_count} jobs) "
        f"vs {bottom.skill} ({bottom.job_count} jobs)"
    )

    return stats, most_wanted, demand_range


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------
def compute_gaps(
    candidate_skills: ResumeSkills,
    target_role: str,
    db_path: str,
) -> SkillGapResult:
    """
    Compute skill gaps between candidate and job market for a target role.

    Args:
        candidate_skills: Skills extracted from the candidate's resume.
        target_role: The job role to compare against (e.g. "Data Engineer").
        db_path: Path to the SQLite jobs database.

    Returns:
        SkillGapResult with gaps, demand statistics, and metadata.
    """
    start = time.time()

    # Fetch tech stacks from DB for the target role
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT tech_stack FROM jobs
                WHERE tech_stack IS NOT NULL
                  AND tech_stack != ''
                  AND LOWER(role) = LOWER(?)
                """,
                (target_role,),
            )
            rows = cursor.fetchall()
    except Exception as e:
        print(f"[gap] DB fetch failed: {e}")
        return SkillGapResult(gaps=[], skill_demand={})

    if not rows:
        print(f"[gap] No tagged jobs found for role: {target_role}")
        return SkillGapResult(gaps=[], skill_demand={})

    tech_stacks = [row[0] for row in rows]
    total_jobs = len(tech_stacks)

    demand_map = _build_demand_map(tech_stacks)
    all_job_skills = set(demand_map.keys())

    # Deterministic set subtraction
    candidate_set = set(candidate_skills.skills)
    gaps = sorted(all_job_skills - candidate_set)

    statistics, most_wanted, demand_range = _build_statistics(
        gaps, demand_map, total_jobs
    )
    gap_demand = {s.skill: s.job_count for s in statistics}

    elapsed = (time.time() - start) * 1000

    return SkillGapResult(
        gaps=gaps,
        skill_demand=gap_demand,
        most_wanted=most_wanted,
        demand_range=demand_range,
        statistics=statistics,
        time_ms=round(elapsed, 3),
    )