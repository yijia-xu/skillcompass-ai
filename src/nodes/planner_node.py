import json

from langchain_openai import AzureChatOpenAI

from src.config import settings
from src.graph.state import GraphState, LearningStep


def planner_node(state: GraphState) -> GraphState:
    llm = AzureChatOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
        azure_deployment=settings.azure_openai_chat_deployment,
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
    raw_steps = json.loads(response.content)
    steps = [LearningStep(**s) for s in raw_steps]
    return state.model_copy(update={"learning_plan": steps})
