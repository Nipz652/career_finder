# Career Finder 🎯

AI-powered career advisor that analyzes resumes, identifies skill gaps against real job market data, and generates personalized learning roadmaps.

## Project Overview

### Problem Statement

Fresh graduates and career changers face three major challenges:
1. **Uncertainty about market demands** - What skills are actually in demand?
2. **Unclear skill gaps** - Which skills should they learn first?
3. **Lack of structured guidance** - How to prioritize learning effectively?

### Target Users

- **Fresh graduates** entering the tech industry
- **Career changers** transitioning into tech roles
- **Junior developers** looking to level up
- **Students** planning their learning path

### System Goal

Provide data-driven, personalized career guidance by:
- Extracting technical skills from resumes using AI
- Comparing skills against real job market data
- Generating prioritized learning roadmaps with resources
- Offering interactive career chat support

## System Architecture

### Data Flow

1. **User Upload** → Resume PDF sent to backend
2. **Skill Extraction** → Gemini AI parses technical skills
3. **Gap Analysis** → Compare with job market database
4. **Roadmap Generation** → AI creates prioritized learning plan
5. **Interactive Chat** → Context-aware career advice

### Module Breakdown

| Module | Path | Purpose |
|--------|------|---------|
| **AI Extractor** | `ai/extractor.py` | Extract skills from resume text using Gemini |
| **Gap Analyzer** | `ai/gap.py` | Compute deterministic skill gaps vs job data |
| **Roadmap Generator** | `ai/roadmap.py` | Generate personalized learning roadmaps |
| **Chat Handler** | `routers/chat.py` | Context-aware career conversation |
| **Stats API** | `routers/stats.py` | Job market analytics endpoints |
| **ETL Pipeline** | `scripts/run_pipeline.py` | Populate database from MHTML files |

## Setup & Installation

### Prerequisites

- **Python 3.12+** (3.14 for Docker)
- **Google Gemini API Key** ([Get one here](https://aistudio.google.com/app/apikey))
- **Docker** (optional, for containerized deployment)
- **Ollama** (optional, for local LLM tagging)


```bash
# 1. Clone the repository
git clone https://github.com/Nipz652/career_finder
cd Career_Finder

# 2. Set up environment variables
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```


Before using the application, populate the database with job data:
```bash
# Run the complete ETL pipeline
python scripts/run_pipeline.py

# Or only re-tag existing jobs
python scripts/run_pipeline.py --tag-only

# Clear tech_stack if want to re-tag jobs.db
python scripts/clear_db.py
```

### Option 1: Docker (Recommended)

```bash
# Build and run
docker-compose up --build

# Access the application:
# Frontend: http://localhost:8000
# Backend API: http://localhost:8001
# API Docs: http://localhost:8001/docs
```

### Option 2: Local Development

Backend Setup
```bash
cd backend

# Install dependencies
uv sync

# Run the server
uv run uvicorn src.app:app --reload --port 8001
```

Frontend Setup
```bash
cd frontend

# Install dependencies
uv sync

# Run the server
uv run uvicorn src.app:app --reload
```

## Features

### Implemented Features

#### 1. Resume Skill Extraction
- **AI-powered parsing** using Google Gemini 2.0 Flash
- **Technical focus only** (excludes soft skills, certifications)
- **Compound skill preservation** (e.g., "C/C++", "React Native")
- **Jailbreak detection** for security
- **Automatic retries** with exponential backoff
- **Daily quota handling** with graceful degradation

#### 2. Skill Gap Analysis
- **Market-driven comparison** against real job listings
- **Deterministic algorithm** (no AI, pure set subtraction)
- **Three demand levels**: High (66%+), Medium (33-66%), Low (<33%)
- **Priority ranking** based on job market demand
- **Most wanted skill identification**
- **Sub-100ms response time** (no API calls)

#### 3. Learning Roadmap Generation
- **AI-generated** personalized recommendations
- **Priority-based ordering** (highest demand first)
- **Time estimates** (weeks per skill)
- **Resource links** (real URLs for learning)
- **Fallback mode** when AI is unavailable
- **Token usage tracking** for cost monitoring

#### 4. Job Market Analytics Dashboard
- **Top 10 in-demand skills** chart
- **Job counts by role** distribution
- **Tagged vs untagged jobs** tracking
- **Job search functionality** with keyword matching
- **Available roles list** for validation

#### 5. Data Pipeline
- **MHTML ingestion** → Extract HTML content
- **HTML parsing** → Structured job data
- **LLM tagging** → Tech stack extraction (Ollama)
- **SQLite storage** → Queryable database
- **Resumable processing** (skip already processed)

## Technical Decisions

### Architecture Choices

| Decision | Rationale |
|----------|-----------|
| SQLite over PostgreSQL | Simplicity, zero configuration, sufficient for moderate data volume (<1M rows) |
| Two-step AI pipeline | Deterministic gap analysis (fast, free) + AI roadmap (expensive but essential) |
| Gemini 2.0 Flash | Fastest Gemini model, optimized for structured extraction tasks |
| Ollama for tagging | Local LLM for batch processing, avoids API costs for large datasets |
| Sync gap analysis | No AI calls needed for set subtraction, sub-100ms response |
| Async AI calls | Gemini API calls are async to prevent blocking |
| Dual Docker services | Clear separation of concerns, independent scaling |

### Trade-offs Made

1. SQLite vs PostgreSQL
- ✅ Pro: No separate database server, easier deployment
- ❌ Con: Limited concurrent writes, no built-in replication

2. Gemini vs OpenAI
- ✅ Pro: Lower cost, faster response, good structured output
- ❌ Con: Less mature ecosystem, occasional formatting issues

3. Deterministic gap analysis
- ✅ Pro: No API cost, instant response, consistent results
- ❌ Con: Cannot infer related skills or handle synonyms

4. Batch tagging with Ollama
- ✅ Pro: No API cost for large datasets, privacy preservation
- ❌ Con: Requires local GPU, slower than cloud APIs

5. Server-side rendering (Jinja2) vs React
- ✅ Pro: Simpler stack, faster initial load, better SEO
- ❌ Con: Less interactive UI, full page reloads

## Limitations

### Known Issues

1. Database Performance
- No full-text search (uses LIKE queries)
- No query caching for repeated analytics
- Limited to <1M rows for good performance

2. AI Capabilities
- Daily quota limits (Gemini free tier)

3. Skill Extraction
- Only extracts technical skills (intentional)
- Cannot infer related skills (e.g., "data analysis" → "pandas")

4. Job Data
- Requires manual pipeline run to update
- No automatic scheduled ingestion
- Limited to MHTML format from specific sources

5. Frontend
- No responsive design for mobile
- No real-time updates

### Future Improvements

- Support for multiple job sources (LinkedIn, Indeed APIs)
- Add user accounts and saved roadmaps
- Implement skill synonym matching (e.g., "Keras" → "TensorFlow")
- Add export to PDF for roadmaps
- Real-time job alerts when skills match
- Salary estimation based on skill set

## Project Structure

```
Career_Finder/
│
├── data/
│   ├── raw/                     # Raw scraped/fetched job data
│   │   └── mthml/
│   │   |   └── jobs_source.mhtml
│   │   └── jobs_static.json
│   └── jobs.db                     # SQLite database
│
├── backend/
│   ├── src/
│   │   ├── ai/
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
├── .env                            # User has to copy paste from .env.example, and include their GOOGLE_API_KEY 
├── .env.example                    # Root level example
├── .gitignore
├── docker-compose.yml 
└── README.md
```
