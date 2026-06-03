"""
Clear database script.
Resets tech_stack to NULL for all jobs so they can be re-tagged.
Useful for demos or when re-running the pipeline.

Usage:
    python scripts/clear_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from db.queries import clear_tech_stacks
from db.connection import DB_PATH


if __name__ == "__main__":
    count = clear_tech_stacks()
    print(f"Cleared tech_stack for {count} rows in '{DB_PATH}'.")
    print("Run scripts/run_pipeline.py --tag-only to re-tag.")