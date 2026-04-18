import json
import re
import time

import requests
from requests.exceptions import RequestException


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


def _normalize_skill_candidate(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned or len(cleaned) < 2 or len(cleaned) > 64:
        return ""
    if "@" in cleaned or cleaned.startswith("http://") or cleaned.startswith("https://"):
        return ""
    if re.fullmatch(r"[0-9\W_]+", cleaned):
        return ""
    return cleaned


def _collect_from_untyped_data_fields(payload: dict, out: list[str]) -> None:
    data = payload.get("data")
    if not isinstance(data, dict):
        return

    # Exclude clearly non-skill textual blobs or metadata containers.
    excluded_keys = {
        "rawtext",
        "text",
        "summary",
        "profile",
        "personal",
        "contact",
        "metadata",
        "meta",
        "experience",
        "workexperience",
        "education",
        "projects",
        "publications",
        "references",
    }

    for key, value in data.items():
        key_norm = key.strip().lower()
        if key_norm in excluded_keys:
            continue
        # Keep list/dict style structured fields and ignore long free text fields.
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
    normalized = sorted(
        {
            normalized_value
            for value in candidates
            if value and value.strip()
            for normalized_value in [_normalize_skill_candidate(value)]
            if normalized_value
        }
    )
    return normalized


def _preview_skill_payload(payload: dict) -> None:
    data = payload.get("data", payload)
    samples = []
    paths = [
        ("top.skills", payload.get("skills")),
        ("data.skills", data.get("skills") if isinstance(data, dict) else None),
        ("data.skillSet", data.get("skillSet") if isinstance(data, dict) else None),
        ("data.languages", data.get("languages") if isinstance(data, dict) else None),
        ("data.frameworks", data.get("frameworks") if isinstance(data, dict) else None),
        ("data.developerTools", data.get("developerTools") if isinstance(data, dict) else None),
        ("data.methodologies", data.get("methodologies") if isinstance(data, dict) else None),
        (
            "data.resume.skills",
            (data.get("resume", {}).get("skills") if isinstance(data, dict) and isinstance(data.get("resume"), dict) else None),
        ),
    ]
    for path, value in paths:
        if isinstance(value, list) and value:
            snippet = value[:5]
            samples.append({"path": path, "count": len(value), "sample": snippet})
    if not samples:
        print("[Affinda Debug] skill_payload_preview=no_list_like_skill_paths_found")
        return
    print(f"[Affinda Debug] skill_payload_preview={json.dumps(samples, ensure_ascii=True)}")


def _print_affinda_debug_summary(payload: dict, stage: str) -> None:
    data = payload.get("data")
    top_keys = sorted(payload.keys()) if isinstance(payload, dict) else []
    data_keys = sorted(data.keys()) if isinstance(data, dict) else []
    identifier = payload.get("identifier") or payload.get("id")
    if isinstance(data, dict):
        identifier = identifier or data.get("identifier") or data.get("id")
    preview = {
        "stage": stage,
        "top_keys": top_keys[:30],
        "data_keys": data_keys[:30],
        "identifier": identifier,
        "has_top_skills": isinstance(payload.get("skills"), list),
        "has_data_skills": isinstance(data.get("skills"), list) if isinstance(data, dict) else False,
        "has_data_skillSet": isinstance(data.get("skillSet"), list) if isinstance(data, dict) else False,
    }
    print(f"[Affinda Debug] {json.dumps(preview, ensure_ascii=True)}")


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
        f"stage={stage}, "
        f"identifier={identifier}, "
        f"top_keys={top_keys[:12]}, "
        f"data_keys={data_keys[:12]}, "
        f"has_top_skills={isinstance(payload.get('skills'), list)}, "
        f"has_data_skills={isinstance(data.get('skills'), list) if isinstance(data, dict) else False}, "
        f"has_data_skillSet={isinstance(data.get('skillSet'), list) if isinstance(data, dict) else False}"
    )


def _print_raw_affinda_json(payload: dict, stage: str) -> None:
    print(f"[Affinda Debug] raw_json stage={stage}")
    print(json.dumps(payload, indent=2, ensure_ascii=True))


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
            sleep_s = 1.2 * attempt
            print(f"[Affinda Debug] request retry {attempt}/{max_attempts} after error: {exc}")
            time.sleep(sleep_s)
    raise ValueError(f"Affinda request failed after {max_attempts} attempts: {last_error}")


def extract_skills_with_affinda(
    api_url: str,
    api_key: str,
    workspace_id: str,
    file_path: str,
    document_type: str = "",
    collection: str = "",
    debug_raw_json: bool = False,
) -> list[str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "GapSolverAI/0.1",
    }

    create_data: dict[str, str | bool] = {"workspace": workspace_id, "wait": "true"}
    if document_type.strip():
        create_data["documentType"] = document_type.strip()
    if collection.strip():
        create_data["collection"] = collection.strip()
    print(
        f"[Affinda Debug] create_document_params="
        f"{json.dumps({'workspace': workspace_id, 'wait': True, 'has_document_type': bool(document_type.strip()), 'has_collection': bool(collection.strip())}, ensure_ascii=True)}"
    )

    with open(file_path, "rb") as fp:
        response = _request_with_retry(
            method="POST",
            url=api_url,
            headers=headers,
            data=create_data,
            files={"file": fp},
            timeout=(10, 90),
        )
    payload = response.json()
    if debug_raw_json:
        _print_raw_affinda_json(payload, stage="create_document")
    _print_affinda_debug_summary(payload, stage="create_document")
    _preview_skill_payload(payload)
    last_debug_summary = _build_affinda_debug_summary(payload, stage="create_document")
    skills = _flatten_skills(payload)
    if skills:
        print(f"[Affinda Debug] extracted_skills={json.dumps(skills[:20], ensure_ascii=True)}")
        print(f"[Affinda Debug] extracted_skills_count={len(skills)} stage=create_document")
        return skills

    # Some parses return before extraction is finalized; poll a few times if we got document id.
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
    document_url = f"{api_url.rstrip('/')}/{document_id}"
    for _ in range(4):
        time.sleep(1.0)
        follow_up = _request_with_retry(
            method="GET",
            url=document_url,
            headers=headers,
            timeout=(10, 45),
        )
        follow_payload = follow_up.json()
        if debug_raw_json:
            _print_raw_affinda_json(follow_payload, stage="get_document")
        _print_affinda_debug_summary(follow_payload, stage="get_document")
        _preview_skill_payload(follow_payload)
        last_debug_summary = _build_affinda_debug_summary(follow_payload, stage="get_document")
        skills = _flatten_skills(follow_payload)
        if skills:
            print(f"[Affinda Debug] extracted_skills={json.dumps(skills[:20], ensure_ascii=True)}")
            print(f"[Affinda Debug] extracted_skills_count={len(skills)} stage=get_document")
            return skills
    print("[Affinda Debug] extracted_skills_count=0")
    raise ValueError(
        "Affinda parsed zero skills. "
        "If extractor is empty and data is {}, set AFFINDA_DOCUMENT_TYPE or AFFINDA_COLLECTION. "
        f"Debug: {last_debug_summary}"
    )
