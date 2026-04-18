import json
import re

from langchain_openai import ChatOpenAI

from src.config import settings
from src.graph.state import GraphState
from src.graph.state import LearningStep
from src.services.resource_discovery import discover_learning_resources


def _extract_json_array(content: str) -> list[dict]:
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

    raise ValueError("PlanningAgent expected a JSON array response from the model.")


def _normalize_tasks(tasks: list) -> list[str]:
    normalized: list[str] = []
    for item in tasks:
        if isinstance(item, str):
            normalized.append(item)
        elif isinstance(item, dict):
            task_text = item.get("task") or item.get("name") or item.get("description")
            source = item.get("resource") or item.get("source")
            if task_text and source:
                normalized.append(f"{task_text} ({source})")
            elif task_text:
                normalized.append(task_text)
            else:
                normalized.append(json.dumps(item, ensure_ascii=True))
        else:
            normalized.append(str(item))
    return normalized


def _task_has_resource(task: str) -> bool:
    has_url = bool(re.search(r"https?://", task))
    has_md_link = bool(re.search(r"\[[^\]]+\]\([^)]+\)", task))
    return has_url or has_md_link


def planning_agent(state: GraphState) -> GraphState:
    """Builds staged learning plans from ranked gaps."""
    trace = list(state.agent_trace)
    trace.append("planning:start")
    state = state.model_copy(update={"agent_trace": trace})

    if not state.top_skill_gaps:
        raise ValueError("PlanningAgent requires non-empty top_skill_gaps.")

    gap_skills = [gap.skill for gap in state.top_skill_gaps]
    resource_map = discover_learning_resources(gap_skills, github_token=settings.github_token)
    trace = list(state.agent_trace)
    trace.append("planning:resources_discovered")
    state = state.model_copy(update={"agent_trace": trace})

    llm = ChatOpenAI(
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
        model=settings.azure_openai_chat_deployment,
        temperature=0.2,
    )
    prompt = (
        "You are a career learning planner. Produce a 3-phase learning plan as strict JSON list with keys: "
        "phase, objective, tasks, deliverable. Phases must be Foundation, Core, Project. "
        "Use gaps, target role, and learning resources as input. "
        "Tasks must include concrete resource links in markdown format. "
        f"strict_resources={settings.strict_resources}. "
        "If strict_resources is true, every task must contain at least one URL or markdown link."
    )
    payload = {
        "target_role": state.target_role,
        "top_skill_gaps": [g.model_dump() for g in state.top_skill_gaps],
        "resource_map": resource_map,
    }
    response = llm.invoke(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload)},
        ]
    )
    raw_steps = _extract_json_array(response.content)
    learning_plan = []
    for step in raw_steps:
        step = dict(step)
        normalized_tasks = _normalize_tasks(step.get("tasks", []))
        if settings.strict_resources:
            normalized_tasks = [task for task in normalized_tasks if _task_has_resource(task)]
        if not normalized_tasks:
            continue
        step["tasks"] = normalized_tasks
        learning_plan.append(LearningStep(**step))
    if settings.strict_resources and len(learning_plan) < 3:
        raise ValueError(
            "PlanningAgent strict mode requires at least 3 phases with resource-backed tasks."
        )
    if not settings.strict_resources and len(learning_plan) < 3:
        raise ValueError("PlanningAgent expected at least 3 learning phases.")

    planned_state = state.model_copy(
        update={"learning_plan": learning_plan, "recommended_resources": resource_map}
    )
    trace = list(planned_state.agent_trace)
    trace.append("planning:plan_generated")
    return planned_state.model_copy(update={"agent_trace": trace})
