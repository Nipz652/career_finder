"""Generate prioritised learning roadmap using Gemini."""

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

MAX_RETRIES = 3
RETRY_DELAY = 5.0

ROADMAP_PROMPT = """You are a senior career advisor. A candidate targets the role: {role}

Their current skills: {current_skills}

Skill gaps ranked by job market demand:
{gaps_with_demand}

Return ONLY a valid JSON object — no explanation, no markdown:
{{
  "target_role": "{role}",
  "current_skills": {current_skills_json},
  "gaps": {gaps_json},
  "steps": [
    {{
      "skill": "skill name",
      "priority": 1,
      "reason": "why this matters for {role}",
      "estimated_weeks": 4,
      "demand_level": "High",
      "resources": ["https://real-url.com"]
    }}
  ],
  "summary": "2-3 sentence overview"
}}

Rules:
- priority 1 = learn first (highest demand)
- max 8 steps
- resources must be real URLs
- sort steps by priority ascending"""


def _tokens_fallback(text: str) -> int:
    return len(text.split()) * 4


def _fallback_roadmap(
    gap_result: SkillGapResult, target_role: str, current_skills: list[str]
) -> CareerRoadmap:
    steps = [
        RoadmapStep(
            skill=s.skill, priority=i + 1,
            reason=f"Required in {s.job_count} {target_role} posting(s).",
            estimated_weeks=4,
            demand_level=s.demand_level,
            resources=[f"https://www.google.com/search?q=learn+{s.skill.replace(' ','+')}"],
        )
        for i, s in enumerate(gap_result.statistics[:8])
    ]
    return CareerRoadmap(
        target_role=target_role, current_skills=current_skills,
        gaps=gap_result.gaps, steps=steps,
        summary=(
            f"You have {len(gap_result.gaps)} skill gap(s) for {target_role}. "
            f"Focus on {gap_result.most_wanted} first. "
            f"(Roadmap generated from market data — AI unavailable.)"
        ),
    )


async def generate_roadmap(
    gap_result: SkillGapResult, target_role: str, current_skills: list[str]
) -> CareerRoadmap:
    if not gap_result.gaps:
        return CareerRoadmap(
            target_role=target_role, current_skills=current_skills,
            gaps=[], steps=[],
            summary=f"No skill gaps found for {target_role}. Your profile matches well!",
        )

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set.")

    client = genai.Client(api_key=api_key)
    start = time.time()

    gaps_with_demand = "\n".join(
        f"- {s.skill}: {s.job_count} job(s) ({s.demand_level} demand)"
        for s in gap_result.statistics[:10]
    )

    prompt = ROADMAP_PROMPT.format(
        role=target_role,
        current_skills=", ".join(current_skills) or "None listed",
        gaps_with_demand=gaps_with_demand,
        current_skills_json=json.dumps(current_skills),
        gaps_json=json.dumps(gap_result.gaps),
    )

    total_tokens = 0

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash", contents=prompt
            )
            text = response.text.strip()

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                total_tokens = (
                    (response.usage_metadata.prompt_token_count or 0) +
                    (response.usage_metadata.candidates_token_count or 0)
                )
            else:
                total_tokens = _tokens_fallback(prompt) + _tokens_fallback(text)

            text = re.sub(r"^```[a-z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text).strip()
            data = json.loads(text)

            steps = sorted([
                RoadmapStep(
                    skill=s["skill"], priority=int(s["priority"]),
                    reason=s["reason"], estimated_weeks=int(s["estimated_weeks"]),
                    demand_level=s.get("demand_level", "Low"),
                    resources=s.get("resources", []),
                )
                for s in data.get("steps", [])
            ], key=lambda x: x.priority)

            return CareerRoadmap(
                target_role=data.get("target_role", target_role),
                current_skills=data.get("current_skills", current_skills),
                gaps=data.get("gaps", gap_result.gaps),
                steps=steps,
                summary=data.get("summary", ""),
                tokens=total_tokens,
                time_ms=round((time.time() - start) * 1000, 3),
            )

        except Exception as e:
            err = str(e)
            if "429" in err and "PerDay" in err:
                raise DailyQuotaExceededError("Daily API quota exceeded.")
            if "400" in err and "INVALID_ARGUMENT" in err:
                raise InvalidRequestError(f"Invalid API request: {err}")

            print(f"[roadmap] Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                match = re.search(r"retry in (\d+(?:\.\d+)?)s", err, re.IGNORECASE)
                wait = float(match.group(1)) + 2 if match else RETRY_DELAY
                await asyncio.sleep(wait)
            else:
                return _fallback_roadmap(gap_result, target_role, current_skills)

    return _fallback_roadmap(gap_result, target_role, current_skills)
