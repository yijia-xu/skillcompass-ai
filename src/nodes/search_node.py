from langchain_openai import OpenAIEmbeddings

from src.config import settings
from src.db.client import get_connection
from src.graph.state import GraphState


def search_node(state: GraphState) -> GraphState:
    embedder = OpenAIEmbeddings(api_key=settings.openai_api_key, model=settings.embedding_model)
    query_text = f"{state.target_role}. Resume skills: {', '.join(state.parsed_resume_skills)}"
    query_embedding = embedder.embed_query(query_text)

    conn = get_connection(settings.database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, company, posted_at, role_family, skills_text, raw_json
                FROM job_postings
                WHERE posted_at >= NOW() - INTERVAL '90 days'
                  AND role_family = %s
                ORDER BY embedding <=> %s::vector
                LIMIT 20
                """,
                (state.target_role, query_embedding),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    matched = [
        {
            "id": str(row[0]),
            "title": row[1],
            "company": row[2],
            "posted_at": str(row[3]),
            "role_family": row[4],
            "skills_text": row[5],
            "raw_json": row[6],
        }
        for row in rows
    ]
    return state.model_copy(update={"query_embedding": query_embedding, "matched_postings": matched})
