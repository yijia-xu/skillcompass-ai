from typing import Any

from pydantic import BaseModel, Field


class SkillGap(BaseModel):
    skill: str
    market_frequency: int
    gap_score: float
    reason: str


class LearningStep(BaseModel):
    phase: str
    objective: str
    tasks: list[str]
    deliverable: str


class GraphState(BaseModel):
    target_role: str
    resume_text: str
    parsed_resume_skills: list[str] = Field(default_factory=list)
    query_embedding: list[float] = Field(default_factory=list)
    matched_postings: list[dict[str, Any]] = Field(default_factory=list)
    top_skill_gaps: list[SkillGap] = Field(default_factory=list)
    learning_plan: list[LearningStep] = Field(default_factory=list)
