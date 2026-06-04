"""
Backend entry point.
Creates the FastAPI app, registers all routers, and handles startup.
"""

import os
from pathlib import Path
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from .db.connection import init_db
from .routers import analyse, chat, stats

load_dotenv()

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Career Path Advisor API",
    description=(
        "Backend API for the Career Path Advisor. "
        "Analyses resume skill gaps and generates learning roadmaps."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------
app.include_router(analyse.router, tags=["Analysis"])
app.include_router(chat.router, tags=["Chat"])
app.include_router(stats.router, tags=["Stats"])


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    """Initialise DB on startup. Creates table if it doesn't exist."""
    db_path = os.getenv("DB_URL", "../data/jobs.db")
    try:
        init_db(db_path)
        print(f"[startup] Backend ready. DB: {db_path}")
    except Exception as e:
        print(f"[startup] WARNING: DB init failed: {e}")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Health"])
def health():
    """Health check endpoint. Returns ok if server is running."""
    return {"status": "ok"}