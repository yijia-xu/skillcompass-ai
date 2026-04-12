import json

from langchain_openai import ChatOpenAI

from src.config import settings
from src.graph.state import GraphState
from src.graph.state import LearningStep


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


def planning_agent(state: GraphState) -> GraphState:
    """Builds staged learning plans from ranked gaps."""
    trace = list(state.agent_trace)
    trace.append("planning:start")
    state = state.model_copy(update={"agent_trace": trace})

    if not state.top_skill_gaps:
        raise ValueError("PlanningAgent requires non-empty top_skill_gaps.")

    llm = ChatOpenAI(
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
        model=settings.azure_openai_chat_deployment,
        temperature=0.2,
    )
    prompt = (
        "You are a career learning planner. Produce a 3-phase learning plan as strict JSON list with keys: "
        "phase, objective, tasks, deliverable. Phases must be Foundation, Core, Project. "
        "Use gaps and target role as input."
    )
    payload = {
        "target_role": state.target_role,
        "top_skill_gaps": [g.model_dump() for g in state.top_skill_gaps],
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
        step["tasks"] = _normalize_tasks(step.get("tasks", []))
        learning_plan.append(LearningStep(**step))
    if len(learning_plan) < 3:
        raise ValueError("PlanningAgent expected at least 3 learning phases.")

    planned_state = state.model_copy(update={"learning_plan": learning_plan})
    trace = list(planned_state.agent_trace)
    trace.append("planning:plan_generated")
    return planned_state.model_copy(update={"agent_trace": trace})
