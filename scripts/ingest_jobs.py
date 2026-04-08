import json
import uuid
from pathlib import Path

from langchain_openai import OpenAIEmbeddings

from src.config import settings
from src.db.client import get_connection, insert_job_postings, load_schema


def main() -> None:
    if not settings.database_url or not settings.openai_api_key:
        raise ValueError("Missing DATABASE_URL or OPENAI_API_KEY in environment.")

    root = Path(__file__).resolve().parents[1]
    schema_path = root / "src" / "db" / "schema.sql"
    data_path = root / "data" / "sample_job_postings.json"

    schema_sql = schema_path.read_text()
    postings = json.loads(data_path.read_text())

    embeddings_client = OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )

    docs = [f"{p['title']} at {p['company']}. Skills: {p['skills_text']}" for p in postings]
    vectors = embeddings_client.embed_documents(docs)

    rows = []
    for posting, vector in zip(postings, vectors):
        rows.append(
            {
                "id": uuid.uuid5(uuid.NAMESPACE_URL, f"{posting['company']}::{posting['title']}::{posting['posted_at']}"),
                "title": posting["title"],
                "company": posting["company"],
                "posted_at": posting["posted_at"],
                "role_family": posting["role_family"],
                "skills_text": posting["skills_text"],
                "embedding": vector,
                "raw_json": posting,
            }
        )

    conn = get_connection(settings.database_url)
    try:
        load_schema(conn, schema_sql)
        insert_job_postings(conn, rows)
    finally:
        conn.close()

    print(f"Ingested {len(rows)} postings into job_postings.")


if __name__ == "__main__":
    main()
