"""SQLite connection helper. Always use get_connection() — never connect directly."""

import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_URL", "/app/data/jobs.db")


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | None = None) -> None:
    """Create jobs table if it does not exist."""
    path = db_path or DB_PATH
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
    print(f"[db] Initialised at: {path}")
