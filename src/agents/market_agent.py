from collections import Counter

from langchain_openai import OpenAIEmbeddings

from src.config import settings
from src.db.client import get_connection
from src.graph.state import GraphState
from src.graph.state import SkillGap


def _normalize_skills(skills_text: str) -> list[str]:
    return [s.strip().lower() for s in skills_text.split(",") if s.strip()]


def market_agent(state: GraphState) -> GraphState:
    """Retrieves market postings and computes ranked skill gaps."""
    trace = list(state.agent_trace)
    trace.append("market:start")
    state = state.model_copy(update={"agent_trace": trace})

    embedder = OpenAIEmbeddings(
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
        model=settings.azure_openai_embedding_deployment,
    )
    query_text = f"{state.target_role}. Resume skills: {', '.join(state.parsed_resume_skills)}"
    query_embedding = embedder.embed_query(query_text)

    conn = get_connection(settings.database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, company, posted_at, role_family, skills_text, raw_json
                FROM job_postings
                WHERE posted_at >= NOW() - INTERVAL '30 days'
                  AND role_family = %s
                ORDER BY embedding <=> %s::vector
                LIMIT 20
                """,
                (state.target_role, query_embedding),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    matched_postings = [
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

    market_skills = []
    for posting in matched_postings:
        market_skills.extend(_normalize_skills(posting["skills_text"]))

    counts = Counter(market_skills)
    resume_skill_set = set(s.strip().lower() for s in state.parsed_resume_skills)
    total_docs = max(len(matched_postings), 1)

    top_skill_gaps: list[SkillGap] = []
    for skill, freq in counts.most_common(12):
        if skill in resume_skill_set:
            continue
        demand_weight = freq / total_docs
        gap_score = round(demand_weight * 100, 2)
        top_skill_gaps.append(
            SkillGap(
                skill=skill,
                market_frequency=freq,
                gap_score=gap_score,
                reason=f"Missing in resume and appears in {freq}/{total_docs} recent postings.",
            )
        )

    ranked_state = state.model_copy(
        update={
            "query_embedding": query_embedding,
            "matched_postings": matched_postings,
            "top_skill_gaps": top_skill_gaps[:8],
        }
    )
    trace = list(ranked_state.agent_trace)
    trace.append("market:retrieved_and_ranked")
    return ranked_state.model_copy(update={"agent_trace": trace})
