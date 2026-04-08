from collections import Counter

from src.graph.state import GraphState, SkillGap


def _normalize_skills(skills_text: str) -> list[str]:
    return [s.strip().lower() for s in skills_text.split(",") if s.strip()]


def rank_node(state: GraphState) -> GraphState:
    market_skills = []
    for posting in state.matched_postings:
        market_skills.extend(_normalize_skills(posting["skills_text"]))

    counts = Counter(market_skills)
    resume_skill_set = set(s.strip().lower() for s in state.parsed_resume_skills)
    total_docs = max(len(state.matched_postings), 1)

    gaps: list[SkillGap] = []
    for skill, freq in counts.most_common(12):
        if skill in resume_skill_set:
            continue
        demand_weight = freq / total_docs
        gap_score = round(demand_weight * 100, 2)
        gaps.append(
            SkillGap(
                skill=skill,
                market_frequency=freq,
                gap_score=gap_score,
                reason=f"Missing in resume and appears in {freq}/{total_docs} recent postings.",
            )
        )

    return state.model_copy(update={"top_skill_gaps": gaps[:8]})
