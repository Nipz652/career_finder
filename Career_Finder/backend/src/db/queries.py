"""All SQL queries. No raw SQL anywhere else in the codebase."""

import sqlite3
from db.connection import get_connection, DB_PATH

INVALID_SKILLS = {"not specified", "n/a", "none", "not mentioned", "not available"}


# ── Read ──────────────────────────────────────────────────────────────

def get_available_roles(db_path: str | None = None) -> list[str]:
    with get_connection(db_path or DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT DISTINCT role FROM jobs WHERE role IS NOT NULL ORDER BY role")
        return [row["role"] for row in c.fetchall()]


def get_tech_stacks_by_role(role: str, db_path: str | None = None) -> list[str]:
    with get_connection(db_path or DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT tech_stack FROM jobs "
            "WHERE tech_stack IS NOT NULL AND tech_stack != '' "
            "AND LOWER(role) = LOWER(?)",
            (role,),
        )
        return [row["tech_stack"] for row in c.fetchall()]


def get_all_tech_stacks(db_path: str | None = None) -> list[str]:
    with get_connection(db_path or DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT tech_stack FROM jobs WHERE tech_stack IS NOT NULL AND tech_stack != ''"
        )
        return [row["tech_stack"] for row in c.fetchall()]


def get_skill_distribution(db_path: str | None = None) -> dict[str, int]:
    stacks = get_all_tech_stacks(db_path)
    demand: dict[str, int] = {}
    for stack in stacks:
        for skill in stack.split(","):
            skill = skill.strip().lower()
            if skill and skill not in INVALID_SKILLS:
                demand[skill] = demand.get(skill, 0) + 1
    return demand


def get_job_count_by_role(db_path: str | None = None) -> dict[str, int]:
    with get_connection(db_path or DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT role, COUNT(*) as count FROM jobs GROUP BY role ORDER BY count DESC"
        )
        return {row["role"]: row["count"] for row in c.fetchall()}


def get_tagged_vs_untagged(db_path: str | None = None) -> dict[str, int]:
    with get_connection(db_path or DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT
                CASE WHEN tech_stack IS NULL OR tech_stack = ''
                     THEN 'Untagged' ELSE 'Tagged' END as status,
                COUNT(*) as count
            FROM jobs GROUP BY status
        """)
        return {row["status"]: row["count"] for row in c.fetchall()}


def search_jobs(keyword: str, limit: int = 20, db_path: str | None = None) -> list[dict]:
    with get_connection(db_path or DB_PATH) as conn:
        c = conn.cursor()
        like = f"%{keyword}%"
        c.execute(
            """SELECT id, role, title, company,
                      tech_stack, SUBSTR(description, 1, 200) AS description
               FROM jobs
               WHERE tech_stack LIKE ? OR description LIKE ? OR title LIKE ?
               LIMIT ?""",
            (like, like, like, limit),
        )
        return [dict(row) for row in c.fetchall()]


def get_untagged_jobs(db_path: str | None = None) -> list[dict]:
    with get_connection(db_path or DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT id, role, title, description FROM jobs "
            "WHERE tech_stack IS NULL OR tech_stack = ''"
        )
        return [dict(row) for row in c.fetchall()]


# ── Write ─────────────────────────────────────────────────────────────

def insert_jobs_batch(jobs: list[dict], db_path: str | None = None) -> int:
    with get_connection(db_path or DB_PATH) as conn:
        c = conn.cursor()
        c.executemany(
            """INSERT OR IGNORE INTO jobs
               (id, role, title, company, location, description, tech_stack, source, created_at)
               VALUES
               (:id, :role, :title, :company, :location, :description, :tech_stack, :source, :created_at)""",
            jobs,
        )
        conn.commit()
        return c.rowcount


def update_tech_stack(job_id: str, tech_stack: str, db_path: str | None = None) -> None:
    with get_connection(db_path or DB_PATH) as conn:
        conn.execute(
            "UPDATE jobs SET tech_stack = ? WHERE id = ?",
            (tech_stack, job_id),
        )
        conn.commit()


def clear_tech_stacks(db_path: str | None = None) -> int:
    with get_connection(db_path or DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE jobs SET tech_stack = NULL")
        conn.commit()
        return c.rowcount
