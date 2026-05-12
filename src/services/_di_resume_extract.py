"""Azure Document Intelligence implementation (import only when DI is used)."""

from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.ai.documentintelligence.models import DocumentField
from azure.ai.documentintelligence.models import DocumentFieldType
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

from src.services.skill_normalization import normalize_skills
from src.services.skill_normalization import split_skill_phrases

_PRIMARY_SKILL_FIELD_KEYS = frozenset({"Skills", "Skill"})


def _normalize_di_endpoint(endpoint: str) -> str:
    return endpoint.strip().rstrip("/") + "/"


def _skills_from_flat_text(text: str, limit: int = 60) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.\-/]{1,30}", text)
    raw_candidates: list[str] = []
    for token in tokens:
        if any(ch.isdigit() for ch in token) or any(ch in token for ch in "+#./-") or len(token) >= 4:
            raw_candidates.append(token)
    return normalize_skills(raw_candidates, limit=limit)


def _full_text_from_analyze_result(result: AnalyzeResult) -> str:
    text = (result.content or "").strip()
    if text:
        return text
    paragraphs = result.paragraphs or []
    parts = [p.content.strip() for p in paragraphs if p.content and p.content.strip()]
    return "\n".join(parts)


def _strings_from_document_field(field: DocumentField | None) -> list[str]:
    if field is None:
        return []
    out: list[str] = []
    ft = field.type
    if ft == DocumentFieldType.STRING:
        if field.value_string:
            out.append(field.value_string.strip())
        elif field.content:
            out.append(field.content.strip())
    elif ft == DocumentFieldType.ARRAY:
        for item in field.value_array or []:
            out.extend(_strings_from_document_field(item))
    elif ft == DocumentFieldType.OBJECT:
        for sub in (field.value_object or {}).values():
            out.extend(_strings_from_document_field(sub))
    else:
        if field.content and field.content.strip():
            out.append(field.content.strip())
    return [s for s in out if s]


def _collect_skill_candidates(result: AnalyzeResult) -> list[str]:
    candidates: list[str] = []
    for doc in result.documents or []:
        fields = doc.fields or {}
        for key in _PRIMARY_SKILL_FIELD_KEYS:
            if key in fields:
                candidates.extend(_strings_from_document_field(fields[key]))
        for fname, fld in fields.items():
            if fname in _PRIMARY_SKILL_FIELD_KEYS:
                continue
            if "skill" in fname.lower():
                candidates.extend(_strings_from_document_field(fld))
    return candidates


def _flatten_skills_from_di(result: AnalyzeResult) -> list[str]:
    raw = _collect_skill_candidates(result)
    if raw:
        expanded: list[str] = []
        for value in raw:
            expanded.extend(split_skill_phrases(value))
        normalized = normalize_skills(expanded, limit=60)
        if normalized:
            return normalized

    flat = _full_text_from_analyze_result(result)
    if flat:
        return _skills_from_flat_text(flat, limit=60)
    return []


def extract_resume_skills_impl(
    *,
    file_path: str,
    endpoint: str,
    api_key: str,
    model_id: str,
    debug_raw_response: bool = False,
) -> list[str]:
    mid = model_id.strip()
    ep = _normalize_di_endpoint(endpoint)
    client = DocumentIntelligenceClient(endpoint=ep, credential=AzureKeyCredential(api_key.strip()))
    body = BytesIO(Path(file_path).read_bytes())
    try:
        poller = client.begin_analyze_document(mid, body=body)
        result = poller.result()
    except HttpResponseError as exc:
        detail = getattr(exc, "message", None) or str(exc)
        code = getattr(exc, "status_code", "?")
        raise ValueError(f"Document Intelligence request failed ({code}): {detail}") from exc

    if debug_raw_response:
        if hasattr(result, "as_dict"):
            print("[DocumentIntelligence Debug] analyze_result=")
            print(json.dumps(result.as_dict(), indent=2, ensure_ascii=True, default=str))
        else:
            print("[DocumentIntelligence Debug] analyze_result=", result)

    return _flatten_skills_from_di(result)
