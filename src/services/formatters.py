from src.graph.state import GraphState


def _gap_bar(score: float, width: int = 10) -> str:
    filled = max(0, min(width, round(score / 10)))
    return "█" * filled + "░" * (width - filled)


def result_to_markdown(result: GraphState) -> str:
    sorted_gaps = sorted(result.top_skill_gaps, key=lambda x: x.gap_score, reverse=True)
    top_three = sorted_gaps[:3]
    top_three_text = ", ".join(g.skill for g in top_three) if top_three else "N/A"
    priority_map = {gap.skill: f"P{idx}" for idx, gap in enumerate(top_three, start=1)}

    lines = [f"# GapSolver AI Report ({result.target_role})", ""]
    lines.append("## 1) Executive Summary")
    lines.append(f"- Target role: `{result.target_role}`")
    lines.append(f"- Analyzed matched postings: `{len(result.matched_postings)}`")
    lines.append(f"- Top priority gaps: {top_three_text}")
    lines.append("")

    lines.append("## 2) Skill Gap Matrix")
    lines.append("Priority | Skill | Gap Score | Market Frequency | Why It Matters")
    lines.append("--- | --- | --- | --- | ---")
    for gap in sorted_gaps:
        priority = priority_map.get(gap.skill, "-")
        lines.append(
            f"**{priority}** | {gap.skill} | {_gap_bar(gap.gap_score)} {gap.gap_score} | {gap.market_frequency} mentions | {gap.reason}"
        )
    lines.append("")

    lines.append("## 3) Learning Plan by Phase")
    for idx, step in enumerate(result.learning_plan, start=1):
        lines.append(f"### Phase {idx}")
        lines.append(f"- Original stage: {step.phase}")
        lines.append(f"- Objective: {step.objective}")
        lines.append(f"- Deliverable: {step.deliverable}")
        lines.append("- Tasks:")
        for task in step.tasks:
            lines.append(f"  - {task}")
        lines.append("")

    lines.append("## 4) Resource Map by Skill")
    for skill in sorted(result.recommended_resources.keys()):
        resources = result.recommended_resources[skill]
        lines.append(f"### {skill}")
        if not resources:
            lines.append("- No resources found.")
            continue
        for item in resources:
            title = item.get("title", "resource")
            url = item.get("url", "")
            source = item.get("source", "unknown")
            lines.append(f"- [{title}]({url}) ({source})")
        lines.append("")

    lines.append("## 5) Risks & Assumptions")
    lines.append("- Uses recent 30-day postings as market window.")
    lines.append("- Retrieval quality depends on current ingestion sample size.")
    lines.append("- Skill gaps are ranked from inferred demand frequency, not direct interview outcomes.")
    return "\n".join(lines)
