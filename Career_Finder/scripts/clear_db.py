"""Reset tech_stack to NULL for re-tagging. Usage: python scripts/clear_db.py"""

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "src"))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DB_PATH = os.getenv("DB_URL", str(Path(__file__).resolve().parent.parent / "data" / "jobs.db"))

with sqlite3.connect(DB_PATH) as conn:
    c = conn.cursor()
    c.execute("UPDATE jobs SET tech_stack = NULL")
    conn.commit()
    print(f"Cleared tech_stack for {c.rowcount} rows in '{DB_PATH}'.")
    print("Run: python scripts/run_pipeline.py --tag-only")
