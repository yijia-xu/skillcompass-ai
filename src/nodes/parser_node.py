import json

from langchain_openai import ChatOpenAI

from src.config import settings
from src.graph.state import GraphState


def _extract_json_object(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(content[start : end + 1])
        raise


def parser_node(state: GraphState) -> GraphState:
    prompt = (
        "Extract atomic technical skills from the resume text. "
        "Return strict JSON in the form {\"skills\": [\"...\"]}. "
        "Use lowercase normalized names."
    )
    llm = ChatOpenAI(
        api_key=settings.azure_openai_api_key,
        base_url=settings.azure_openai_endpoint,
        model=settings.azure_openai_chat_deployment,
        temperature=0,
    )
    response = llm.invoke(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": state.resume_text},
        ]
    )

    parsed = _extract_json_object(response.content)
    return state.model_copy(update={"parsed_resume_skills": parsed.get("skills", [])})
