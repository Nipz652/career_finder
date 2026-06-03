"""
Data ingestion module.
Fetches raw job data from an external source or local static dataset.
Saves raw data to data/raw/jobs_raw.json.

Data source: JSearch API via RapidAPI (free tier)
Fallback: static JSON dataset bundled with the project.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RAW_OUTPUT_PATH = Path("../../data/raw/jobs_raw.json")

TARGET_ROLES = [
    "Data Engineer",
    "Backend Developer",
    "Machine Learning Engineer",
    "DevOps Engineer",
    "Frontend Developer",
]

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
}


# ---------------------------------------------------------------------------
# JSearch API fetcher
# ---------------------------------------------------------------------------
async def _fetch_from_jsearch(role: str, num_pages: int = 2) -> list[dict]:
    """
    Fetch job postings for a role from the JSearch API.
    Returns raw API records.
    """
    results = []

    async with httpx.AsyncClient(timeout=30) as client:
        for page in range(1, num_pages + 1):
            try:
                response = await client.get(
                    JSEARCH_URL,
                    headers=JSEARCH_HEADERS,
                    params={
                        "query": f"{role} jobs",
                        "page": str(page),
                        "num_pages": "1",
                        "country": "my",   # Malaysia — adjust as needed
                    },
                )
                response.raise_for_status()
                data = response.json()
                results.extend(data.get("data", []))
                print(f"[ingest] Fetched page {page} for '{role}': "
                      f"{len(data.get('data', []))} jobs")

            except Exception as e:
                print(f"[ingest] Failed to fetch page {page} for '{role}': {e}")

    return results


# ---------------------------------------------------------------------------
# Normalise raw API record to our schema
# ---------------------------------------------------------------------------
def _normalise_jsearch_record(record: dict, role: str) -> dict:
    """Convert a JSearch API record to our internal job schema."""
    return {
        "id": record.get("job_id") or str(uuid.uuid4()),
        "role": role,
        "title": record.get("job_title", ""),
        "company": record.get("employer_name", ""),
        "location": record.get("job_city", "") or record.get("job_country", ""),
        "description": record.get("job_description", ""),
        "tech_stack": None,
        "source": "jsearch",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Fallback: static dataset
# ---------------------------------------------------------------------------
def _load_static_dataset() -> list[dict]:
    """
    Load a bundled static job dataset when API is unavailable.
    Place your static data at data/raw/jobs_static.json.
    """
    static_path = Path("../../data/raw/jobs_static.json")
    if static_path.exists():
        with open(static_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[ingest] Loaded {len(data)} jobs from static dataset.")
        return data

    print("[ingest] No static dataset found. Returning empty list.")
    return []


# ---------------------------------------------------------------------------
# Main ingest function
# ---------------------------------------------------------------------------
async def ingest_jobs(
    roles: list[str] | None = None,
    output_path: Path | None = None,
) -> list[dict]:
    """
    Fetch raw job data for all target roles.

    Args:
        roles: List of role names to fetch. Defaults to TARGET_ROLES.
        output_path: Where to save the raw JSON. Defaults to RAW_OUTPUT_PATH.

    Returns:
        List of normalised raw job dicts.
    """
    roles = roles or TARGET_ROLES
    output_path = output_path or RAW_OUTPUT_PATH

    all_jobs: list[dict] = []

    if not RAPIDAPI_KEY:
        print("[ingest] RAPIDAPI_KEY not set. Using static dataset fallback.")
        return _load_static_dataset()

    for role in roles:
        print(f"[ingest] Fetching jobs for role: {role}")
        raw_records = await _fetch_from_jsearch(role)
        normalised = [_normalise_jsearch_record(r, role) for r in raw_records]
        all_jobs.extend(normalised)
        print(f"[ingest] {len(normalised)} jobs collected for '{role}'")

    if not all_jobs:
        print("[ingest] No jobs fetched from API. Falling back to static dataset.")
        return _load_static_dataset()

    # Save raw output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, indent=2, ensure_ascii=False)
    print(f"[ingest] Saved {len(all_jobs)} raw jobs to {output_path}")

    return all_jobs