from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from agents import (
    classify_files,
    domain_agent,
    ingest_files,
    letter_writer,
    risk_explanation_finder,
)
from state import GraphState


def build_graph() -> StateGraph:
    builder = StateGraph(GraphState)

    builder.add_node("ingest", ingest_files)
    builder.add_node("classify", classify_files)
    builder.add_node("personal", domain_agent("personal"))
    builder.add_node("travel_history", domain_agent("travel_history"))
    builder.add_node("employment", domain_agent("employment"))
    builder.add_node("financial", domain_agent("financial"))
    builder.add_node("purpose", domain_agent("purpose"))
    builder.add_node("risk", risk_explanation_finder)
    builder.add_node("writer", letter_writer)

    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", "classify")
    builder.add_edge("classify", "personal")
    builder.add_edge("personal", "travel_history")
    builder.add_edge("travel_history", "employment")
    builder.add_edge("employment", "financial")
    builder.add_edge("financial", "purpose")
    builder.add_edge("purpose", "risk")
    builder.add_edge("risk", "writer")
    builder.add_edge("writer", END)

    return builder.compile()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default=None)
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    model = args.model or os.getenv("OPENAI_MODEL", "gpt-5-mini")
    llm = ChatOpenAI(model=model, temperature=0)

    graph = build_graph()
    state: GraphState = {
        "input_dir": args.input_dir,
        "output_path": args.output,
        "model": model,
        "llm": llm,
    }
    result = graph.invoke(state)

    output_path = args.output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result.get("letter_full", ""))

    print(f"Saved letter to: {output_path}")


if __name__ == "__main__":
    main()
