"""
Backend entry point.
All imports are ABSOLUTE — no relative imports (no dot notation).
This is required because uvicorn loads app.py as a top-level module.
"""

import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

# Absolute imports — must match folder names under src/
from db.connection import init_db, DB_PATH
from routers.analyse import router as analyse_router
from routers.chat import router as chat_router
from routers.stats import router as stats_router

load_dotenv()

app = FastAPI(
    title="Career Path Advisor API",
    description="Backend for resume skill gap analysis and career roadmap generation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyse_router, tags=["Analysis"])
app.include_router(chat_router,    tags=["Chat"])
app.include_router(stats_router,   tags=["Stats"])


@app.on_event("startup")
async def startup():
    try:
        init_db(DB_PATH)
        print(f"[startup] Backend ready. DB: {DB_PATH}")
    except Exception as e:
        print(f"[startup] WARNING: DB init failed: {e}")


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
