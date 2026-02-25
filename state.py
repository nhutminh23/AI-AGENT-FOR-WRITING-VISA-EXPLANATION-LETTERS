from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class FileItem(TypedDict):
    path: str
    name: str
    text: str
    domain: str


class GraphState(TypedDict, total=False):
    input_dir: str
    output_path: str
    model: str
    llm: Any
    files: List[FileItem]
    grouped: Dict[str, List[str]]
    extracted: Dict[str, Any]
    risk_points: List[Dict[str, Any]]
    contradictions: Dict[str, List[str]]
    summary_profile: str
    letter_vi: str
    letter_en: str
    letter_full: str
