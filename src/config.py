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
    affinda_api_key: str = os.getenv("AFFINDA_API_KEY", "")
    affinda_api_url: str = os.getenv("AFFINDA_API_URL", "https://api.affinda.com/v3/documents")
    affinda_workspace_id: str = os.getenv("AFFINDA_WORKSPACE_ID", "")
    affinda_document_type: str = os.getenv("AFFINDA_DOCUMENT_TYPE", "")
    affinda_collection: str = os.getenv("AFFINDA_COLLECTION", "")
    affinda_debug_raw_json: bool = _env_bool("AFFINDA_DEBUG_RAW_JSON", default=False)
    adzuna_app_id: str = os.getenv("ADZUNA_APP_ID", "")
    adzuna_app_key: str = os.getenv("ADZUNA_APP_KEY", "")
    market_max_pages: int = _env_int("MARKET_MAX_PAGES", 8)
    market_results_per_page: int = _env_int("MARKET_RESULTS_PER_PAGE", 50)


settings = Settings()
