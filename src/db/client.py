import json
from typing import Sequence

import psycopg
from pgvector.psycopg import register_vector


def get_connection(database_url: str) -> psycopg.Connection:
    conn = psycopg.connect(database_url)
    try:
        register_vector(conn)
    except psycopg.ProgrammingError:
        # First-run databases may not have CREATE EXTENSION vector yet.
        pass
    return conn


def load_schema(conn: psycopg.Connection, schema_sql: str) -> None:
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()


def insert_job_postings(conn: psycopg.Connection, rows: Sequence[dict]) -> None:
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                """
                INSERT INTO job_postings
                (id, title, company, posted_at, role_family, skills_text, embedding, raw_json)
                VALUES (%(id)s, %(title)s, %(company)s, %(posted_at)s, %(role_family)s, %(skills_text)s, %(embedding)s, %(raw_json)s)
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title,
                    company = EXCLUDED.company,
                    posted_at = EXCLUDED.posted_at,
                    role_family = EXCLUDED.role_family,
                    skills_text = EXCLUDED.skills_text,
                    embedding = EXCLUDED.embedding,
                    raw_json = EXCLUDED.raw_json
                """,
                {
                    **row,
                    "raw_json": json.dumps(row["raw_json"]),
                },
            )
    conn.commit()


def prune_old_job_postings(conn: psycopg.Connection, retention_days: int = 30) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM job_postings
            WHERE posted_at < CURRENT_DATE - (%s::text || ' days')::interval
            """,
            (retention_days,),
        )
        deleted = cur.rowcount
    conn.commit()
    return deleted


def truncate_job_postings(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE job_postings")
    conn.commit()
