"""
SQLite connection helper.
Always use get_connection() — never connect directly in other modules.
"""

import sqlite3
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_URL", "../../data/jobs.db")


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """
    Returns a sqlite3 connection to the jobs database.

    Args:
        db_path: Optional override path. Uses DB_URL env var by default.

    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row
        so rows can be accessed by column name.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | None = None) -> None:
    """
    Create the jobs table if it doesn't exist.
    Run this on startup.
    """
    path = db_path or DB_PATH

    # Ensure parent directory exists
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with get_connection(path) as conn:
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
    print(f"[db] Database initialised at: {path}")