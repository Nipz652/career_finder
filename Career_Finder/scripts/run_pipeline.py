"""
One-shot pipeline script.
Run this once before starting the backend server to populate the database.

Usage:
    python scripts/run_pipeline.py              # full pipeline
    python scripts/run_pipeline.py --tag-only   # skip ingest/transform, just re-tag
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path

# Add backend/src to path so we can import pipeline modules
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from pipeline.ingest import ingest_jobs
from pipeline.transform import transform_jobs
from pipeline.tag import tag_jobs
from db.connection import init_db, DB_PATH
from db.queries import insert_jobs_batch

PROCESSED_PATH = Path(__file__).parent.parent / "data" / "processed" / "jobs_tagged.json"


async def run_full_pipeline() -> None:
    """Run ingest → transform → insert → tag."""
    print("=" * 50)
    print("STEP 1: Initialise database")
    print("=" * 50)
    init_db()

    print("\n" + "=" * 50)
    print("STEP 2: Ingest raw job data")
    print("=" * 50)
    raw_jobs = await ingest_jobs()
    print(f"Ingested {len(raw_jobs)} raw jobs.")

    print("\n" + "=" * 50)
    print("STEP 3: Transform and clean")
    print("=" * 50)
    clean_jobs = transform_jobs(raw_jobs)
    print(f"Cleaned {len(clean_jobs)} jobs.")

    print("\n" + "=" * 50)
    print("STEP 4: Insert into database")
    print("=" * 50)
    inserted = insert_jobs_batch(clean_jobs)
    print(f"Inserted {inserted} new jobs into DB.")

    print("\n" + "=" * 50)
    print("STEP 5: AI tag tech stacks")
    print("=" * 50)
    tagged, tokens = await tag_jobs()
    print(f"Tagged {tagged} jobs using {tokens} tokens.")

    print("\n" + "=" * 50)
    print("Pipeline complete. Database is ready.")
    print(f"DB location: {DB_PATH}")
    print("=" * 50)


async def run_tag_only() -> None:
    """Re-tag only — skip ingest and transform."""
    print("=" * 50)
    print("TAG ONLY: Re-tagging untagged jobs")
    print("=" * 50)
    tagged, tokens = await tag_jobs()
    print(f"Tagged {tagged} jobs using {tokens} tokens.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Career Path Advisor data pipeline")
    parser.add_argument(
        "--tag-only",
        action="store_true",
        help="Skip ingest/transform and only re-tag untagged jobs",
    )
    args = parser.parse_args()

    if args.tag_only:
        asyncio.run(run_tag_only())
    else:
        asyncio.run(run_full_pipeline())