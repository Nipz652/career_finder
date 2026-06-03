"""
Career roadmap generator.
Uses Gemini to produce a prioritised learning plan from skill gaps.
Validates output with Pydantic. Falls back gracefully on failure.
"""

import asyncio
import json
import os
import re
import time

from google import genai
from dotenv import load_dotenv

from ai.models import CareerRoadmap, RoadmapStep, SkillGapResult
from ai.extractor import DailyQuotaExceededError, InvalidRequestError

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_RETRIES = 3
RETRY_DELAY = 5.0

ROADMAP_PROMPT = """You are a senior career advisor with deep knowledge of the tech job market.

A candidate is targeting the role of: {role}

Their current skills: {current_skills}

Skill gaps identified (with job market demand count):
{gaps_with_demand}

Generate a prioritised learning roadmap. Return ONLY a valid JSON object
matching this exact structure — no explanation, no markdown fences:

{{
  "target_role": "{role}",
  "current_skills": {current_skills_json},
  "gaps": {gaps_json},
  "steps": [
    {{
      "skill": "skill name",
      "priority": 1,
      "reason": "why this skill matters for {role} specifically",
      "estimated_weeks": 4,
      "resources": [
        "https://real-url-1.com",
        "https://real-url-2.com"
      ]
    }}
  ],
  "summary": "2-3 sentence plain English overview of the roadmap"
}}

Rules:
- priority 1 = learn first (highest demand + fastest return on investment)
- estimated_weeks must be realistic (not optimistic)
- resources must be real, working URLs (official docs, YouTube, Coursera, etc.)
- reason must be specific to {role}, not generic
- include at most 8 steps — focus on the highest impact gaps
- sort steps by priority ascending (1 first)"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _count_tokens_fallback(text: str) -> int:
    return len(text.split()) * 4


def _parse_json_object(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text.strip())


def _get_client() -> genai.Client:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set in environment.")
    return genai.Client(api_key=api_key)


def _fallback_roadmap(
    gap_result: SkillGapResult,
    target_role: str,
    current_skills: list[str],
) -> CareerRoadmap:
    """
    Returns a basic roadmap using only gap data when Gemini fails.
    Sorted by demand count — no AI reasoning.
    """
    steps = []
    for i, stat in enumerate(gap_result.statistics[:8], start=1):
        steps.append(RoadmapStep(
            skill=stat.skill,
            priority=i,
            reason=f"Required in {stat.job_count} {target_role} job posting(s).",
            estimated_weeks=4,
            resources=[
                f"https://www.google.com/search?q=learn+{stat.skill.replace(' ', '+')}"
            ],
        ))

    return CareerRoadmap(
        target_role=target_role,
        current_skills=current_skills,
        gaps=gap_result.gaps,
        steps=steps,
        summary=(
            f"You have {len(gap_result.gaps)} skill gap(s) for the {target_role} role. "
            f"Focus on {gap_result.most_wanted} first as it appears in the most job postings. "
            f"This roadmap was generated from market data only — AI reasoning unavailable."
        ),
        tokens=0,
        time_ms=0.0,
    )


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------
async def generate_roadmap(
    gap_result: SkillGapResult,
    target_role: str,
    current_skills: list[str],
) -> CareerRoadmap:
    """
    Generate a prioritised learning roadmap using Gemini.

    Args:
        gap_result: Skill gap analysis result from gap.py.
        target_role: The target job role.
        current_skills: List of candidate's current skills.

    Returns:
        CareerRoadmap with steps, reasons, estimates, and resources.
        Falls back to demand-sorted list if Gemini fails.

    Raises:
        DailyQuotaExceededError: When daily API quota is hit.
    """
    if not gap_result.gaps:
        return CareerRoadmap(
            target_role=target_role,
            current_skills=current_skills,
            gaps=[],
            steps=[],
            summary=(
                f"No skill gaps found for the {target_role} role. "
                "Your profile matches the job market requirements well!"
            ),
        )

    start = time.time()
    client = _get_client()

    # Build gaps with demand context for the prompt
    gaps_with_demand = "\n".join(
        f"- {stat.skill}: {stat.job_count} job(s) ({stat.demand_level} demand)"
        for stat in gap_result.statistics[:10]
    )
    # Include any gaps not in statistics
    stats_skills = {s.skill for s in gap_result.statistics}
    for gap in gap_result.gaps:
        if gap not in stats_skills:
            gaps_with_demand += f"\n- {gap}: 0 job(s) (Low demand)"

    prompt = ROADMAP_PROMPT.format(
        role=target_role,
        current_skills=", ".join(current_skills) if current_skills else "None listed",
        gaps_with_demand=gaps_with_demand,
        current_skills_json=json.dumps(current_skills),
        gaps_json=json.dumps(gap_result.gaps),
    )

    total_tokens = 0

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            response_text = response.text.strip()

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                total_tokens = (
                    (response.usage_metadata.prompt_token_count or 0) +
                    (response.usage_metadata.candidates_token_count or 0)
                )
            else:
                total_tokens = (
                    _count_tokens_fallback(prompt) +
                    _count_tokens_fallback(response_text)
                )

            data = _parse_json_object(response_text)

            # Validate steps
            steps = []
            for step_data in data.get("steps", []):
                steps.append(RoadmapStep(
                    skill=step_data["skill"],
                    priority=int(step_data["priority"]),
                    reason=step_data["reason"],
                    estimated_weeks=int(step_data["estimated_weeks"]),
                    resources=step_data.get("resources", []),
                ))

            steps.sort(key=lambda s: s.priority)

            elapsed = (time.time() - start) * 1000

            return CareerRoadmap(
                target_role=data.get("target_role", target_role),
                current_skills=data.get("current_skills", current_skills),
                gaps=data.get("gaps", gap_result.gaps),
                steps=steps,
                summary=data.get("summary", ""),
                tokens=total_tokens,
                time_ms=round(elapsed, 3),
            )

        except Exception as e:
            error_str = str(e)

            # Daily quota — stop immediately
            if "429" in error_str and (
                "PerDay" in error_str or
                "GenerateRequestsPerDay" in error_str
            ):
                raise DailyQuotaExceededError(
                    "Daily API quota exceeded. "
                    "Please try again tomorrow or check "
                    "https://ai.dev/rate-limit"
                )

            # Invalid argument — stop immediately
            if "400" in error_str and "INVALID_ARGUMENT" in error_str:
                raise InvalidRequestError(f"Invalid API request: {error_str}")

            print(f"[roadmap] Attempt {attempt} failed: {e}")

            if attempt < MAX_RETRIES:
                match = re.search(
                    r"retry in (\d+(?:\.\d+)?)s", error_str, re.IGNORECASE
                )
                wait = float(match.group(1)) + 2 if match else RETRY_DELAY
                print(f"[roadmap] Retrying in {wait:.0f}s...")
                await asyncio.sleep(wait)
            else:
                print("[roadmap] All retries exhausted. Using fallback roadmap.")
                return _fallback_roadmap(gap_result, target_role, current_skills)

    return _fallback_roadmap(gap_result, target_role, current_skills)