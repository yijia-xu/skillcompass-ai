from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "")
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_embedding_deployment: str = os.getenv(
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
    )
    azure_openai_chat_deployment: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
    strict_resources: bool = _env_bool("STRICT_RESOURCES", default=False)
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    azure_document_intelligence_endpoint: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    azure_document_intelligence_key: str = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
    azure_document_intelligence_debug_raw_response: bool = _env_bool(
        "AZURE_DOCUMENT_INTELLIGENCE_DEBUG_RAW_RESPONSE", default=False
    )
    # v4 GA has no prebuilt-resume; use prebuilt-layout + text heuristics by default.
    azure_document_intelligence_model_id: str = os.getenv(
        "AZURE_DOCUMENT_INTELLIGENCE_MODEL_ID", "prebuilt-layout"
    )
    adzuna_app_id: str = os.getenv("ADZUNA_APP_ID", "")
    adzuna_app_key: str = os.getenv("ADZUNA_APP_KEY", "")
    market_max_pages: int = _env_int("MARKET_MAX_PAGES", 8)
    market_results_per_page: int = _env_int("MARKET_RESULTS_PER_PAGE", 50)


settings = Settings()
