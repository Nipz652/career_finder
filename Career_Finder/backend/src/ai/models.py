"""
All Pydantic models for the Career Path Advisor.
Single source of truth — import from here everywhere.
"""

from pydantic import BaseModel, field_validator
from typing import List


class ResumeSkills(BaseModel):
    skills: List[str]

    @field_validator("skills")
    @classmethod
    def lowercase_skills(cls, v: List[str]) -> List[str]:
        return [s.strip().lower() for s in v if s.strip()]


class SkillStats(BaseModel):
    skill: str
    job_count: int
    demand_pct: float
    demand_level: str       # "High" | "Medium" | "Low"


class SkillGapResult(BaseModel):
    gaps: List[str]
    skill_demand: dict      # {skill: job_count}
    most_wanted: str = ""
    demand_range: str = ""
    statistics: List[SkillStats] = []
    tokens: int = 0
    time_ms: float = 0.0


class RoadmapStep(BaseModel):
    skill: str
    priority: int           # 1 = learn first
    reason: str             # why this skill matters for target role
    estimated_weeks: int    # realistic weeks to learn
    resources: List[str]    # URLs to learning materials


class CareerRoadmap(BaseModel):
    target_role: str
    current_skills: List[str]
    gaps: List[str]
    steps: List[RoadmapStep]
    summary: str
    tokens: int = 0
    time_ms: float = 0.0


class AnalyseRequest(BaseModel):
    resume_text: str
    target_role: str

    @field_validator("resume_text")
    @classmethod
    def resume_not_empty(cls, v: str) -> str:
        if not v or len(v.strip()) < 50:
            raise ValueError(
                "Resume text is too short. "
                "Please upload a valid resume PDF."
            )
        return v.strip()

    @field_validator("target_role")
    @classmethod
    def role_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Target role must be provided.")
        return v.strip()


class ChatRequest(BaseModel):
    message: str
    pdf_text: str | None = None


class ChatResponse(BaseModel):
    reply: str


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""