from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request
from langchain_openai import ChatOpenAI

import database as db
from core.agents import build_summary_profile, ingest_files
from core.file_utils import read_docx, read_pdf, read_text_file
from core.helpers import cache_dir, get_text_model, get_vision_model
from core.letter_v2 import (
    extract_style_profile,
    generate_letter_v2,
    get_default_style_profile,
)
from core.state import GraphState


letter_v2_bp = Blueprint("letter_v2", __name__)

REQUIRED_WRITER_MODEL = "gpt-5-mini"


def _load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _parse_project_id(raw: Any) -> Optional[int]:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def _resolve_writer_model_or_error() -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Enforce writer model policy for OLA2 cost control.

    Policy:
    - Writer tasks (style profiling, letter generation, quality check) must use gpt-5-mini.
    - The model value comes from OPENAI_MODEL in .env (TEXT_MODEL is supported as alias).
    """
    writer_model = (get_text_model() or "").strip()
    if not writer_model:
        return None, {
            "error": "missing_text_model",
            "message": "Writer model is empty. Please set OPENAI_MODEL=gpt-5-mini in .env (TEXT_MODEL is supported as alias).",
        }
    if writer_model != REQUIRED_WRITER_MODEL:
        return None, {
            "error": "writer_model_not_allowed",
            "message": (
                "OLA2 writer is cost-locked to gpt-5-mini. "
                "Please set OPENAI_MODEL=gpt-5-mini in .env (TEXT_MODEL is supported as alias)."
            ),
            "current_text_model": writer_model,
            "required_text_model": REQUIRED_WRITER_MODEL,
        }
    return writer_model, None


def _read_uploaded_sample_text() -> Tuple[str, str]:
    sample_text = (request.form.get("sample_text") or "").strip()
    sample_file = request.files.get("sample_file")

    if sample_text:
        return sample_text, "text"

    if not sample_file or not sample_file.filename:
        return "", ""

    ext = os.path.splitext(sample_file.filename)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        temp_path = tmp.name
        sample_file.save(temp_path)

    try:
        if ext in {".txt", ".md"}:
            return read_text_file(temp_path), sample_file.filename
        if ext == ".docx":
            return read_docx(temp_path), sample_file.filename
        if ext == ".pdf":
            return read_pdf(temp_path), sample_file.filename
        # Fallback for unknown text-like files
        with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(), sample_file.filename
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


def _build_fallback_evidence(files_data: list[dict]) -> str:
    lines: list[str] = []
    for item in files_data[:12]:
        name = item.get("name", "")
        text = (item.get("text", "") or "").strip().replace("\r", "")
        top = "\n".join(text.split("\n")[:10]).strip()
        tail = "\n".join(text.split("\n")[-4:]).strip() if text else ""
        snippet = "\n...\n".join(part for part in [top, tail] if part).strip()
        if snippet:
            lines.append(f"- file {name}:\n{snippet}")
    if not lines:
        return ""
    return "\n\nRAW EVIDENCE SNAPSHOT:\n" + "\n\n".join(lines)


def _trim_for_prompt(text: str, max_chars: int = 12000) -> str:
    raw = (text or "").strip()
    if not raw or len(raw) <= max_chars:
        return raw
    head = raw[: int(max_chars * 0.65)]
    tail = raw[-int(max_chars * 0.30):]
    return f"{head}\n\n...[TRUNCATED]...\n\n{tail}"


def _guess_legacy_letter_from_files(files_data: list[dict]) -> Tuple[str, str]:
    name_keywords = [
        "thu giai trinh",
        "thư giải trình",
        "giai trinh",
        "explanation letter",
        "letter of explanation",
        "statement of purpose",
        "sop",
    ]
    content_keywords = [
        "dear visa officer",
        "letter of explanation",
        "statement of purpose",
        "purpose of visit",
        "travel arrangements",
        "financial capacity",
        "strong ties",
        "travel history",
        "yours sincerely",
        "subclass 600",
    ]

    best_score = -1
    best_text = ""
    best_name = ""

    for item in files_data:
        name = (item.get("name", "") or "").strip()
        text = (item.get("text", "") or "").strip()
        if not text or len(text) < 300:
            continue

        lname = name.lower()
        ltext = text.lower()

        score = 0
        for kw in name_keywords:
            if kw in lname:
                score += 6

        keyword_hits = 0
        for kw in content_keywords:
            if kw in ltext:
                keyword_hits += 1
        score += keyword_hits * 2

        if "dear visa officer" in ltext and "yours sincerely" in ltext:
            score += 4

        if len(text) > 1200:
            score += 1

        if score > best_score:
            best_score = score
            best_text = text
            best_name = name

    if best_score < 4:
        return "", ""
    return best_text, best_name


def _prepare_summary_profile(text_llm: ChatOpenAI, files_data: list[dict]) -> str:
    summary_state: GraphState = {
        "llm": text_llm,
        "files": files_data,
    }
    summary_state = build_summary_profile(summary_state)
    summary = (summary_state.get("summary_profile") or "").strip()

    # If filename prefixes are missing, domain summary can become too empty.
    zero_count = summary.count("có 0 file")
    if zero_count >= 5:
        summary = (summary + _build_fallback_evidence(files_data)).strip()

    return summary


@letter_v2_bp.post("/api/letter-v2/style-profile")
def letter_v2_style_profile():
    writer_model, model_error = _resolve_writer_model_or_error()
    if model_error:
        return jsonify(model_error), 400

    sample_text = ""
    sample_source = ""

    if request.is_json:
        payload = request.get_json(force=True) or {}
        sample_text = (payload.get("sample_text") or "").strip()
        sample_source = "text"
    else:
        sample_text, sample_source = _read_uploaded_sample_text()

    if not sample_text:
        return jsonify({"error": "missing_sample_text"}), 400

    llm = ChatOpenAI(model=writer_model, temperature=0)
    style_profile = extract_style_profile(llm, sample_text)

    return jsonify(
        {
            "status": "ok",
            "sample_source": sample_source,
            "writer_model": writer_model,
            "sample_text_length": len(sample_text),
            "style_profile": style_profile,
        }
    )


@letter_v2_bp.post("/api/letter-v2/generate")
def letter_v2_generate():
    writer_model, model_error = _resolve_writer_model_or_error()
    if model_error:
        return jsonify(model_error), 400

    payload = request.get_json(force=True) or {}

    input_dir = payload.get("input_dir", "booking/input")
    output_path = payload.get("output", os.path.join("output", "letter_v2.txt"))
    writer_context = (payload.get("writer_context") or "").strip()
    force = bool(payload.get("force", False))

    sample_text = (payload.get("sample_text") or "").strip()
    sample_style_profile = payload.get("sample_style_profile") or {}
    if not isinstance(sample_style_profile, dict):
        sample_style_profile = {}

    if not os.path.isdir(input_dir):
        return jsonify({"error": "input_dir_not_found", "input_dir": input_dir}), 404

    text_llm = ChatOpenAI(model=writer_model, temperature=0)
    vision_llm = ChatOpenAI(model=get_vision_model(), temperature=0)

    cdir = cache_dir(output_path)
    v2_state_path = os.path.join(cdir, "letter_v2_state.json")
    cached_state = _load_json(v2_state_path)

    files_data = []
    if not force:
        cached_files = cached_state.get("files_data")
        if isinstance(cached_files, list):
            files_data = cached_files

    if not files_data:
        ingest_state: GraphState = {
            "input_dir": input_dir,
            "llm": vision_llm,
        }
        ingest_state = ingest_files(ingest_state)
        files_data = ingest_state.get("files", [])

    summary_profile = _prepare_summary_profile(text_llm, files_data)

    legacy_letter_reference = sample_text
    legacy_letter_source = ""
    if legacy_letter_reference:
        legacy_letter_source = "provided_sample_text"

    if not legacy_letter_reference:
        cached_legacy = cached_state.get("legacy_letter_reference")
        if isinstance(cached_legacy, str) and cached_legacy.strip():
            legacy_letter_reference = cached_legacy.strip()
            legacy_letter_source = "cached_legacy_letter"

    if not legacy_letter_reference:
        detected_text, detected_name = _guess_legacy_letter_from_files(files_data)
        if detected_text:
            legacy_letter_reference = detected_text
            legacy_letter_source = f"auto_detected:{detected_name}"

    style_profile_source = ""
    if not sample_style_profile:
        style_sample = sample_text or legacy_letter_reference
        if style_sample:
            sample_style_profile = extract_style_profile(text_llm, style_sample)
            style_profile_source = "from_sample_or_legacy"
        else:
            sample_style_profile = get_default_style_profile()
            style_profile_source = "default_style_profile"
    else:
        style_profile_source = "provided_style_profile"

    legacy_letter_reference = _trim_for_prompt(legacy_letter_reference, max_chars=10000)

    generation = generate_letter_v2(
        llm=text_llm,
        summary_profile=summary_profile,
        sample_style_profile=sample_style_profile,
        legacy_letter_reference=legacy_letter_reference,
        writer_context=writer_context,
    )
    letter = generation.get("letter", "")
    quality_report = generation.get("quality_report", {})

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(letter)

    state_to_save = {
        "input_dir": input_dir,
        "output_path": output_path,
        "files_data": files_data,
        "summary_profile": summary_profile,
        "sample_style_profile": sample_style_profile,
        "style_profile_source": style_profile_source,
        "legacy_letter_reference": legacy_letter_reference,
        "legacy_letter_source": legacy_letter_source,
        "writer_context": writer_context,
        "letter": letter,
        "quality_report": quality_report,
    }
    _save_json(v2_state_path, state_to_save)

    project_id = _parse_project_id(payload.get("project_id"))
    if project_id:
        db.save_letter_state(
            project_id,
            files_data=files_data,
            summary_profile=summary_profile,
            writer_context=writer_context,
            letter_content=letter,
            step_ingest=True,
            step_summary=True,
            step_writer=True,
        )

    return jsonify(
        {
            "status": "ok",
            "output_path": output_path,
            "summary_profile": summary_profile,
            "style_profile": sample_style_profile,
            "style_profile_source": style_profile_source,
            "legacy_letter_source": legacy_letter_source,
            "quality_report": quality_report,
            "letter": letter,
            "writer_model": writer_model,
            "file_count": len(files_data),
        }
    )


@letter_v2_bp.get("/api/letter-v2/latest")
def letter_v2_latest():
    output_path = request.args.get("output", os.path.join("output", "letter_v2.txt"))
    cdir = cache_dir(output_path)
    v2_state_path = os.path.join(cdir, "letter_v2_state.json")
    state = _load_json(v2_state_path)
    return jsonify(
        {
            "summary_profile": state.get("summary_profile", ""),
            "style_profile": state.get("sample_style_profile", {}),
            "style_profile_source": state.get("style_profile_source", ""),
            "legacy_letter_source": state.get("legacy_letter_source", ""),
            "quality_report": state.get("quality_report", {}),
            "letter": state.get("letter", ""),
            "writer_context": state.get("writer_context", ""),
        }
    )
