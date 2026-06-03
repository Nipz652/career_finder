"""
Data ingestion module.
Supports three data sources (checked in order):
  1. Directory of .mhtml files  → set MHTML_DIR env var or pass mhtml_dir arg
  2. JSearch API via RapidAPI   → set RAPIDAPI_KEY env var
  3. Static JSON fallback       → data/raw/jobs_static.json

Saves raw data to data/raw/jobs_raw.json.
"""

import json
import os
import uuid
import hashlib
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
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

# Role inference — maps keywords found in job titles to canonical role names.
# Add more keywords here if your .mhtml files contain other role variations.
ROLE_KEYWORDS: dict[str, list[str]] = {
    "Data Engineer":              ["data engineer", "etl developer", "data pipeline", "data platform"],
    "Backend Developer":          ["backend", "back-end", "back end", "api developer", "server-side"],
    "Machine Learning Engineer":  ["machine learning", "ml engineer", "ai engineer", "deep learning"],
    "DevOps Engineer":            ["devops", "platform engineer", "sre", "site reliability", "cloud engineer", "infrastructure engineer"],
    "Frontend Developer":         ["frontend", "front-end", "front end", "ui developer", "react developer", "vue developer"],
}

# Default directory to look for .mhtml files when MHTML_DIR env var is not set.
DEFAULT_MHTML_DIR = Path("../../data/raw/mhtml")

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
MHTML_DIR_ENV = os.getenv("MHTML_DIR", "")

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HEADERS = {
    "X-RapidAPI-Key": RAPIDAPI_KEY,
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
}


# ---------------------------------------------------------------------------
# MHTML parser
# ---------------------------------------------------------------------------
def _extract_html_from_mhtml(mhtml_path: Path) -> str:
    """
    Extract the HTML body from a .mhtml (MIME HTML) file.
    Returns empty string if no HTML part is found.
    """
    with open(mhtml_path, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)

    # MHTML is a multipart MIME container — walk parts to find text/html
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            try:
                return part.get_content()
            except Exception:
                # Fallback for encoding edge cases
                raw = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")

    return ""


def _infer_role(title: str) -> str:
    """
    Infer canonical role name from job title string.
    Returns 'Other' if no keyword matches.
    """
    title_lower = title.lower()
    for role, keywords in ROLE_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            return role
    return "Other"


def _parse_job_from_html(html: str, source_stem: str) -> dict | None:
    """
    Parse a job record from raw HTML content.

    Tries a sequence of common CSS selectors used by job sites
    (LinkedIn, Indeed, JobStreet, Glassdoor, etc.).
    Returns None if the minimum required fields cannot be extracted.
    """
    soup = BeautifulSoup(html, "html.parser")

    # --- Title ---
    title_el = (
        soup.select_one("h1.job-title") or
        soup.select_one("h1.topcard__title") or          # LinkedIn
        soup.select_one("h1[data-testid='jobsearch-JobInfoHeader-title']") or  # Indeed
        soup.select_one(".job-header-title") or           # JobStreet
        soup.select_one("h1")                             # generic fallback
    )
    title = title_el.get_text(strip=True) if title_el else ""

    # --- Company ---
    company_el = (
        soup.select_one(".topcard__org-name-link") or     # LinkedIn
        soup.select_one("[data-testid='inlineHeader-companyName']") or  # Indeed
        soup.select_one(".company-name") or
        soup.select_one("[data-company]") or
        soup.select_one(".employer-name")
    )
    company = company_el.get_text(strip=True) if company_el else ""

    # --- Location ---
    location_el = (
        soup.select_one(".topcard__flavor--bullet") or    # LinkedIn
        soup.select_one("[data-testid='job-location']") or
        soup.select_one(".location") or
        soup.select_one("[data-location]")
    )
    location = location_el.get_text(strip=True) if location_el else ""

    # --- Description ---
    desc_el = (
        soup.select_one(".description__text") or          # LinkedIn
        soup.select_one("#jobDescriptionText") or         # Indeed
        soup.select_one(".job-description") or
        soup.select_one("#job-details") or
        soup.select_one(".description") or
        soup.select_one("article") or
        soup.select_one("main")                           # last resort
    )
    description = desc_el.get_text(separator=" ", strip=True) if desc_el else ""

    # Require at minimum a title and a non-trivial description
    if not title or len(description) < 100:
        return None

    # Stable ID based on content so re-runs don't create duplicates
    stable_id = hashlib.md5(f"{title}{company}{source_stem}".encode()).hexdigest()

    return {
        "id":          stable_id,
        "role":        _infer_role(title),
        "title":       title,
        "company":     company,
        "location":    location,
        "description": description,
        "tech_stack":  None,
        "source":      f"mhtml:{source_stem}",
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }


async def _ingest_from_mhtml(mhtml_dir: Path) -> list[dict]:
    """
    Walk a directory of .mhtml files and parse each one into a job record.
    Files that cannot be parsed are skipped with a warning.
    """
    mhtml_files = sorted(mhtml_dir.glob("*.mhtml"))

    if not mhtml_files:
        print(f"[ingest] No .mhtml files found in {mhtml_dir}")
        return []

    print(f"[ingest] Found {len(mhtml_files)} .mhtml files in {mhtml_dir}")

    jobs: list[dict] = []

    for mhtml_path in mhtml_files:
        html = _extract_html_from_mhtml(mhtml_path)

        if not html:
            print(f"[ingest]   Skipped (no HTML content): {mhtml_path.name}")
            continue

        job = _parse_job_from_html(html, source_stem=mhtml_path.stem)

        if job is None:
            print(f"[ingest]   Skipped (could not extract fields): {mhtml_path.name}")
            continue

        jobs.append(job)
        print(f"[ingest]   Parsed: {mhtml_path.name}  →  [{job['role']}] {job['title']} @ {job['company']}")

    print(f"[ingest] Extracted {len(jobs)} jobs from .mhtml files.")
    return jobs


# ---------------------------------------------------------------------------
# JSearch API fetcher (unchanged from original)
# ---------------------------------------------------------------------------
async def _fetch_from_jsearch(role: str, num_pages: int = 2) -> list[dict]:
    """Fetch job postings for a role from the JSearch API."""
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
                        "country": "my",
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


def _normalise_jsearch_record(record: dict, role: str) -> dict:
    """Convert a JSearch API record to our internal job schema."""
    return {
        "id":          record.get("job_id") or str(uuid.uuid4()),
        "role":        role,
        "title":       record.get("job_title", ""),
        "company":     record.get("employer_name", ""),
        "location":    record.get("job_city", "") or record.get("job_country", ""),
        "description": record.get("job_description", ""),
        "tech_stack":  None,
        "source":      "jsearch",
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Static JSON fallback (unchanged from original)
# ---------------------------------------------------------------------------
def _load_static_dataset() -> list[dict]:
    """Load a bundled static job dataset when API is unavailable."""
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
    mhtml_dir: Path | None = None,
) -> list[dict]:
    """
    Fetch raw job data. Source priority:

      1. .mhtml directory  — if mhtml_dir arg is given, or MHTML_DIR env var is set,
                             or data/raw/mhtml/ directory exists and has .mhtml files
      2. JSearch API       — if RAPIDAPI_KEY is set
      3. Static JSON       — data/raw/jobs_static.json fallback

    Args:
        roles:       List of role names (used by JSearch only). Defaults to TARGET_ROLES.
        output_path: Where to save the raw JSON. Defaults to RAW_OUTPUT_PATH.
        mhtml_dir:   Path to directory containing .mhtml files. Overrides env var.

    Returns:
        List of normalised raw job dicts.
    """
    roles = roles or TARGET_ROLES
    output_path = output_path or RAW_OUTPUT_PATH

    # --- Resolve mhtml directory ---
    resolved_mhtml_dir: Path | None = None

    if mhtml_dir is not None:
        resolved_mhtml_dir = Path(mhtml_dir)
    elif MHTML_DIR_ENV:
        resolved_mhtml_dir = Path(MHTML_DIR_ENV)
    elif DEFAULT_MHTML_DIR.exists() and any(DEFAULT_MHTML_DIR.glob("*.mhtml")):
        resolved_mhtml_dir = DEFAULT_MHTML_DIR

    # --- Source 1: .mhtml files ---
    if resolved_mhtml_dir is not None:
        print(f"[ingest] Source: .mhtml directory → {resolved_mhtml_dir}")
        all_jobs = await _ingest_from_mhtml(resolved_mhtml_dir)

        if all_jobs:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(all_jobs, f, indent=2, ensure_ascii=False)
            print(f"[ingest] Saved {len(all_jobs)} raw jobs to {output_path}")
            return all_jobs

        print("[ingest] .mhtml directory was empty or all files failed. Falling back.")

    # --- Source 2: JSearch API ---
    if RAPIDAPI_KEY:
        print("[ingest] Source: JSearch API")
        all_jobs: list[dict] = []

        for role in roles:
            print(f"[ingest] Fetching jobs for role: {role}")
            raw_records = await _fetch_from_jsearch(role)
            normalised = [_normalise_jsearch_record(r, role) for r in raw_records]
            all_jobs.extend(normalised)
            print(f"[ingest] {len(normalised)} jobs collected for '{role}'")

        if all_jobs:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(all_jobs, f, indent=2, ensure_ascii=False)
            print(f"[ingest] Saved {len(all_jobs)} raw jobs to {output_path}")
            return all_jobs

        print("[ingest] No jobs from API. Falling back to static dataset.")

    # --- Source 3: Static JSON ---
    print("[ingest] Source: static dataset fallback")
    return _load_static_dataset()