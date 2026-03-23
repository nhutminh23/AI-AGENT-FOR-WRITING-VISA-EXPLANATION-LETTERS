import json
import os
from typing import TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END

from prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

load_dotenv()


class AgentState(TypedDict):
    docx_content: str
    rules: str
    configs: dict


def parse_and_generate(state: AgentState) -> AgentState:
    """Node chính: gọi OpenAI để sinh config objects."""
    model_name = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    llm = ChatOpenAI(
        model=model_name,
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        docx_content=state["docx_content"],
        rules=state["rules"],
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    response = llm.invoke(messages)
    raw = response.content.strip()

    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)

    configs = json.loads(raw)
    return {"docx_content": state["docx_content"], "rules": state["rules"], "configs": configs}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("parse_and_generate", parse_and_generate)
    graph.add_edge(START, "parse_and_generate")
    graph.add_edge("parse_and_generate", END)
    return graph.compile()


def run_agent(docx_content: str, rules: str) -> dict:
    """Entry point: chạy agent và trả về các config objects."""
    app = build_graph()
    result = app.invoke({
        "docx_content": docx_content,
        "rules": rules,
        "configs": {},
    })
    return result["configs"]
