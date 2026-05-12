"""Apply src/db/schema.sql to the database in DATABASE_URL (creates extensions + tables)."""

from pathlib import Path

from src.config import settings
from src.db.client import get_connection, load_schema


def main() -> None:
    if not settings.database_url.strip():
        raise SystemExit("DATABASE_URL is not set. Copy .env.example to .env and configure it.")
    root = Path(__file__).resolve().parents[1]
    schema_sql = (root / "src" / "db" / "schema.sql").read_text()
    conn = get_connection(settings.database_url)
    try:
        load_schema(conn, schema_sql)
    finally:
        conn.close()
    print("Schema applied: extensions + job_postings (and related objects) are ready.")


if __name__ == "__main__":
    main()
