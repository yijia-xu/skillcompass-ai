from typing import Any

from pydantic import BaseModel, Field, field_validator


class SkillGap(BaseModel):
    skill: str
    market_frequency: int
    gap_score: float
    reason: str

    @field_validator("skill")
    @classmethod
    def validate_skill(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("skill cannot be empty")
        return normalized


class LearningStep(BaseModel):
    phase: str
    objective: str
    tasks: list[str]
    deliverable: str

    @field_validator("phase")
    @classmethod
    def validate_phase(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("phase cannot be empty")
        return normalized

    @field_validator("tasks")
    @classmethod
    def validate_tasks(cls, value: list[str]) -> list[str]:
        normalized = [task.strip() for task in value if task.strip()]
        if not normalized:
            raise ValueError("tasks cannot be empty")
        return normalized


class GraphState(BaseModel):
    target_role: str
    resume_text: str
    agent_trace: list[str] = Field(default_factory=list)
    parsed_resume_skills: list[str] = Field(default_factory=list)
    query_embedding: list[float] = Field(default_factory=list)
    matched_postings: list[dict[str, Any]] = Field(default_factory=list)
    top_skill_gaps: list[SkillGap] = Field(default_factory=list)
    learning_plan: list[LearningStep] = Field(default_factory=list)

    @field_validator("target_role")
    @classmethod
    def validate_target_role(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("target_role cannot be empty")
        return normalized

    @field_validator("resume_text")
    @classmethod
    def validate_resume_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("resume_text cannot be empty")
        return value
