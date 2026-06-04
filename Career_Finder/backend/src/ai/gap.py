"""Deterministic skill gap computation. No AI calls."""

import time
from ai.models import ResumeSkills, SkillGapResult, SkillStats
from db.queries import get_tech_stacks_by_role

INVALID_SKILLS = {"not specified", "n/a", "none", "not mentioned", "not available"}


def _build_demand_map(tech_stacks: list[str]) -> dict[str, int]:
    demand: dict[str, int] = {}
    for stack in tech_stacks:
        for skill in stack.split(","):
            skill = skill.strip().lower()
            if skill and skill not in INVALID_SKILLS:
                demand[skill] = demand.get(skill, 0) + 1
    return demand


def _build_statistics(
    gaps: list[str], demand_map: dict[str, int], total_jobs: int
) -> tuple[list[SkillStats], str, str]:
    if not gaps:
        return [], "", ""

    counts = [demand_map.get(skill, 0) for skill in gaps]
    max_count = max(counts) if counts else 1
    high_t = max_count * 0.66
    mid_t  = max_count * 0.33

    stats = []
    for skill, count in zip(gaps, counts):
        pct = round((count / total_jobs) * 100, 1) if total_jobs > 0 else 0.0
        level = "High" if count >= high_t else ("Medium" if count >= mid_t else "Low")
        stats.append(SkillStats(skill=skill, job_count=count, demand_pct=pct, demand_level=level))

    stats.sort(key=lambda x: -x.job_count)
    most_wanted = stats[0].skill if stats else ""
    demand_range = (
        f"{stats[0].skill} ({stats[0].job_count} jobs) vs "
        f"{stats[-1].skill} ({stats[-1].job_count} jobs)"
    ) if stats else ""

    return stats, most_wanted, demand_range


def compute_gaps(
    candidate_skills: ResumeSkills,
    target_role: str,
    db_path: str,
) -> SkillGapResult:
    start = time.time()

    try:
        tech_stacks = get_tech_stacks_by_role(target_role, db_path)
    except Exception as e:
        print(f"[gap] DB fetch failed: {e}")
        return SkillGapResult(gaps=[], skill_demand={})

    if not tech_stacks:
        return SkillGapResult(gaps=[], skill_demand={})

    demand_map = _build_demand_map(tech_stacks)
    all_job_skills = set(demand_map.keys())
    candidate_set = set(candidate_skills.skills)
    gaps = sorted(all_job_skills - candidate_set)

    statistics, most_wanted, demand_range = _build_statistics(gaps, demand_map, len(tech_stacks))
    gap_demand = {s.skill: s.job_count for s in statistics}

    return SkillGapResult(
        gaps=gaps,
        skill_demand=gap_demand,
        most_wanted=most_wanted,
        demand_range=demand_range,
        statistics=statistics,
        time_ms=round((time.time() - start) * 1000, 3),
    )
