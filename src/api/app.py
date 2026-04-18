from fastapi import FastAPI
from pydantic import BaseModel

from src.services.analyze import run_analysis
from src.services.formatters import result_to_markdown

app = FastAPI(title="GapSolver AI API", version="0.1.0")


class AnalyzeRequest(BaseModel):
    target_role: str
    resume_text: str
    resume_file_path: str = ""


class AnalyzeResponse(BaseModel):
    result: dict
    markdown_report: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    result = run_analysis(
        target_role=payload.target_role,
        resume_text=payload.resume_text,
        resume_file_path=payload.resume_file_path,
    )
    return AnalyzeResponse(result=result.model_dump(), markdown_report=result_to_markdown(result))
