import json
import re

from src.config import settings
from src.graph.state import GraphState
from src.services.document_intelligence_skills import extract_resume_skills_from_file
from src.services.skill_normalization import normalize_skills


def _fallback_extract_skills_from_text(resume_text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-/]{1,30}", resume_text)
    raw_candidates: list[str] = []
    for token in tokens:
        # Keep likely technical terms.
        if any(ch.isdigit() for ch in token) or any(ch in token for ch in "+#./-") or len(token) >= 4:
            raw_candidates.append(token)
    return normalize_skills(raw_candidates, limit=40)


def profile_agent(state: GraphState) -> GraphState:
    """Extracts normalized user skills from the resume file via Azure Document Intelligence."""
    trace = list(state.agent_trace)
    trace.append("profile:start")
    if not settings.azure_document_intelligence_endpoint.strip():
        raise ValueError(
            "ProfileAgent requires AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT for resume parsing."
        )
    if not settings.azure_document_intelligence_key.strip():
        raise ValueError("ProfileAgent requires AZURE_DOCUMENT_INTELLIGENCE_KEY for resume parsing.")
    if not state.resume_file_path.strip():
        raise ValueError(
            "ProfileAgent requires resume_file_path for Document Intelligence document parsing."
        )
    try:
        normalized_skills = extract_resume_skills_from_file(
            file_path=state.resume_file_path,
            endpoint=settings.azure_document_intelligence_endpoint,
            api_key=settings.azure_document_intelligence_key,
            model_id=settings.azure_document_intelligence_model_id.strip() or "prebuilt-layout",
            debug_raw_response=settings.azure_document_intelligence_debug_raw_response,
        )
        trace.append("profile:document_intelligence_used")
    except Exception as exc:
        raise ValueError(f"Document Intelligence skill extraction failed: {exc}") from exc
    if not normalized_skills:
        normalized_skills = _fallback_extract_skills_from_text(state.resume_text)
        if not normalized_skills:
            raise ValueError(
                "Document Intelligence returned no skills for this resume and text fallback was empty."
            )
        trace.append("profile:fallback_text_skills_used")
        print(f"[Profile Debug] final_skills_source=text_fallback count={len(normalized_skills)}")
        print(f"[Profile Debug] final_skills={json.dumps(normalized_skills, ensure_ascii=True)}")
    else:
        print(f"[Profile Debug] final_skills_source=document_intelligence count={len(normalized_skills)}")
        print(f"[Profile Debug] final_skills={json.dumps(normalized_skills, ensure_ascii=True)}")

    updated_state = state.model_copy(update={"parsed_resume_skills": normalized_skills, "agent_trace": trace})
    trace = list(updated_state.agent_trace)
    trace.append("profile:skills_extracted")
    return updated_state.model_copy(update={"agent_trace": trace})
