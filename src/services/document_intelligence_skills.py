"""Resume skill extraction via Azure AI Document Intelligence.

Azure SDK imports are deferred until ``extract_resume_skills_from_file`` runs so the API
can load without ``azure-ai-documentintelligence`` installed (e.g. wrong interpreter).
"""

from __future__ import annotations

# `prebuilt-resume` is not available on Document Intelligence API v4 (2024-11-30) GA;
# use `prebuilt-layout` or `prebuilt-read` and derive skills from OCR text.
DEFAULT_MODEL_ID = "prebuilt-layout"


def extract_resume_skills_from_file(
    *,
    file_path: str,
    endpoint: str,
    api_key: str,
    model_id: str = DEFAULT_MODEL_ID,
    debug_raw_response: bool = False,
) -> list[str]:
    """
    Analyze a resume file with Document Intelligence and return normalized skill strings.

    Default model is ``prebuilt-layout`` (full OCR + structure). Structured ``Skills`` fields
    are used when present (e.g. some custom models); otherwise skills are inferred from text.
    """
    try:
        from src.services._di_resume_extract import extract_resume_skills_impl
    except ModuleNotFoundError as exc:
        raise ValueError(
            "Missing dependency azure-ai-documentintelligence (or azure-core). "
            "Activate the project .venv and run: pip install -e ."
        ) from exc

    mid = (model_id or DEFAULT_MODEL_ID).strip()
    return extract_resume_skills_impl(
        file_path=file_path,
        endpoint=endpoint,
        api_key=api_key,
        model_id=mid,
        debug_raw_response=debug_raw_response,
    )
