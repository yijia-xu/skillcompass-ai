from collections import Counter
import hashlib
import json
import re
import ssl
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import certifi
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings

from src.config import settings
from src.db.client import delete_job_postings_by_role_family, get_connection, insert_job_postings
from src.graph.state import GraphState
from src.graph.state import SkillGap

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/ca/search"
FALLBACK_STOPWORDS = {
    "and", "the", "for", "with", "from", "this", "that", "will", "into", "using", "are",
    "our", "team", "work", "about", "have", "has", "job", "join",
}
MINIMAL_NOISE_WORDS = {
    "engineer", "engineering", "developer", "development", "software", "data", "role",
    "position", "company", "required", "preferred", "experience", "years", "it",
}
JD_SKILL_EXTRACTION_PROMPT = (
    "You extract hard technical skills from job descriptions for role-gap analysis.\n"
    "Return STRICT JSON array of strings only.\n"
    "Include: programming languages, frameworks/libraries, cloud/data platforms, tools, protocols, methods.\n"
    "Exclude: role titles, generic hiring words, soft skills, responsibilities, company/team words."
)
SKILL_CANDIDATE_FILTER_PROMPT = (
    "You are validating candidate terms for a technical skill-gap matrix.\n"
    "Keep only concrete technical skills, tools, frameworks, cloud/data platforms, protocols, or programming languages.\n"
    "Reject generic words, hiring language, company words, and vague terms.\n"
    "Return STRICT JSON array of the kept terms, preserving original lowercase strings only."
)


def _normalize_skills(skills_text: str) -> list[str]:
    return [s.strip().lower() for s in skills_text.split(",") if s.strip()]


def _normalize_role_family(target_role: str) -> str:
    return "_".join(target_role.strip().lower().split())


def _html_to_text(html: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", no_tags).strip()


def _parse_posted_at(raw_job: dict) -> datetime | None:
    created = raw_job.get("created")
    if isinstance(created, str):
        try:
            return datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None
    return None


def _extract_market_skills(title: str, description: str, tags: list[str], query: str) -> list[str]:
    text = f"{title} {description} {' '.join(tags)}".lower()
    tokens = re.findall(r"[a-z][a-z0-9\+\#\.\-]{1,}", text)
    query_terms = {term for term in re.split(r"\s+", query.lower().strip()) if term}
    role_noise = query_terms | {t.rstrip("s") for t in query_terms}
    extracted = set()
    for token in tokens:
        if token in FALLBACK_STOPWORDS or token in MINIMAL_NOISE_WORDS:
            continue
        if token in role_noise:
            continue
        if len(token) < 3:
            continue
        # Keep likely technical tokens; drop plain language fragments.
        if not any(ch.isdigit() for ch in token) and all(ch.isalpha() for ch in token) and len(token) < 4:
            continue
        extracted.add(token)
    return sorted(extracted)[:30]


def _extract_json_array(content: str) -> list:
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end != -1 and end > start:
        parsed = json.loads(content[start : end + 1])
        if isinstance(parsed, list):
            return parsed
    return []


def _extract_market_skills_with_llm(title: str, description: str, query: str) -> list[str]:
    llm = ChatOpenAI(
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
        model=settings.azure_openai_chat_deployment,
        temperature=0,
    )
    payload = {"target_role": query, "title": title, "description": description}
    response = llm.invoke(
        [
            {"role": "system", "content": JD_SKILL_EXTRACTION_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
        ]
    )
    raw = _extract_json_array(response.content if isinstance(response.content, str) else str(response.content))
    return _normalize_extracted_skills(raw)


def _normalize_extracted_skills(raw_items: list) -> list[str]:
    cleaned: list[str] = []
    seen = set()
    for item in raw_items:
        if not isinstance(item, str):
            continue
        skill = item.strip().lower()
        if not skill:
            continue
        if len(skill) < 2 or len(skill) > 64:
            continue
        if skill in FALLBACK_STOPWORDS or skill in MINIMAL_NOISE_WORDS:
            continue
        if skill in seen:
            continue
        seen.add(skill)
        cleaned.append(skill)
    return cleaned[:30]


def _filter_skill_candidates_with_llm(candidates: list[str], target_role: str) -> set[str]:
    if not candidates:
        return set()
    llm = ChatOpenAI(
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
        model=settings.azure_openai_chat_deployment,
        temperature=0,
    )
    payload = {"target_role": target_role, "candidates": candidates}
    response = llm.invoke(
        [
            {"role": "system", "content": SKILL_CANDIDATE_FILTER_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
        ]
    )
    kept = _extract_json_array(response.content if isinstance(response.content, str) else str(response.content))
    return {item.strip().lower() for item in kept if isinstance(item, str) and item.strip()}


def _fetch_json(url: str) -> dict:
    req = Request(url, headers={"User-Agent": "GapSolverAI/0.1"})
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(req, timeout=30, context=ssl_context) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_adzuna_jobs(query: str, max_pages: int = 3, results_per_page: int = 40) -> list[dict]:
    jobs: list[dict] = []
    for page in range(1, max_pages + 1):
        query_string = urlencode(
            {
                "app_id": settings.adzuna_app_id,
                "app_key": settings.adzuna_app_key,
                "results_per_page": results_per_page,
                "what": query,
                "content-type": "application/json",
            }
        )
        url = f"{ADZUNA_BASE}/{page}?{query_string}"
        payload = _fetch_json(url)
        page_jobs = payload.get("results", [])
        if not page_jobs:
            break
        jobs.extend(page_jobs)
    return jobs


def _build_dedupe_key(url: str, title: str, company: str, posted_at: datetime, description: str) -> str:
    normalized_url = urlparse(url).path or url
    text_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()[:16]
    return f"{normalized_url}|{title.lower()}|{company.lower()}|{posted_at.date()}|{text_hash}"


def _refresh_market_data_for_role(target_role: str, retention_days: int = 30) -> int:
    role_query = target_role.replace("_", " ").strip()
    role_family = _normalize_role_family(target_role)
    raw_jobs = _fetch_adzuna_jobs(role_query)
    cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)

    dedupe = set()
    normalized = []
    for raw in raw_jobs:
        title = str(raw.get("title", "")).strip()
        company = str((raw.get("company") or {}).get("display_name", "")).strip()
        url = str(raw.get("redirect_url", "")).strip()
        category_label = str((raw.get("category") or {}).get("label", "")).strip().lower()
        tags = [category_label] if category_label else []
        description = _html_to_text(str(raw.get("description", "")))
        posted_at_dt = _parse_posted_at(raw)

        if not (title and company and url and posted_at_dt):
            continue
        if posted_at_dt < cutoff:
            continue
        if role_query.lower() not in f"{title} {description}".lower():
            continue

        try:
            skills = _extract_market_skills_with_llm(title, description, query=role_query)
        except Exception:
            skills = _extract_market_skills(title, description, tags, query=role_query)
        if not skills:
            skills = _extract_market_skills(title, description, tags, query=role_query)
        if len(description) < 80 or len(skills) < 1:
            continue

        dedupe_key = _build_dedupe_key(url, title, company, posted_at_dt, description)
        if dedupe_key in dedupe:
            continue
        dedupe.add(dedupe_key)
        normalized.append(
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
                "raw_json": raw,
            }
        )

    embedder = OpenAIEmbeddings(
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
        model=settings.azure_openai_embedding_deployment,
    )
    docs = [f"{j['title']} at {j['company']}. {j['description']} Skills: {j['skills_text']}" for j in normalized]
    vectors = embedder.embed_documents(docs) if docs else []

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
                    "skills": job["skills"],
                    "raw": job["raw_json"],
                },
            }
        )

    conn = get_connection(settings.database_url)
    try:
        delete_job_postings_by_role_family(conn, role_family=role_family)
        if rows:
            insert_job_postings(conn, rows)
    finally:
        conn.close()
    return len(rows)


def market_agent(state: GraphState) -> GraphState:
    """Retrieves market postings and computes ranked skill gaps."""
    trace = list(state.agent_trace)
    trace.append("market:start")
    refreshed_count = _refresh_market_data_for_role(state.target_role)
    trace.append(f"market:refreshed_role_postings:{refreshed_count}")
    state = state.model_copy(update={"agent_trace": trace})

    embedder = OpenAIEmbeddings(
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
        model=settings.azure_openai_embedding_deployment,
    )
    query_text = f"{state.target_role}. Resume skills: {', '.join(state.parsed_resume_skills)}"
    query_embedding = embedder.embed_query(query_text)

    role_family = _normalize_role_family(state.target_role)
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
                (role_family, query_embedding),
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
    candidate_terms = [skill for skill, _ in counts.most_common(40)]
    try:
        llm_kept = _filter_skill_candidates_with_llm(candidate_terms, target_role=state.target_role)
    except Exception:
        llm_kept = set()
    if llm_kept:
        allowed_terms = llm_kept
    else:
        # Fallback when filtering model fails.
        allowed_terms = {s for s in candidate_terms if s not in FALLBACK_STOPWORDS and s not in MINIMAL_NOISE_WORDS}

    top_skill_gaps: list[SkillGap] = []
    for skill, freq in counts.most_common(12):
        if skill not in allowed_terms:
            continue
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
    if not matched_postings:
        trace.append(f"market:no_postings_for_role:{role_family}")
    trace.append("market:retrieved_and_ranked")
    return ranked_state.model_copy(update={"agent_trace": trace})
