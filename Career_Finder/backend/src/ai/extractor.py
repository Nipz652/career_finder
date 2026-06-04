"""Extract technical skills from resume text using Gemini."""

import asyncio
import json
import os
import re

from google import genai
from dotenv import load_dotenv

from ai.models import ResumeSkills

load_dotenv()

MAX_RETRIES = 5
RETRY_DELAY = 5.0

EXTRACT_PROMPT = """You are a resume parser. Extract ONLY technical skills from the resume below.

Rules:
- Include: languages, frameworks, tools, platforms, databases, cloud, DevOps
- Exclude: certifications, soft skills, spoken languages
- Preserve compound names exactly: C/C++ stays as C/C++
- Return a JSON array of strings ONLY. No explanation, no markdown.

Resume:
{resume}"""

JAILBREAK_PATTERNS = [
    r"ignore (all |previous |above |prior )?instructions?",
    r"forget (everything|all|your instructions?)",
    r"you are now", r"act as (a |an )?", r"pretend (you are|to be)",
    r"do anything now", r"disregard (your |all )?",
    r"new (role|persona|instructions?|task)", r"override",
    r"system prompt", r"jailbreak",
    r"<\s*(script|iframe|object|embed)", r"\\x[0-9a-f]{2}",
]


class DailyQuotaExceededError(Exception):
    pass


class InvalidRequestError(Exception):
    pass


def is_jailbreak(text: str) -> bool:
    lower = text.lower()
    return any(re.search(p, lower) for p in JAILBREAK_PATTERNS)


def _parse_json_list(text: str) -> list[str]:
    text = re.sub(r"^```[a-z]*\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text).strip()
    return json.loads(text)


def _tokens_fallback(text: str) -> int:
    return len(text.split()) * 4


async def extract_skills(resume_text: str) -> tuple[ResumeSkills, int]:
    if is_jailbreak(resume_text):
        raise ValueError("Potentially malicious content detected.")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set.")

    client = genai.Client(api_key=api_key)
    prompt = EXTRACT_PROMPT.format(resume=resume_text)
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

            return ResumeSkills(skills=_parse_json_list(text)), total_tokens

        except Exception as e:
            err = str(e)
            if "429" in err and "PerDay" in err:
                raise DailyQuotaExceededError(
                    "Daily API quota exceeded. Try again tomorrow."
                )
            if "400" in err and "INVALID_ARGUMENT" in err:
                raise InvalidRequestError(f"Invalid API request: {err}")

            print(f"[extractor] Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                match = re.search(r"retry in (\d+(?:\.\d+)?)s", err, re.IGNORECASE)
                wait = float(match.group(1)) + 2 if match else RETRY_DELAY
                await asyncio.sleep(wait)
            else:
                return ResumeSkills(skills=[]), total_tokens

    return ResumeSkills(skills=[]), total_tokens
