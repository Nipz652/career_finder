"""
All SQL queries in one place.
No raw SQL anywhere else in the codebase — import from here.
"""

import sqlite3
from db.connection import get_connection, DB_PATH


# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

def get_tech_stacks_by_role(role: str, db_path: str | None = None) -> list[str]:
    """
    Returns all non-empty tech_stack values for a given role.
    Used by gap.py for skill gap computation.
    """
    with get_connection(db_path or DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tech_stack FROM jobs
            WHERE tech_stack IS NOT NULL
              AND tech_stack != ''
              AND LOWER(role) = LOWER(?)
            """,
            (role,),
        )
        return [row["tech_stack"] for row in cursor.fetchall()]


def get_all_tech_stacks(db_path: str | None = None) -> list[str]:
    """Returns all non-empty tech_stack values across all roles."""
    with get_connection(db_path or DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tech_stack FROM jobs
            WHERE tech_stack IS NOT NULL AND tech_stack != ''
            """
        )
        return [row["tech_stack"] for row in cursor.fetchall()]


def get_available_roles(db_path: str | None = None) -> list[str]:
    """Returns distinct role names available in the database."""
    with get_connection(db_path or DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT role FROM jobs ORDER BY role"
        )
        return [row["role"] for row in cursor.fetchall()]


def get_jobs_by_role(
    role: str,
    limit: int = 50,
    db_path: str | None = None,
) -> list[dict]:
    """Returns job records for a given role."""
    with get_connection(db_path or DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, role, title, company, location, tech_stack, description
            FROM jobs
            WHERE LOWER(role) = LOWER(?)
            LIMIT ?
            """,
            (role, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def search_jobs(keyword: str, limit: int = 20, db_path: str | None = None) -> list[dict]:
    """
    Search jobs by keyword in description or tech_stack.
    Returns job records matching the keyword.
    """
    with get_connection(db_path or DB_PATH) as conn:
        cursor = conn.cursor()
        like = f"%{keyword}%"
        cursor.execute(
            """
            SELECT id, role, title, company, tech_stack,
                   SUBSTR(description, 1, 200) AS description
            FROM jobs
            WHERE tech_stack LIKE ?
               OR description LIKE ?
               OR title LIKE ?
            LIMIT ?
            """,
            (like, like, like, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_skill_distribution(db_path: str | None = None) -> dict[str, int]:
    """
    Returns skill → job count across all roles.
    Used by stats endpoints for charts.
    """
    tech_stacks = get_all_tech_stacks(db_path)
    demand: dict[str, int] = {}
    invalid = {"not specified", "n/a", "none", "not mentioned", "not available"}

    for stack in tech_stacks:
        for skill in stack.split(","):
            skill = skill.strip().lower()
            if skill and skill not in invalid:
                demand[skill] = demand.get(skill, 0) + 1

    return demand


def get_job_count_by_role(db_path: str | None = None) -> dict[str, int]:
    """Returns role → total job count. Used for bar chart."""
    with get_connection(db_path or DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, COUNT(*) as count FROM jobs GROUP BY role ORDER BY count DESC"
        )
        return {row["role"]: row["count"] for row in cursor.fetchall()}


def get_tagged_vs_untagged(db_path: str | None = None) -> dict[str, int]:
    """Returns tagged vs untagged job counts."""
    with get_connection(db_path or DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                CASE
                    WHEN tech_stack IS NULL OR tech_stack = '' THEN 'Untagged'
                    ELSE 'Tagged'
                END as status,
                COUNT(*) as count
            FROM jobs
            GROUP BY status
            """
        )
        return {row["status"]: row["count"] for row in cursor.fetchall()}


# ---------------------------------------------------------------------------
# Write queries
# ---------------------------------------------------------------------------

def insert_job(job: dict, db_path: str | None = None) -> None:
    """
    Insert a single job record.
    Ignores duplicates (INSERT OR IGNORE).
    """
    with get_connection(db_path or DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO jobs
                (id, role, title, company, location, description, source, created_at)
            VALUES
                (:id, :role, :title, :company, :location, :description, :source, :created_at)
            """,
            job,
        )
        conn.commit()


def insert_jobs_batch(jobs: list[dict], db_path: str | None = None) -> int:
    """
    Insert multiple job records in one transaction.
    Returns number of rows inserted.
    """
    with get_connection(db_path or DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT OR IGNORE INTO jobs
                (id, role, title, company, location, description, source, created_at)
            VALUES
                (:id, :role, :title, :company, :location, :description, :source, :created_at)
            """,
            jobs,
        )
        conn.commit()
        return cursor.rowcount


def update_tech_stack(job_id: str, tech_stack: str, db_path: str | None = None) -> None:
    """Update the tech_stack for a single job by ID."""
    with get_connection(db_path or DB_PATH) as conn:
        conn.execute(
            "UPDATE jobs SET tech_stack = ? WHERE id = ?",
            (tech_stack, job_id),
        )
        conn.commit()


def clear_tech_stacks(db_path: str | None = None) -> int:
    """
    Reset all tech_stack values to NULL.
    Used by clear_db.py script for re-tagging.
    Returns number of rows affected.
    """
    with get_connection(db_path or DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE jobs SET tech_stack = NULL")
        conn.commit()
        return cursor.rowcount


def get_untagged_jobs(db_path: str | None = None) -> list[dict]:
    """Returns jobs where tech_stack is NULL or empty. Used by tag.py."""
    with get_connection(db_path or DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, role, title, description FROM jobs
            WHERE tech_stack IS NULL OR tech_stack = ''
            """
        )
        return [dict(row) for row in cursor.fetchall()]