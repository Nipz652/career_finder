"""
Frontend server.
Serves HTML pages via FastAPI + Jinja2.
Injects BACKEND_URL from environment into every template.
"""

import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"backend_url": BACKEND_URL},
    )


@app.get("/roadmap")
async def roadmap(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="roadmap.html",
        context={"backend_url": BACKEND_URL},
    )


@app.get("/stats")
async def stats(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="stats.html",
        context={"backend_url": BACKEND_URL},
    )