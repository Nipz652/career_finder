"""
Data transformation module.
Cleans and normalises raw job records before AI tagging.
Saves processed data to data/processed/jobs_tagged.json.
"""

import json
import re
from pathlib import Path

PROCESSED_OUTPUT_PATH = Path("../../data/processed/jobs_tagged.json")
MIN_DESCRIPTION_LENGTH = 100   # skip jobs with very short descriptions


# ---------------------------------------------------------------------------
# Cleaners
# ---------------------------------------------------------------------------
def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def _normalise_role(role: str) -> str:
    """Standardise role names to title case."""
    return role.strip().title()


def _is_valid_job(job: dict) -> bool:
    """Return True if the job record has enough data to be useful."""
    if not job.get("id"):
        return False
    if not job.get("description"):
        return False
    if len(job.get("description", "")) < MIN_DESCRIPTION_LENGTH:
        return False
    if not job.get("role"):
        return False
    return True


# ---------------------------------------------------------------------------
# Main transform function
# ---------------------------------------------------------------------------
def transform_jobs(
    raw_jobs: list[dict],
    output_path: Path | None = None,
) -> list[dict]:
    """
    Clean and normalise raw job records.

    Steps:
    1. Strip HTML from descriptions
    2. Normalise role names
    3. Remove duplicates by job ID
    4. Filter out jobs with missing/short descriptions

    Args:
        raw_jobs: Raw job records from ingest.py
        output_path: Where to save processed JSON

    Returns:
        List of cleaned job dicts ready for AI tagging
    """
    output_path = output_path or PROCESSED_OUTPUT_PATH

    seen_ids: set[str] = set()
    cleaned: list[dict] = []

    for job in raw_jobs:
        job_id = str(job.get("id", "")).strip()

        # Skip duplicates
        if job_id in seen_ids:
            continue
        seen_ids.add(job_id)

        # Clean fields
        cleaned_job = {
            "id": job_id,
            "role": _normalise_role(job.get("role", "")),
            "title": job.get("title", "").strip(),
            "company": job.get("company", "").strip(),
            "location": job.get("location", "").strip(),
            "description": _strip_html(job.get("description", "")),
            "tech_stack": job.get("tech_stack"),     # None at this stage
            "source": job.get("source", "unknown"),
            "created_at": job.get("created_at", ""),
        }

        # Validate
        if not _is_valid_job(cleaned_job):
            continue

        cleaned.append(cleaned_job)

    print(f"[transform] {len(raw_jobs)} raw → {len(cleaned)} clean jobs "
          f"({len(raw_jobs) - len(cleaned)} removed)")

    # Save processed output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    print(f"[transform] Saved {len(cleaned)} processed jobs to {output_path}")

    return cleaned