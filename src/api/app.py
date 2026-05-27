from io import BytesIO
import os
from pathlib import Path
import tempfile
import time
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pypdf import PdfReader
from pydantic import BaseModel

from src.services.formatters import result_to_markdown

app = FastAPI(title="SkillCompass AI API", version="0.1.0")

_INDEX_PAGE_PATH = Path(__file__).resolve().parent / "index_page.html"
INDEX_HTML = _INDEX_PAGE_PATH.read_text(encoding="utf-8")



class AnalyzeRequest(BaseModel):
    target_role: str
    resume_text: str
    resume_file_path: str = ""
    weekly_hours: int = 8


class AnalyzeResponse(BaseModel):
    analysis_id: str = ""
    result: dict
    markdown_report: str


_analysis_cache: dict[str, tuple[dict, float]] = {}
_ANALYSIS_TTL_SECONDS = 60 * 30


def _cache_put(payload: dict) -> str:
    now = time.time()
    for key, (_, ts) in list(_analysis_cache.items()):
        if now - ts > _ANALYSIS_TTL_SECONDS:
            _analysis_cache.pop(key, None)
    analysis_id = str(uuid.uuid4())
    _analysis_cache[analysis_id] = (payload, now)
    return analysis_id


def _cache_get(analysis_id: str) -> dict | None:
    item = _analysis_cache.get(analysis_id)
    if not item:
        return None
    payload, ts = item
    if time.time() - ts > _ANALYSIS_TTL_SECONDS:
        _analysis_cache.pop(analysis_id, None)
        return None
    return payload


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.post("/analyze-ui")
def analyze_ui(target_role: str = Form(...), resume_file: UploadFile = File(...)) -> AnalyzeResponse:
    tmp_path: str | None = None
    try:
        content = resume_file.file.read()
        try:
            reader = PdfReader(BytesIO(content))
            text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Could not read PDF: {exc}",
            ) from exc
        if not text:
            raise HTTPException(
                status_code=400,
                detail="Uploaded PDF has no extractable text (try a text-based PDF, not a scan).",
            )
        suffix = Path(resume_file.filename or "resume.pdf").suffix or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        from src.services.analyze import run_gap_analysis

        try:
            result = run_gap_analysis(
                target_role=target_role,
                resume_text=text,
                resume_file_path=tmp_path,
            )
            markdown_report = result_to_markdown(result)
            analysis_id = _cache_put(result.model_dump())
            return AnalyzeResponse(
                analysis_id=analysis_id, result=result.model_dump(), markdown_report=markdown_report
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc) or type(exc).__name__,
            ) from exc
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    from src.services.analyze import run_analysis

    try:
        result = run_analysis(
            target_role=payload.target_role,
            resume_text=payload.resume_text,
            resume_file_path=payload.resume_file_path,
            weekly_hours=payload.weekly_hours,
        )
        markdown_report = result_to_markdown(result)
        return AnalyzeResponse(analysis_id="", result=result.model_dump(), markdown_report=markdown_report)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc) or type(exc).__name__,
        ) from exc


@app.post("/plan-ui")
def plan_ui(analysis_id: str = Form(...), weekly_hours: int = Form(8)) -> AnalyzeResponse:
    from src.agents.planning_agent import planning_agent
    from src.graph.state import GraphState

    payload = _cache_get(analysis_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Analysis expired. Please re-run gap analysis.")

    try:
        state = GraphState.model_validate(payload)
        state = state.model_copy(update={"weekly_hours": weekly_hours})
        planned = planning_agent(state)
        md = result_to_markdown(planned)
        updated_payload = planned.model_dump()
        _analysis_cache[analysis_id] = (updated_payload, time.time())
        return AnalyzeResponse(analysis_id=analysis_id, result=updated_payload, markdown_report=md)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc) or type(exc).__name__) from exc
