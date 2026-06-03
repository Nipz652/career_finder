<<<<<<< HEAD
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
=======
import json     # LLM response parsing
import sqlite3   # SQLite database interaction
import time    # Delay between retries
from tracemalloc import start
from typing import List     # Type hinting for better code clarity

from ..ai.prompt_model import prompt_model  # LLM communication

BATCH_SIZE = 3  # low token usage, stable JSON output, lower memory usage, less chance of timeout; TPM is 250k, but as I want to keep my RAM usage low, and ensure stable output, I keep the batch size small. If want to speed up, can increase batch size, but need to monitor the token usage and response quality
MAX_RETRIES = 3 
RETRY_DELAY = 5
MODEL_NAME = "llama3.1"     # llama3.1 is good for structured data extraction, has stronger formatting discipline; phi3 is more optimized for lightweight inference, and deepseek-r1:1.5b is more optimized for search relevance and problem solving, usually shows step-by-step reasoning, which is not ideal for concise tech stack extraction.

SYSTEM_PROMPT = """
You are a technical recruiter extracting technology stacks from job descriptions.
Extract the main technologies, programming languages, frameworks, databases, and tools mentioned.

Rules:
- Include programming languages, frameworks, databases, cloud platforms, development tools, AI/ML libraries, enterprise systems, APIs, and analytics tools.
- Use comma separation without extra spaces after commas.
- If no clear tech stack is found, use "Not specified".
- Keep tags concise.
- Exclude soft skills.
- Use comma-separated strings of the technical stack used.
- Return ONLY JSON, no other text.

Expected JSON format:
[
  {
    "source_id": "12345",
    "tech_stack": "Python, SQL, statistics, machine learning"
  }
]
""".strip()

def build_prompt(rows: List[tuple]) -> str:
    """
    Build a token-efficient batch prompt.
    Convert each row into optimized text blocks and concatenate them with the prompt.
    """
    job_blocks = []

    for row in rows:
        source_id, title, description = row

        cut_description = description[:2000]    # limit description to 2000 characters to save tokens

        block = f"""
        Job ID: {source_id}
        Title: {title}
        Description:
        {cut_description}
        """.strip()

        job_blocks.append(block)

    append_jobs = "\n---\n".join(job_blocks)    # separate jobs with clear delimiters for better parsing and readability

    return f"""
{SYSTEM_PROMPT}

Analyze the following jobs.

{append_jobs}
""".strip()

def parse_response(response: str):
    """
    Safely parse model JSON response.
    """
    try:
        start = response.find("[")  # the start of the JSON array
        end = response.rfind("]") + 1   # the end of the JSON array

        # if the response does not contain valid JSON array
        if start == -1 or end == 0:
            return None

        json_text = response[start:end]     # extract the JSON array from the response, ignoring any extra text before or after

        return json.loads(json_text)    # parse the JSON text into Python list of dictionaries

    # catch JSON parsing errors or any other unexpected issues
    except Exception:
        return None

def fetch_unprocessed_jobs(cursor, limit: int):
    """
    Fetch jobs without tech stack.
    """
    cursor.execute(
        """
        SELECT source_id, job_title, description
        FROM jobs
        WHERE tech_stack IS NULL
           OR tech_stack = ''
        LIMIT ?
        """,
        (limit,),
    )   # skip already processed jobs (tech_stack is not NULL), limit the number of rows to the specified batch size to avoid loading entire DB into RAM

    return cursor.fetchall()    # returns a list of tuples, each tuple contains (source_id, job_title, description)

def update_tech_stack(cursor, source_id: str, tech_stack: str):
    """
    Update tech stack for specified source id .
    """
    cursor.execute(
        """
        UPDATE jobs
        SET tech_stack = ?
        WHERE source_id = ?
        """,
        (tech_stack, source_id),
    ) 

def process_batch(cursor, conn, batch_rows, batch_index: int):
    """
    Process one batch with retry handling.
    """
    prompt = build_prompt(batch_rows)   # create a single prompt for the entire batch

    # create a retry loop to handle transient errors, such as network issues or temporary model unavailability
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = prompt_model(MODEL_NAME, prompt)     # send the batch prompt to the model and get the response, which returns a JSON string containing the source_id and tech_stack for each job in the batch

            parsed = parse_response(response)   # parse the model response to extract the structured data (list of dictionaries with source_id and tech_stack)

            # if parsing fails
            if parsed is None:
                raise ValueError("Invalid JSON response")

            # validate that the number of parsed items matches the number of input jobs to ensure we have a complete response for the batch
            if len(parsed) != len(batch_rows):
                raise ValueError("Mismatch between batch size and response")

            for item in parsed:
                source_id = str(item.get("source_id", "")).strip()
                tech_stack = str(item.get("tech_stack", "")).strip()

                # if either source_id or tech_stack is missing or empty, skip updating the database for that job
                if not source_id or not tech_stack:
                    continue

                update_tech_stack(cursor, source_id, tech_stack)    # update the database

                print(f"Analyzed Job {source_id}: {tech_stack}")     # log the result for each job in the batch

            conn.commit()   # commit per batch and save changes to the database
            return True  # batch processed successfully

        # catch any exceptions that occur during the API call
        except Exception as e:
            print(f"[Batch {batch_index}] Attempt {attempt} failed: {e}")
            
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)  # wait before retrying
    return False # failed after all retries

def tag_data(db_url: str):
    """
    Read jobs from SQLite and populate tech_stack.
    
    Input: 
        - database URL (file path for SQLite)
    Output: 
        - None (updates the database in place, and prints the results to the console)
    """
    try:
        conn = sqlite3.connect(db_url)  # connect to the database
        cursor = conn.cursor()  # cursor executes SQL commands

        batch_index = 0  # to keep track of batch number for logging

        while True:
            rows = fetch_unprocessed_jobs(cursor, BATCH_SIZE)  # fetch a batch of unprocessed jobs

            # if no more unprocessed jobs, exit the loop
            if not rows:
                print("No more jobs to process.")
                break

            process_batch(cursor, conn, rows, batch_index)  # process the batch and update the database
            batch_index += 1     # increment batch index for logging
            
        conn.close()    # close the database connection after processing all batches

    # catch SQLite errors
    except sqlite3.Error as e:
        print(f"[SQLite Error] {e}")

    # catch any other unexpected errors
    except Exception as e:
        print(f"[Error] {e}")
>>>>>>> 49f1bfbb41c01134e069d557fde8aaa2f3c834ed
