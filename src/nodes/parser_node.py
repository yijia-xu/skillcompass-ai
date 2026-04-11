import json

from langchain_openai import AzureChatOpenAI

from src.config import settings
from src.graph.state import GraphState


def parser_node(state: GraphState) -> GraphState:
    prompt = (
        "Extract atomic technical skills from the resume text. "
        "Return strict JSON in the form {\"skills\": [\"...\"]}. "
        "Use lowercase normalized names."
    )
    llm = AzureChatOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
        azure_deployment=settings.azure_openai_chat_deployment,
        temperature=0,
    )
    response = llm.invoke(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": state.resume_text},
        ]
    )

    parsed = json.loads(response.content)
    return state.model_copy(update={"parsed_resume_skills": parsed.get("skills", [])})
