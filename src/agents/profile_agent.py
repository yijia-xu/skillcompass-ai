import json
import re
import time

import requests
from requests.exceptions import RequestException
from src.config import settings
from src.graph.state import GraphState
from src.services.skill_normalization import normalize_skills
from src.services.skill_normalization import split_skill_phrases


def _fallback_extract_skills_from_text(resume_text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-/]{1,30}", resume_text)
    raw_candidates: list[str] = []
    for token in tokens:
        # Keep likely technical terms.
        if any(ch.isdigit() for ch in token) or any(ch in token for ch in "+#./-") or len(token) >= 4:
            raw_candidates.append(token)
    return normalize_skills(raw_candidates, limit=40)


def _collect_skill_like_values(node, out: list[str], in_skill_context: bool = False) -> None:
    skill_keys = {"skill", "skills", "skillset", "technologies", "technology"}
    value_keys = {"name", "skill", "value", "label"}
    if isinstance(node, dict):
        for key, value in node.items():
            key_is_skill = key.lower() in skill_keys
            next_in_skill_context = in_skill_context or key_is_skill
            if key_is_skill and isinstance(value, str):
                out.append(value)
            elif next_in_skill_context and key.lower() in value_keys and isinstance(value, str):
                out.append(value)
            _collect_skill_like_values(value, out, next_in_skill_context)
    elif isinstance(node, list):
        for item in node:
            _collect_skill_like_values(item, out, in_skill_context)


def _extract_string_candidates(node, out: list[str]) -> None:
    if isinstance(node, str):
        out.append(node)
        return
    if isinstance(node, list):
        for item in node:
            _extract_string_candidates(item, out)
        return
    if isinstance(node, dict):
        for value in node.values():
            _extract_string_candidates(value, out)


def _collect_from_untyped_data_fields(payload: dict, out: list[str]) -> None:
    data = payload.get("data")
    if not isinstance(data, dict):
        return
    excluded_keys = {
        "rawtext", "text", "summary", "profile", "personal", "contact", "metadata", "meta",
        "experience", "workexperience", "education", "projects", "publications", "references",
    }
    for key, value in data.items():
        if key.strip().lower() in excluded_keys:
            continue
        if isinstance(value, str):
            if len(value) <= 64:
                out.append(value)
            continue
        if isinstance(value, (list, dict)):
            _extract_string_candidates(value, out)


def _flatten_skills(payload: dict) -> list[str]:
    candidates: list[str] = []
    data = payload.get("data", payload)
    possible_paths = [
        data.get("skills"),
        data.get("skillSet"),
        data.get("resume", {}).get("skills") if isinstance(data.get("resume"), dict) else None,
    ]
    for path in possible_paths:
        if not isinstance(path, list):
            continue
        for item in path:
            if isinstance(item, str):
                candidates.append(item)
            elif isinstance(item, dict):
                value = item.get("name") or item.get("skill") or item.get("value")
                if isinstance(value, str):
                    candidates.append(value)
    _collect_skill_like_values(payload, candidates)
    _collect_from_untyped_data_fields(payload, candidates)
    expanded: list[str] = []
    for value in candidates:
        if not value or not value.strip():
            continue
        expanded.extend(split_skill_phrases(value))
    return normalize_skills(expanded, limit=60)


def _build_affinda_debug_summary(payload: dict, stage: str) -> str:
    data = payload.get("data")
    meta = payload.get("meta")
    top_keys = sorted(payload.keys()) if isinstance(payload, dict) else []
    data_keys = sorted(data.keys()) if isinstance(data, dict) else []
    identifier = payload.get("identifier") or payload.get("id")
    if isinstance(data, dict):
        identifier = identifier or data.get("identifier") or data.get("id")
    if isinstance(meta, dict):
        identifier = identifier or meta.get("identifier") or meta.get("id")
    return (
        f"stage={stage}, identifier={identifier}, top_keys={top_keys[:12]}, "
        f"data_keys={data_keys[:12]}, has_top_skills={isinstance(payload.get('skills'), list)}, "
        f"has_data_skills={isinstance(data.get('skills'), list) if isinstance(data, dict) else False}, "
        f"has_data_skillSet={isinstance(data.get('skillSet'), list) if isinstance(data, dict) else False}"
    )


def _request_with_retry(method: str, url: str, max_attempts: int = 3, **kwargs) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.request(method=method, url=url, **kwargs)
            response.raise_for_status()
            return response
        except RequestException as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            time.sleep(1.2 * attempt)
    raise ValueError(f"Affinda request failed after {max_attempts} attempts: {last_error}")


def _extract_skills_with_affinda(file_path: str) -> list[str]:
    headers = {
        "Authorization": f"Bearer {settings.affinda_api_key}",
        "Accept": "application/json",
        "User-Agent": "GapSolverAI/0.1",
    }
    create_data: dict[str, str | bool] = {"workspace": settings.affinda_workspace_id, "wait": "true"}
    if settings.affinda_document_type.strip():
        create_data["documentType"] = settings.affinda_document_type.strip()
    if settings.affinda_collection.strip():
        create_data["collection"] = settings.affinda_collection.strip()

    with open(file_path, "rb") as fp:
        response = _request_with_retry(
            method="POST",
            url=settings.affinda_api_url,
            headers=headers,
            data=create_data,
            files={"file": fp},
            timeout=(10, 90),
        )
    payload = response.json()
    if settings.affinda_debug_raw_json:
        print("[Affinda Debug] raw_json stage=create_document")
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    skills = _flatten_skills(payload)
    if skills:
        return skills

    last_debug_summary = _build_affinda_debug_summary(payload, stage="create_document")
    meta = payload.get("meta", {})
    document_id = (
        payload.get("identifier")
        or payload.get("id")
        or (meta.get("identifier") if isinstance(meta, dict) else None)
        or (meta.get("id") if isinstance(meta, dict) else None)
    )
    if not document_id:
        raise ValueError(
            "Affinda response has no document identifier. "
            f"Check extractor/workspace configuration. Debug: {last_debug_summary}"
        )

    document_url = f"{settings.affinda_api_url.rstrip('/')}/{document_id}"
    for _ in range(4):
        time.sleep(1.0)
        follow_up = _request_with_retry(
            method="GET",
            url=document_url,
            headers=headers,
            timeout=(10, 45),
        )
        follow_payload = follow_up.json()
        if settings.affinda_debug_raw_json:
            print("[Affinda Debug] raw_json stage=get_document")
            print(json.dumps(follow_payload, indent=2, ensure_ascii=True))
        skills = _flatten_skills(follow_payload)
        if skills:
            return skills
        last_debug_summary = _build_affinda_debug_summary(follow_payload, stage="get_document")

    raise ValueError(
        "Affinda parsed zero skills. "
        "If extractor is empty and data is {}, set AFFINDA_DOCUMENT_TYPE or AFFINDA_COLLECTION. "
        f"Debug: {last_debug_summary}"
    )


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
        normalized_skills = _extract_skills_with_affinda(file_path=state.resume_file_path)
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
