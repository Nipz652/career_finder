# Project Structure

```
week_4/
│
├── data/
│   ├── raw/                        # Raw scraped/fetched job data
│   │   └── jobs_raw.json
│   ├── processed/                  # Cleaned and tagged data
│   │   └── jobs_tagged.json
│   └── jobs.db                     # SQLite database
│
├── backend/
│   ├── src/
│   │   ├── pipeline/
│   │   │   ├── __init__.py
│   │   │   ├── ingest.py           # Fetch jobs from API or static dataset
│   │   │   ├── transform.py        # Clean and normalise raw job data
│   │   │   └── tag.py              # AI tagging of tech stacks (Gemini)
│   │   │
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   ├── extractor.py        # Extract skills from resume via Gemini
│   │   │   ├── gap.py              # Deterministic skill gap set subtraction
│   │   │   ├── roadmap.py          # Generate prioritised learning roadmap
│   │   │   └── models.py           # All Pydantic models (SkillGapResult, RoadmapStep, etc.)
│   │   │
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── connection.py       # SQLite connection helper
│   │   │   └── queries.py          # All SQL queries in one place
│   │   │
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py             # POST /chat endpoint
│   │   │   ├── analyse.py          # POST /analyse endpoint
│   │   │   └── stats.py            # GET /api/stats/* endpoints
│   │   │
│   │   └── app.py                  # FastAPI app entry point, registers routers
│   │
│   ├── .env.example
│   ├── .dockerignore
│   ├── Dockerfile
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── templates/
│   │   │   ├── index.html          # Landing Page 
│   │   │   ├── roadmap.html        # Roadmap results page  + resume upload
│   │   │   └── stats.html          # Job market charts dashboard + Job upload
│   │   │
│   │   └── app.py                  # FastAPI + Jinja2 frontend server
│   │
│   ├── .env.example
│   ├── .dockerignore
│   ├── Dockerfile
│   └── pyproject.toml
│
├── scripts/
│   ├── run_pipeline.py             # One-shot: ingest → transform → tag → save to DB
│   └── clear_db.py                 # Reset database for demo/testing (optional)
│
├── tests/ (optional)
│   ├── test_pipeline.py            # Test ingest, transform, tag (optional)
│   ├── test_ai.py                  # Test extractor, gap, roadmap (optional)
│   └── test_api.py                 # Test backend endpoints with httpx (optional) 
│
├── secrets/ (Not Commited)
│   └── README.md                   # Instructions, never commit actual secrets 
│
├── .env.example                    # Root level example
├── .gitignore
├── docker-compose.yml 
└── README.md
```
