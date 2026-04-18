from src.graph.state import GraphState


def result_to_markdown(result: GraphState) -> str:
    lines = [f"# GapSolver AI Report ({result.target_role})", ""]
    lines.append("## Top Skill Gaps")
    for gap in result.top_skill_gaps:
        lines.append(f"- **{gap.skill}** (score: {gap.gap_score}) - {gap.reason}")
    lines.append("")
    lines.append("## 3-Phase Learning Plan")
    for step in result.learning_plan:
        lines.append(f"### {step.phase}")
        lines.append(f"- Objective: {step.objective}")
        lines.append(f"- Deliverable: {step.deliverable}")
        lines.append("- Tasks:")
        for task in step.tasks:
            lines.append(f"  - {task}")
        lines.append("")
    return "\n".join(lines)
