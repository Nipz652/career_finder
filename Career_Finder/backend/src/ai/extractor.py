"""
Resume skill extractor.
Uses Gemini to extract technical skills from resume text.
Returns a validated ResumeSkills Pydantic model.
"""

import asyncio
import json
import os
import re

from google import genai
from dotenv import load_dotenv

from ai.models import ResumeSkills

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_RETRIES = 5
RETRY_DELAY = 5.0

EXTRACT_SKILLS_PROMPT = """You are a resume parser. Extract ONLY the technical skills from the resume below.

Rules:
- Include: programming languages, frameworks, tools, platforms, databases, cloud services, DevOps tools
- Exclude: certifications (e.g. CCNA, AWS Certified), soft skills (leadership, management), spoken languages
- CRITICAL: Preserve compound skills EXACTLY as written.
  If the resume says "C/C++", output "C/C++" as ONE item, not "C" and "C++" separately.
- Do not alter, expand, or split any skill name.
- Return a JSON array of strings only. No explanation, no markdown fences.

Examples:
- "C, C++" in resume → ["C", "C++"]   (two separate items)
- "C/C++" in resume  → ["C/C++"]       (one compound item)

Resume:
{resume}"""

# ---------------------------------------------------------------------------
# Jailbreak detection
# ---------------------------------------------------------------------------
JAILBREAK_PATTERNS = [
    r"ignore (all |previous |above |prior )?instructions?",
    r"forget (everything|all|your instructions?)",
    r"you are now",
    r"act as (a |an )?",
    r"pretend (you are|to be)",
    r"do anything now",
    r"disregard (your |all )?",
    r"new (role|persona|instructions?|task)",
    r"override",
    r"system prompt",
    r"jailbreak",
    r"<\s*(script|iframe|object|embed)",
    r"\\x[0-9a-f]{2}",
]


def is_jailbreak(text: str) -> bool:
    lower = text.lower()
    return any(re.search(p, lower) for p in JAILBREAK_PATTERNS)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------
class DailyQuotaExceededError(Exception):
    pass


class InvalidRequestError(Exception):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _count_tokens_fallback(text: str) -> int:
    return len(text.split()) * 4


def _parse_json_list(text: str) -> list[str]:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return json.loads(text.strip())


def _get_client() -> genai.Client:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set in environment.")
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Core extractor
# ---------------------------------------------------------------------------
async def extract_skills(resume_text: str) -> tuple[ResumeSkills, int]:
    """
    Extract technical skills from resume text using Gemini.

    Args:
        resume_text: Raw text content of the resume.

    Returns:
        (ResumeSkills, tokens_used)

    Raises:
        DailyQuotaExceededError: When daily API quota is hit.
        InvalidRequestError: When request is malformed.
        ValueError: When resume contains jailbreak content.
    """
    if is_jailbreak(resume_text):
        raise ValueError(
            "Potentially malicious content detected in resume. Aborting."
        )

    client = _get_client()
    prompt = EXTRACT_SKILLS_PROMPT.format(resume=resume_text)
    total_tokens = 0

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            response_text = response.text.strip()

            # Token counting
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

            skills_list = _parse_json_list(response_text)
            return ResumeSkills(skills=skills_list), total_tokens

        except Exception as e:
            error_str = str(e)

            # Daily quota — stop immediately, no retry
            if "429" in error_str and (
                "PerDay" in error_str or
                "GenerateRequestsPerDay" in error_str
            ):
                raise DailyQuotaExceededError(
                    "Daily API quota exceeded. "
                    "Please try again tomorrow or check "
                    "https://ai.dev/rate-limit"
                )

            # Invalid argument — stop immediately, no retry
            if "400" in error_str and "INVALID_ARGUMENT" in error_str:
                raise InvalidRequestError(
                    f"Invalid API request: {error_str}"
                )

            print(f"[extractor] Attempt {attempt} failed: {e}")

            if attempt < MAX_RETRIES:
                match = re.search(
                    r"retry in (\d+(?:\.\d+)?)s", error_str, re.IGNORECASE
                )
                wait = float(match.group(1)) + 2 if match else RETRY_DELAY
                print(f"[extractor] Retrying in {wait:.0f}s...")
                await asyncio.sleep(wait)
            else:
                print("[extractor] All retries exhausted. Returning empty skills.")
                return ResumeSkills(skills=[]), total_tokens

    return ResumeSkills(skills=[]), total_tokens