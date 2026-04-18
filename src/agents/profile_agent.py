import re
import json

from src.config import settings
from src.graph.state import GraphState
from src.services.affinda_client import extract_skills_with_affinda


def _fallback_extract_skills_from_text(resume_text: str) -> list[str]:
    stopwords = {
        "and", "the", "for", "with", "from", "that", "this", "have", "using", "used",
        "work", "team", "years", "experience", "project", "projects", "responsible",
    }
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-/]{1,30}", resume_text)
    normalized: list[str] = []
    for token in tokens:
        value = token.strip().lower()
        if value in stopwords or value.isdigit() or len(value) < 2:
            continue
        # Keep likely technical terms.
        if any(ch.isdigit() for ch in value) or any(ch in value for ch in "+#./-") or len(value) >= 4:
            normalized.append(value)
    deduped: list[str] = []
    seen = set()
    for skill in normalized:
        if skill not in seen:
            deduped.append(skill)
            seen.add(skill)
        if len(deduped) >= 40:
            break
    return deduped


def profile_agent(state: GraphState) -> GraphState:
    """Extracts normalized user skills from resume file via Affinda."""
    trace = list(state.agent_trace)
    trace.append("profile:start")
    if not settings.affinda_api_key:
        raise ValueError("ProfileAgent requires AFFINDA_API_KEY to extract resume skills.")
    if not settings.affinda_workspace_id:
        raise ValueError("ProfileAgent requires AFFINDA_WORKSPACE_ID to extract resume skills.")
    if not state.resume_file_path.strip():
        raise ValueError("ProfileAgent requires resume_file_path for Affinda document parsing.")
    try:
        normalized_skills = extract_skills_with_affinda(
            api_url=settings.affinda_api_url,
            api_key=settings.affinda_api_key,
            workspace_id=settings.affinda_workspace_id,
            file_path=state.resume_file_path,
            document_type=settings.affinda_document_type,
            collection=settings.affinda_collection,
            debug_raw_json=settings.affinda_debug_raw_json,
        )
        trace.append("profile:affinda_used")
    except Exception as exc:
        raise ValueError(f"Affinda skill extraction failed: {exc}") from exc
    if not normalized_skills:
        normalized_skills = _fallback_extract_skills_from_text(state.resume_text)
        if not normalized_skills:
            raise ValueError("Affinda returned no valid skills for this resume.")
        trace.append("profile:fallback_text_skills_used")
        print(f"[Profile Debug] final_skills_source=fallback count={len(normalized_skills)}")
        print(f"[Profile Debug] final_skills={json.dumps(normalized_skills, ensure_ascii=True)}")
    else:
        print(f"[Profile Debug] final_skills_source=affinda count={len(normalized_skills)}")
        print(f"[Profile Debug] final_skills={json.dumps(normalized_skills, ensure_ascii=True)}")

    updated_state = state.model_copy(update={"parsed_resume_skills": normalized_skills, "agent_trace": trace})
    trace = list(updated_state.agent_trace)
    trace.append("profile:skills_extracted")
    return updated_state.model_copy(update={"agent_trace": trace})
