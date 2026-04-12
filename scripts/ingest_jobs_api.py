import argparse
import hashlib
import json
import re
import ssl
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import certifi
from langchain_openai import OpenAIEmbeddings
from pgvector.psycopg import register_vector

from src.config import settings
from src.db.client import (
    get_connection,
    insert_job_postings,
    load_schema,
    prune_old_job_postings,
    truncate_job_postings,
)

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/ca/search"
DATA_ENGINEERING_KEYWORDS = [
    "python",
    "sql",
    "airflow",
    "dbt",
    "spark",
    "kafka",
    "snowflake",
    "bigquery",
    "redshift",
    "databricks",
    "etl",
    "elt",
    "data modeling",
    "data warehouse",
    "postgresql",
    "aws",
    "azure",
    "gcp",
]

ROLE_KEYWORDS = {
    "data_engineer": [
        "data engineer",
        "analytics engineer",
        "data platform",
        "etl engineer",
        "big data",
    ],
    "ml_engineer": ["machine learning engineer", "ml engineer", "mlops"],
    "backend_engineer": ["backend engineer", "software engineer backend"],
}


def fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "GapSolverAI/0.1"})
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(req, timeout=30, context=ssl_context) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_adzuna_jobs(
    app_id: str,
    app_key: str,
    query: str,
    max_pages: int = 3,
    results_per_page: int = 50,
) -> list[dict]:
    jobs: list[dict] = []
    # Adzuna pages are 1-indexed
    for page in range(1, max_pages + 1):
        query = urlencode(
            {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": results_per_page,
                "what": query,
                "content-type": "application/json",
            }
        )
        url = f"{ADZUNA_BASE}/{page}?{query}"
        payload = fetch_json(url)
        page_jobs = payload.get("results", [])
        if not page_jobs:
            break
        jobs.extend(page_jobs)
    return jobs



def html_to_text(html: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", html)
    squashed = re.sub(r"\s+", " ", no_tags).strip()
    return squashed


def infer_role_family(title: str, description: str) -> str | None:
    haystack = f"{title} {description}".lower()
    for role_family, patterns in ROLE_KEYWORDS.items():
        if any(pattern in haystack for pattern in patterns):
            return role_family
    return None


def extract_skills(title: str, description: str, tags: list[str]) -> list[str]:
    haystack = f"{title} {description} {' '.join(tags)}".lower()
    found = [keyword for keyword in DATA_ENGINEERING_KEYWORDS if keyword in haystack]
    return sorted(set(found))


def parse_posted_at(raw_job: dict) -> datetime | None:
    created = raw_job.get("created")
    if isinstance(created, str):
        try:
            return datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None
    return None


def build_dedupe_key(url: str, title: str, company: str, posted_at: datetime, description: str) -> str:
    normalized_url = urlparse(url).path or url
    text_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()[:16]
    return f"{normalized_url}|{title.lower()}|{company.lower()}|{posted_at.date()}|{text_hash}"


def normalize_jobs(
    raw_jobs: list[dict], query: str, retention_days: int = 30
) -> tuple[list[dict], dict[str, int]]:
    dedupe = set()
    normalized_rows = []
    stats = {
        "missing_required_fields": 0,
        "older_than_retention": 0,
        "non_matching_query": 0,
        "low_quality_content": 0,
        "deduplicated": 0,
        "kept": 0,
    }
    cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)

    for raw in raw_jobs:
        title = str(raw.get("title", "")).strip()
        company = str((raw.get("company") or {}).get("display_name", "")).strip()
        url = str(raw.get("redirect_url", "")).strip()
        location = str((raw.get("location") or {}).get("display_name", "")).strip().lower()
        category_label = str((raw.get("category") or {}).get("label", "")).strip().lower()
        tags = [category_label] if category_label else []
        description = html_to_text(str(raw.get("description", "")))
        posted_at_dt = parse_posted_at(raw)

        if not (title and company and url and posted_at_dt):
            stats["missing_required_fields"] += 1
            continue
        if posted_at_dt < cutoff:
            stats["older_than_retention"] += 1
            continue

        haystack = f"{title} {description}".lower()
        if query.lower() not in haystack:
            stats["non_matching_query"] += 1
            continue
        role_family = infer_role_family(title, description) or "other"

        skills = extract_skills(title, description, tags)
        # Keep quality guardrails, but avoid over-filtering early-stage ingestion.
        if len(description) < 80 or len(skills) < 1:
            stats["low_quality_content"] += 1
            continue

        dedupe_key = build_dedupe_key(url, title, company, posted_at_dt, description)
        if dedupe_key in dedupe:
            stats["deduplicated"] += 1
            continue
        dedupe.add(dedupe_key)

        normalized_rows.append(
            {
                "source": "adzuna_ca",
                "title": title,
                "company": company,
                "posted_at": posted_at_dt.date().isoformat(),
                "role_family": role_family,
                "skills": skills,
                "skills_text": ", ".join(skills),
                "description": description,
                "url": url,
                "location": location,
                "raw_json": raw,
            }
        )
        stats["kept"] += 1
    return normalized_rows, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and ingest real JD data from Adzuna Canada API")
    parser.add_argument("--query", default="data engineer", help="Keyword query to search on Adzuna")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--results-per-page", type=int, default=50)
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--keep-old", action="store_true", help="Skip pruning old postings")
    args = parser.parse_args()

    if (
        not settings.database_url
        or not settings.azure_openai_api_key
        or not settings.azure_openai_endpoint
        or not settings.adzuna_app_id
        or not settings.adzuna_app_key
    ):
        raise ValueError(
            "Missing DATABASE_URL, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, ADZUNA_APP_ID, or ADZUNA_APP_KEY."
        )

    root = Path(__file__).resolve().parents[1]
    schema_path = root / "src" / "db" / "schema.sql"
    schema_sql = schema_path.read_text()

    raw_jobs = fetch_adzuna_jobs(
        app_id=settings.adzuna_app_id,
        app_key=settings.adzuna_app_key,
        query=args.query,
        max_pages=args.max_pages,
        results_per_page=args.results_per_page,
    )
    normalized, stats = normalize_jobs(raw_jobs, query=args.query, retention_days=args.retention_days)
    if not normalized:
        print("No valid jobs after dedupe/filtering.")
        print(f"Filter stats: {stats}")
        return

    embeddings_client = OpenAIEmbeddings(
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
        model=settings.azure_openai_embedding_deployment,
    )
    docs = [f"{j['title']} at {j['company']}. {j['description']} Skills: {j['skills_text']}" for j in normalized]
    vectors = embeddings_client.embed_documents(docs)

    rows = []
    for job, vector in zip(normalized, vectors):
        stable_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{job['source']}::{job['url']}::{job['posted_at']}::{job['title']}::{job['company']}",
        )
        rows.append(
            {
                "id": stable_id,
                "title": job["title"],
                "company": job["company"],
                "posted_at": job["posted_at"],
                "role_family": job["role_family"],
                "skills_text": job["skills_text"],
                "embedding": vector,
                "raw_json": {
                    "source": job["source"],
                    "url": job["url"],
                    "description": job["description"],
                    "location": job["location"],
                    "skills": job["skills"],
                    "raw": job["raw_json"],
                },
            }
        )

    conn = get_connection(settings.database_url)
    try:
        load_schema(conn, schema_sql)
        register_vector(conn)
        truncate_job_postings(conn)
        print("Reset job_postings table before ingestion.")
        if not args.keep_old:
            deleted = prune_old_job_postings(conn, retention_days=args.retention_days)
            print(f"Pruned {deleted} postings older than {args.retention_days} days.")
        insert_job_postings(conn, rows)
    finally:
        conn.close()

    print(
        f"Fetched {len(raw_jobs)} raw jobs, kept {len(normalized)} after dedupe/filter, upserted {len(rows)} rows."
    )
    print(f"Filter stats: {stats}")


if __name__ == "__main__":
    main()
