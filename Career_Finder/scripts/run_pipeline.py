"""
Career Path Advisor — Data Pipeline
Reads .mhtml files → extracts job data → inserts into SQLite → AI tags tech stacks.

Usage (inside Docker):
    python scripts/run_pipeline.py            # full pipeline
    python scripts/run_pipeline.py --tag-only # re-tag only

The script adds backend/src to sys.path automatically so it can
reuse db/connection.py and db/queries.py.
"""

import asyncio
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ── Path setup ────────────────────────────────────────────────────────
# Works whether called from /app or /app/scripts inside the container
SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR      = PROJECT_ROOT / "backend" / "src"
sys.path.insert(0, str(SRC_DIR))

load_dotenv(PROJECT_ROOT / ".env")

DB_PATH    = os.getenv("DB_URL", str(PROJECT_ROOT / "data" / "jobs.db"))
MHTML_DIR  = Path(os.getenv("MHTML_DIR", str(PROJECT_ROOT / "data" / "raw" / "mhtml")))
BATCH_SIZE = 5
MAX_RETRIES = 3
RETRY_DELAY = 5.0

# ── Role keyword map ─────────────────────────────────────────────────
ROLE_KEYWORDS: dict[str, list[str]] = {
    "Data Engineer":             ["data engineer", "data analytic", "analytics engineer",
                                  "etl", "data pipeline"],
    "Machine Learning Engineer": ["ml engineer", "ai engineer", "machine learning",
                                  "deep learning", "gen ai", "generative ai", "applied ai",
                                  "algorithm engineer", "ai application", "ai solution",
                                  "ai software", "ai chatbot", "ai & workflow"],
    "Backend Developer":         ["backend", "back-end", "back end", "python developer",
                                  "flask", "node.js", "php", "software developer",
                                  "software engineer", "application developer",
                                  "it application", "junior software", "graduate software"],
    "DevOps Engineer":           ["devops", "automation engineer", "automation tester",
                                  "automation specialist", "qa engineer", "test engineer",
                                  "system administrator"],
    "Frontend Developer":        ["frontend", "front-end", "front end", "web developer",
                                  "full stack", "ui developer"],
    "Data Scientist":            ["data scientist", "data analyst", "product data"],
}

TAG_PROMPT = """Extract the technical stack from these job descriptions.
Output format — one line per job, nothing else:
JobID: tech1, tech2, tech3

Rules:
- Include: programming languages, frameworks, tools, databases, cloud, DevOps
- Exclude: soft skills, certifications, spoken languages
- If no skills found: JobID: Not specified

{jobs}"""

INVALID_TAGS = {"not specified", "n/a", "none", "not mentioned"}


# ── Helpers ───────────────────────────────────────────────────────────

def infer_role(title: str) -> str:
    t = title.lower()
    for role, keywords in ROLE_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return role
    return "Software Engineer"


def strip_html(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", clean).strip()


def tokens_fallback(text: str) -> int:
    return len(text.split()) * 4


# ── STEP 1: Init DB ───────────────────────────────────────────────────

def step_init_db() -> None:
    print("\n[STEP 1] Initialise database")
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id          TEXT PRIMARY KEY,
                role        TEXT NOT NULL,
                title       TEXT,
                company     TEXT,
                location    TEXT,
                description TEXT,
                tech_stack  TEXT,
                source      TEXT,
                created_at  TEXT
            )
        """)
        conn.commit()
    print(f"[init] Database ready at: {DB_PATH}")


# ── STEP 2: Ingest from .mhtml files ─────────────────────────────────

def _extract_html_from_mhtml(path: Path) -> str:
    with open(path, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            try:
                return part.get_content()
            except Exception:
                raw = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
    return ""


def _parse_job_from_html(html: str, stem: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")

    # Jobstreet uses data-automation attributes — these are the correct selectors
    def by_auto(val: str):
        return soup.find(attrs={"data-automation": val})

    # Title
    title_el = by_auto("job-detail-title") or soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # Company
    company_el = by_auto("advertiser-name")
    company = company_el.get_text(strip=True) if company_el else ""

    # Location
    location_el = by_auto("job-detail-location")
    location = location_el.get_text(strip=True) if location_el else ""

    # Description — the full job ad content
    desc_el = by_auto("jobAdDetails")
    if not desc_el:
        # Fallback for other job sites
        desc_el = (
            soup.select_one(".description__text") or
            soup.select_one("#jobDescriptionText") or
            soup.select_one(".job-description") or
            soup.select_one("article") or
            soup.select_one("main")
        )
    description = desc_el.get_text(separator=" ", strip=True) if desc_el else ""

    # Require title and a meaningful description
    if not title or len(description) < 100:
        return None

    job_id = hashlib.md5(f"{title}{company}{stem}".encode()).hexdigest()
    return {
        "id":          job_id,
        "role":        infer_role(title),
        "title":       title,
        "company":     company,
        "location":    location,
        "description": description,
        "tech_stack":  None,
        "source":      f"mhtml:{stem}",
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }


def step_ingest() -> list[dict]:
    print("\n[STEP 2] Ingest from .mhtml files")
    files = sorted(MHTML_DIR.glob("*.mhtml"))

    if not files:
        print(f"[ingest] No .mhtml files found in {MHTML_DIR}")
        print("[ingest] Add .mhtml files to data/raw/mhtml/ and re-run.")
        return []

    print(f"[ingest] Found {len(files)} .mhtml files")
    jobs: list[dict] = []

    for f in files:
        html = _extract_html_from_mhtml(f)
        if not html:
            print(f"[ingest]   SKIP (no HTML): {f.name}")
            continue
        job = _parse_job_from_html(html, f.stem)
        if job is None:
            print(f"[ingest]   SKIP (no fields): {f.name}")
            continue
        jobs.append(job)
        print(f"[ingest]   OK [{job['role']}] {job['title']} @ {job['company']}")

    print(f"[ingest] Extracted {len(jobs)} jobs from .mhtml files.")
    return jobs


# ── STEP 3: Transform ─────────────────────────────────────────────────

def step_transform(raw: list[dict]) -> list[dict]:
    print("\n[STEP 3] Transform and clean")
    seen: set[str] = set()
    clean: list[dict] = []
    for job in raw:
        jid = job.get("id", "")
        if not jid or jid in seen:
            continue
        seen.add(jid)
        desc = strip_html(job.get("description", ""))
        if len(desc) < 100:
            continue
        clean.append({**job, "description": desc})
    print(f"[transform] {len(raw)} raw → {len(clean)} clean jobs.")
    return clean


# ── STEP 4: Insert ────────────────────────────────────────────────────

def step_insert(jobs: list[dict]) -> int:
    print("\n[STEP 4] Insert into database")
    if not jobs:
        print("[insert] Nothing to insert.")
        return 0
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.executemany(
            """INSERT OR IGNORE INTO jobs
               (id, role, title, company, location, description, tech_stack, source, created_at)
               VALUES
               (:id, :role, :title, :company, :location, :description, :tech_stack, :source, :created_at)""",
            jobs,
        )
        conn.commit()
        c.execute("SELECT COUNT(*) FROM jobs")
        total = c.fetchone()[0]
    print(f"[insert] {total} jobs in database.")
    return total


# ── STEP 5: Tag ───────────────────────────────────────────────────────

async def step_tag() -> tuple[int, int]:
    print("\n[STEP 5] AI tag tech stacks")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[tag] GOOGLE_API_KEY not set. Skipping.")
        return 0, 0

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
    except ImportError:
        print("[tag] google-genai not installed. Skipping.")
        return 0, 0

    # Fetch untagged
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT id, title, description FROM jobs "
            "WHERE tech_stack IS NULL OR tech_stack = ''"
        )
        jobs = [dict(r) for r in c.fetchall()]

    if not jobs:
        print("[tag] No untagged jobs.")
        return 0, 0

    print(f"[tag] Tagging {len(jobs)} jobs in batches of {BATCH_SIZE}...")
    total_tagged = 0
    total_tokens = 0
    start = time.time()

    for i in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE
        expected_ids = {j["id"] for j in batch}

        job_lines = "\n\n".join(
            f"Job {j['id']}: {j['description'][:600]}" for j in batch
        )
        prompt = TAG_PROMPT.format(jobs=job_lines)

        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await client.aio.models.generate_content(
                    model="gemini-2.0-flash", contents=prompt
                )
                text = response.text.strip()

                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    total_tokens += (
                        (response.usage_metadata.prompt_token_count or 0) +
                        (response.usage_metadata.candidates_token_count or 0)
                    )
                else:
                    total_tokens += tokens_fallback(prompt) + tokens_fallback(text)

                results: dict[str, str] = {}
                for line in text.splitlines():
                    line = line.strip()
                    if not line or ":" not in line:
                        continue
                    left, right = line.split(":", 1)
                    jid = left.strip().replace("Job", "").strip()
                    if jid in expected_ids:
                        stack = right.strip()
                        if stack.lower() not in INVALID_TAGS:
                            results[jid] = stack

                with sqlite3.connect(DB_PATH) as conn:
                    for jid, stack in results.items():
                        conn.execute(
                            "UPDATE jobs SET tech_stack = ? WHERE id = ?",
                            (stack, jid),
                        )
                    conn.commit()

                for jid, stack in results.items():
                    title = next((j["title"] for j in batch if j["id"] == jid), jid)
                    print(f"[tag]   Tagged '{title}': {stack}")
                    total_tagged += 1

                success = True
                break

            except Exception as e:
                err = str(e)
                print(f"[tag] Batch {batch_num} attempt {attempt} failed: {e}")

                if "429" in err and "PerDay" in err:
                    print("[tag] Daily quota exceeded. Stopping.")
                    return total_tagged, total_tokens
                if "400" in err and "INVALID_ARGUMENT" in err:
                    print("[tag] Invalid request. Stopping.")
                    return total_tagged, total_tokens
                if attempt < MAX_RETRIES:
                    match = re.search(r"retry in (\d+(?:\.\d+)?)s", err, re.IGNORECASE)
                    wait = float(match.group(1)) + 2 if match else RETRY_DELAY
                    print(f"[tag] Retrying in {wait:.0f}s...")
                    await asyncio.sleep(wait)

        if not success:
            print(f"[tag] Batch {batch_num} gave up.")

        await asyncio.sleep(4)

    elapsed = (time.time() - start) * 1000
    print(f"[tag] Done. Tagged: {total_tagged}, tokens: {total_tokens}, time: {elapsed:.0f}ms")
    return total_tagged, total_tokens


# ── Main ──────────────────────────────────────────────────────────────

async def main() -> None:
    tag_only = "--tag-only" in sys.argv

    print("=" * 55)
    print("  Career Path Advisor — Data Pipeline")
    print("=" * 55)

    if not tag_only:
        step_init_db()
        raw_jobs   = step_ingest()
        clean_jobs = step_transform(raw_jobs)
        step_insert(clean_jobs)
    else:
        print("\nTag-only mode — skipping ingest and insert.")

    tagged, tokens = await step_tag()

    print("\n" + "=" * 55)
    print("  Pipeline complete")
    print(f"  Tagged: {tagged} jobs | Tokens: {tokens}")
    print(f"  DB: {DB_PATH}")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
