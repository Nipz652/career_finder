"""
AI tagging module.
Uses Gemini to extract tech stacks from job descriptions in batches.
Writes results directly to the SQLite database.
"""

import asyncio
import json
import os
import re
import time

from google import genai
from dotenv import load_dotenv

from db.connection import DB_PATH
from db.queries import get_untagged_jobs, update_tech_stack

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BATCH_SIZE = 5
MAX_RETRIES = 3
RETRY_DELAY = 5.0
BATCH_SLEEP = 4.0    # seconds between batches to respect RPM limits

TAG_PROMPT = """Extract the technical stack from these job descriptions.
Output format — one line per job, nothing else:
JobID: tech1, tech2, tech3

Rules:
- Include: programming languages, frameworks, tools, databases, cloud services, DevOps tools
- Exclude: soft skills, certifications, spoken languages
- If no technical skills found, write: JobID: Not specified

{jobs}"""

INVALID_TAGS = {"not specified", "n/a", "none", "not mentioned"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _count_tokens_fallback(text: str) -> int:
    return len(text.split()) * 4


def _get_client() -> genai.Client:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set in environment.")
    return genai.Client(api_key=api_key)


def _parse_tag_response(response_text: str, batch: list[dict]) -> dict[str, str]:
    """
    Parse model response into {job_id: tech_stack}.
    Only includes IDs that were in the batch.
    """
    expected_ids = {str(job["id"]) for job in batch}
    results: dict[str, str] = {}

    for line in response_text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        left, right = line.split(":", 1)
        job_id = left.strip().replace("Job", "").strip()
        if job_id in expected_ids:
            tech_stack = right.strip()
            if tech_stack.lower() not in INVALID_TAGS:
                results[job_id] = tech_stack

    return results


# ---------------------------------------------------------------------------
# Main tagger
# ---------------------------------------------------------------------------
async def tag_jobs(
    jobs: list[dict] | None = None,
    db_path: str | None = None,
    batch_size: int = BATCH_SIZE,
) -> tuple[int, int]:
    """
    Tag job descriptions with their tech stacks using Gemini.

    Args:
        jobs: List of job dicts to tag. If None, fetches untagged from DB.
        db_path: Path to SQLite DB. Uses DB_URL env var by default.
        batch_size: Number of jobs per API call.

    Returns:
        (total_tagged, total_tokens) — count of tagged jobs and tokens used.
    """
    client = _get_client()
    db_path = db_path or DB_PATH

    if jobs is None:
        jobs = get_untagged_jobs(db_path)

    if not jobs:
        print("[tag] No untagged jobs found.")
        return 0, 0

    print(f"[tag] Tagging {len(jobs)} jobs in batches of {batch_size}...")

    total_tagged = 0
    total_tokens = 0
    start_time = time.time()

    for batch_idx in range(0, len(jobs), batch_size):
        batch = jobs[batch_idx:batch_idx + batch_size]
        batch_num = batch_idx // batch_size

        # Build prompt
        job_lines = "\n\n".join(
            f"Job {job['id']}: {job['description'][:800]}"
            for job in batch
        )
        prompt = TAG_PROMPT.format(jobs=job_lines)

        success = False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await client.aio.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                )
                response_text = response.text.strip()

                # Token counting
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    total_tokens += (
                        (response.usage_metadata.prompt_token_count or 0) +
                        (response.usage_metadata.candidates_token_count or 0)
                    )
                else:
                    total_tokens += (
                        _count_tokens_fallback(prompt) +
                        _count_tokens_fallback(response_text)
                    )

                results = _parse_tag_response(response_text, batch)

                # Validate batch size match
                if len(results) == 0:
                    raise ValueError(
                        f"No results parsed from batch {batch_num}"
                    )

                # Write to DB
                for job_id, tech_stack in results.items():
                    update_tech_stack(job_id, tech_stack, db_path)
                    print(f"[tag] Tagged Job {job_id}: {tech_stack}")
                    total_tagged += 1

                success = True
                break

            except Exception as e:
                error_str = str(e)
                print(f"[tag] Batch {batch_num} attempt {attempt} failed: {e}")

                # Daily quota — stop entirely
                if "429" in error_str and "PerDay" in error_str:
                    print("[tag] Daily quota exceeded. Stopping.")
                    elapsed = (time.time() - start_time) * 1000
                    print(f"[tag] Total tagged: {total_tagged}, "
                          f"tokens: {total_tokens}, "
                          f"time: {elapsed:.0f}ms")
                    return total_tagged, total_tokens

                # Invalid model — stop entirely
                if "400" in error_str and "INVALID_ARGUMENT" in error_str:
                    print("[tag] Invalid request. Stopping.")
                    return total_tagged, total_tokens

                if attempt < MAX_RETRIES:
                    match = re.search(
                        r"retry in (\d+(?:\.\d+)?)s", error_str, re.IGNORECASE
                    )
                    wait = float(match.group(1)) + 2 if match else RETRY_DELAY
                    print(f"[tag] Retrying in {wait:.0f}s...")
                    await asyncio.sleep(wait)

        if not success:
            print(f"[tag] Batch {batch_num} gave up after {MAX_RETRIES} attempts.")

        # Pace between batches
        await asyncio.sleep(BATCH_SLEEP)

    elapsed = (time.time() - start_time) * 1000
    print(f"[tag] Done. Tagged: {total_tagged}, "
          f"tokens: {total_tokens}, "
          f"time: {elapsed:.0f}ms")

    return total_tagged, total_tokens