from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.agents import (
    build_summary_profile,
    detect_domain,
    extract_text_with_openai,
    ingest_files,
    itinerary_writer,
    letter_writer,
)
from classifier.agent import classify_files_in_folder
from pypdf import PdfReader, PdfWriter
from core.state import GraphState
import database as db


load_dotenv()

app = Flask(__name__, static_folder="frontend", static_url_path="")


def _list_input_files(input_dir: str) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for root, _, filenames in os.walk(input_dir):
        for fname in filenames:
            path = os.path.join(root, fname)
            rel_path = os.path.relpath(path, input_dir).replace("\\", "/")
            items.append(
                {
                    "name": fname,
                    "rel_path": rel_path,
                    "path": path,
                    "domain": detect_domain(fname),
                }
            )
    return items


STEP_ORDER = [
    "ingest",
    "summary",
    "writer",
]


def _cache_dir(output_path: str) -> str:
    return os.path.join(os.path.dirname(output_path), "cache")


def _state_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "state.json")


def _step_marker_path(cache_dir: str, step: str) -> str:
    return os.path.join(cache_dir, f"step_{step}.json")


def _reset_downstream_steps(cache_dir: str, step: str) -> None:
    if step not in STEP_ORDER:
        return
    idx = STEP_ORDER.index(step)
    downstream = STEP_ORDER[idx + 1 :]
    for s in downstream:
        marker = _step_marker_path(cache_dir, s)
        if os.path.exists(marker):
            os.remove(marker)

    # Clear derived caches so downstream status/data stay consistent.
    if "summary" in downstream:
        path = os.path.join(cache_dir, "summary_profile.txt")
        if os.path.exists(path):
            os.remove(path)


def _load_state(cache_dir: str) -> Dict[str, Any]:
    path = _state_path(cache_dir)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(cache_dir: str, state: GraphState) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    serializable = {
        "input_dir": state.get("input_dir"),
        "output_path": state.get("output_path"),
        "model": state.get("model"),
        "files": state.get("files", []),
        "grouped": state.get("grouped", {}),
        "summary_profile": state.get("summary_profile", ""),
        "writer_context": state.get("writer_context", ""),
        "letter_full": state.get("letter_full", ""),
    }
    with open(_state_path(cache_dir), "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def _save_step_output(cache_dir: str, step: str, state: GraphState) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    if step == "ingest":
        with open(os.path.join(cache_dir, "ingest.json"), "w", encoding="utf-8") as f:
            json.dump(state.get("files", []), f, ensure_ascii=False, indent=2)
    elif step == "summary":
        with open(
            os.path.join(cache_dir, "summary_profile.txt"), "w", encoding="utf-8"
        ) as f:
            f.write(state.get("summary_profile", ""))
    elif step == "writer":
        output_path = state.get("output_path") or os.path.join("output", "letter.txt")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(state.get("letter_full", ""))

    with open(_step_marker_path(cache_dir, step), "w", encoding="utf-8") as f:
        json.dump({"done": True}, f)


def _is_step_done(cache_dir: str, step: str) -> bool:
    return os.path.exists(_step_marker_path(cache_dir, step))


def _resolve_input_file_path(input_dir: str, file_ref: str) -> Optional[str]:
    if not file_ref:
        return None

    input_root = os.path.abspath(input_dir)
    candidate = os.path.abspath(os.path.normpath(os.path.join(input_dir, file_ref)))
    if candidate.startswith(input_root) and os.path.exists(candidate):
        return candidate

    for root, _, filenames in os.walk(input_dir):
        for fname in filenames:
            if fname == file_ref:
                return os.path.join(root, fname)
    return None


def _upsert_file_record(files: List[Dict[str, Any]], new_file: Dict[str, Any]) -> List[Dict[str, Any]]:
    updated: List[Dict[str, Any]] = []
    replaced = False
    for item in files:
        if item.get("path") == new_file.get("path"):
            updated.append(new_file)
            replaced = True
        else:
            updated.append(item)
    if not replaced:
        updated.append(new_file)
    return updated


def _missing_prereq_step(cache_dir: str, step: str) -> Optional[str]:
    if step not in STEP_ORDER:
        return None
    idx = STEP_ORDER.index(step)
    for prev in STEP_ORDER[:idx]:
        if not _is_step_done(cache_dir, prev):
            return prev
    return None


def _run_single_step(step: str, state: GraphState) -> GraphState:
    if step == "ingest":
        return ingest_files(state)
    if step == "summary":
        return build_summary_profile(state)
    if step == "writer":
        return letter_writer(state)
    return state


@app.get("/")
def index():
    return send_from_directory("frontend", "index.html")


# ==================== PROJECT ENDPOINTS ====================

@app.post("/api/projects")
def create_project():
    payload = request.get_json(force=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Project name is required"}), 400
    project = db.create_project(name)
    return jsonify(project)


@app.get("/api/projects")
def list_projects():
    projects = db.list_projects()
    return jsonify({"projects": projects})


@app.get("/api/projects/<int:project_id>")
def get_project(project_id):
    project = db.get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(project)


@app.put("/api/projects/<int:project_id>")
def update_project(project_id):
    payload = request.get_json(force=True) or {}
    name = payload.get("name")
    updates = {}
    if name:
        updates["name"] = name.strip()
    project = db.update_project(project_id, **updates)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(project)


@app.delete("/api/projects/<int:project_id>")
def delete_project(project_id):
    ok = db.delete_project(project_id)
    if not ok:
        return jsonify({"error": "Project not found"}), 404
    return jsonify({"status": "deleted"})


@app.get("/api/files")
def list_files():
    input_dir = request.args.get("input_dir", "input")
    files = _list_input_files(input_dir)
    return jsonify({"input_dir": input_dir, "files": files})


@app.get("/api/classifier/files")
def list_classifier_files():
    input_dir = request.args.get("input_dir", os.path.join("phanloai", "input"))
    if not os.path.isdir(input_dir):
        return jsonify({"input_dir": input_dir, "files": [], "exists": False})
    items = _list_input_files(input_dir)
    return jsonify(
        {
            "input_dir": input_dir,
            "exists": True,
            "files": items,
        }
    )


@app.post("/api/classifier/run")
def run_classifier():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    output_dir = payload.get("output_dir", os.path.join("phanloai", "output"))
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404

    result = classify_files_in_folder(input_dir=input_dir, output_dir=output_dir, model=model)
    return jsonify({"status": "done", **result})


def _safe_join(base: str, rel_path: str) -> str:
    base_abs = os.path.abspath(base)
    candidate = os.path.abspath(os.path.join(base, rel_path))
    if not candidate.startswith(base_abs):
        raise ValueError("Invalid path")
    return candidate


@app.post("/api/classifier/split_manual")
def split_manual():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    output_dir = payload.get("output_dir", os.path.join("phanloai", "output"))
    source = (payload.get("source") or "").strip()
    segments = payload.get("segments") or []

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404
    os.makedirs(output_dir, exist_ok=True)
    if not source:
        return jsonify({"error": "missing_source"}), 400
    if not isinstance(segments, list) or not segments:
        return jsonify({"error": "missing_segments"}), 400

    try:
        src_path = _safe_join(input_dir, source)
    except ValueError:
        return jsonify({"error": "invalid_source"}), 400

    if not os.path.exists(src_path):
        return jsonify({"error": "source_not_found"}), 404
    if os.path.splitext(src_path)[1].lower() != ".pdf":
        return jsonify({"error": "source_not_pdf"}), 400

    try:
        reader = PdfReader(src_path)
    except Exception as exc:
        return jsonify({"error": "read_pdf_failed", "detail": str(exc)}), 500

    total_pages = len(reader.pages)
    created: list[dict[str, Any]] = []

    def _sanitize_name(value: str, fallback: str) -> str:
        text = (value or "").strip()
        text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or fallback

    def _pick_unique(dest_dir: str, stem: str, ext: str) -> str:
        candidate = os.path.join(dest_dir, f"{stem}{ext}")
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
            idx += 1
        return candidate

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        name = _sanitize_name(seg.get("output_name") or "", "DOCUMENT")
        try:
            s = int(seg.get("start_page"))
            e = int(seg.get("end_page"))
        except Exception:
            continue
        if s < 1 or e < 1 or s > total_pages or e > total_pages:
            continue
        if s > e:
            s, e = e, s
        writer = PdfWriter()
        for i in range(s - 1, e):
            writer.add_page(reader.pages[i])
        out_path = _pick_unique(output_dir, name, ".pdf")
        try:
            with open(out_path, "wb") as f:
                writer.write(f)
        except Exception:
            continue
        created.append(
            {
                "output_name": name,
                "start_page": s,
                "end_page": e,
                "to": os.path.relpath(out_path, output_dir).replace("\\", "/"),
            }
        )

    return jsonify(
        {
            "status": "done",
            "input_dir": input_dir,
            "output_dir": output_dir,
            "source": source,
            "total_pages": total_pages,
            "segments": created,
        }
    )


@app.route("/api/pdf/merge", methods=["POST"])
def merge_pdf():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("pdf", "input"))
    output_dir = payload.get("output_dir", os.path.join("pdf", "output"))
    files = payload.get("files") or []
    output_name = (payload.get("output_name") or "").strip()

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404
    os.makedirs(output_dir, exist_ok=True)

    if not isinstance(files, list) or not files:
        return jsonify({"error": "missing_files"}), 400
    if not output_name:
        return jsonify({"error": "missing_output_name"}), 400

    # Reuse helpers
    def _sanitize_name(value: str, fallback: str) -> str:
        text = (value or "").strip()
        text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text or fallback

    def _pick_unique(dest_dir: str, stem: str, ext: str) -> str:
        candidate = os.path.join(dest_dir, f"{stem}{ext}")
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
            idx += 1
        return candidate

    writer = PdfWriter()
    total_pages = 0
    used_files: list[str] = []

    for rel in files:
        try:
            src_path = _safe_join(input_dir, rel)
        except ValueError:
            continue
        if not os.path.exists(src_path):
            continue
        if os.path.splitext(src_path)[1].lower() != ".pdf":
            continue
        try:
            reader = PdfReader(src_path)
        except Exception:
            continue
        for page in reader.pages:
            writer.add_page(page)
            total_pages += 1
        used_files.append(os.path.relpath(src_path, input_dir).replace("\\", "/"))

    if not used_files:
        return jsonify({"error": "no_valid_pdfs"}), 400

    safe_name = _sanitize_name(output_name, "MERGED")
    out_path = _pick_unique(output_dir, safe_name, ".pdf")
    try:
        with open(out_path, "wb") as f:
            writer.write(f)
    except Exception as exc:
        return jsonify({"error": "write_failed", "detail": str(exc)}), 500

    return jsonify(
        {
            "status": "done",
            "input_dir": input_dir,
            "output_dir": output_dir,
            "files": used_files,
            "file_count": len(used_files),
            "total_pages": total_pages,
            "output_file": os.path.relpath(out_path, output_dir).replace("\\", "/"),
        }
    )


@app.route("/api/pdf/rename", methods=["POST"])
def rename_pdf():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("pdf", "input"))
    source = (payload.get("source") or "").strip()
    prefix = (payload.get("prefix") or "").strip()
    doc_type = (payload.get("doc_type") or "").strip()

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404
    if not source:
        return jsonify({"error": "missing_source"}), 400
    if not prefix or not doc_type:
        return jsonify({"error": "missing_name_parts"}), 400

    try:
        src_path = _safe_join(input_dir, source)
    except ValueError:
        return jsonify({"error": "invalid_source"}), 400

    if not os.path.exists(src_path):
        return jsonify({"error": "source_not_found"}), 404
    if os.path.splitext(src_path)[1].lower() != ".pdf":
        return jsonify({"error": "source_not_pdf"}), 400

    def _sanitize_part(value: str) -> str:
        text = (value or "").strip()
        text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _pick_unique_name(dest_dir: str, stem: str, ext: str) -> str:
        candidate = os.path.join(dest_dir, f"{stem}{ext}")
        idx = 1
        while os.path.exists(candidate):
            candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
            idx += 1
        return candidate

    prefix_clean = _sanitize_part(prefix)
    doc_type_clean = _sanitize_part(doc_type)
    if not prefix_clean or not doc_type_clean:
        return jsonify({"error": "invalid_name"}), 400

    stem = f"{prefix_clean} - {doc_type_clean}"
    dest_dir = os.path.dirname(src_path)
    dest_path = _pick_unique_name(dest_dir, stem, ".pdf")

    try:
        os.rename(src_path, dest_path)
    except Exception as exc:
        return jsonify({"error": "rename_failed", "detail": str(exc)}), 500

    return jsonify(
        {
            "status": "done",
            "input_dir": input_dir,
            "source": os.path.relpath(src_path, input_dir).replace("\\", "/"),
            "new_name": os.path.basename(dest_path),
            "new_rel_path": os.path.relpath(dest_path, input_dir).replace("\\", "/"),
        }
    )


@app.route("/api/pdf/rename_suggest_name", methods=["POST"])
def pdf_rename_suggest_name():
    payload = request.get_json(force=True) or {}
    input_text = (payload.get("input_text") or "").strip()
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")

    if not input_text:
        return jsonify({"error": "missing_input_text"}), 400

    llm = ChatOpenAI(model=model, temperature=0)

    system = SystemMessage(
        content=(
            "Bạn là trợ lý đặt tên tài liệu cho hồ sơ visa. "
            "Nhiệm vụ: chuyển mô tả tiếng Việt về loại giấy tờ sang 1 cụm tiếng Anh rất ngắn gọn "
            "(tối đa khoảng 3–4 từ), ALL CAPS, phù hợp đặt tên file. "
            "Ví dụ: 'giấy khai sinh' -> 'BIRTH CERT'; 'giấy kết hôn' -> 'MARRIAGE CERT'. "
            "Chỉ trả về đúng cụm tiếng Anh, không giải thích thêm."
        )
    )
    human = HumanMessage(
        content=f"Người dùng nhập: \"{input_text}\".\nHãy trả về cụm tiếng Anh ngắn gọn để đặt tên file."
    )

    try:
        result = llm.invoke([system, human])
    except Exception as exc:
        return jsonify({"error": "llm_error", "detail": str(exc)}), 500

    suggested = (getattr(result, "content", "") or "").strip().upper()
    suggested = re.sub(r"[^A-Z0-9\s]", " ", suggested)
    suggested = re.sub(r"\s+", " ", suggested).strip()

    if not suggested:
        return jsonify({"error": "empty_suggestion"}), 500

    return jsonify({"suggested_name": suggested})


@app.get("/api/steps")
def list_steps():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        state = db.get_latest_letter_state(project_id)
        if state:
            steps = [
                {"name": "ingest", "done": state["step_ingest"]},
                {"name": "summary", "done": state["step_summary"]},
                {"name": "writer", "done": state["step_writer"]},
            ]
        else:
            steps = [{"name": s, "done": False} for s in STEP_ORDER]
        return jsonify({"steps": steps})
    # Fallback to file-based
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    steps = [
        {"name": step, "done": _is_step_done(cache_dir, step)} for step in STEP_ORDER
    ]
    return jsonify({"steps": steps})


@app.get("/api/summary")
def get_summary():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        state = db.get_latest_letter_state(project_id)
        summary = state["summary_profile"] if state else ""
        return jsonify({"summary_profile": summary})
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    summary = state_cache.get("summary_profile", "")
    if not summary:
        path = os.path.join(cache_dir, "summary_profile.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                summary = f.read()
    return jsonify({"summary_profile": summary})


@app.get("/api/writer_context")
def get_writer_context():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        state = db.get_latest_letter_state(project_id)
        return jsonify({"writer_context": state["writer_context"] if state else ""})
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    return jsonify({"writer_context": state_cache.get("writer_context", "")})


@app.get("/api/ingest_stream")
def ingest_stream():
    input_dir = request.args.get("input_dir", "input")
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    model = request.args.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
    force = request.args.get("force", "0") == "1"
    project_id = request.args.get("project_id", type=int)

    llm = ChatOpenAI(model=model, temperature=0)
    cache_dir = _cache_dir(output_path)
    files: List[Dict[str, str]] = []

    if force:
        _reset_downstream_steps(cache_dir, "ingest")

    def sse(data: Dict) -> str:
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    def generate():
        for root, _, filenames in os.walk(input_dir):
            for fname in filenames:
                path = os.path.join(root, fname)
                yield sse({"type": "progress", "message": f"Đang trích xuất: {fname}"})
                text = extract_text_with_openai(llm, path)
                files.append(
                    {
                        "path": path,
                        "name": fname,
                        "text": text,
                        "domain": detect_domain(fname),
                    }
                )
        state: GraphState = {
            "input_dir": input_dir,
            "output_path": output_path,
            "model": model,
            "llm": llm,
            "files": files,
        }
        _save_state(cache_dir, state)
        _save_step_output(cache_dir, "ingest", state)

        # Save to DB if project_id provided
        if project_id:
            db.save_letter_state(
                project_id,
                files_data=files,
                step_ingest=True,
            )

        yield sse({"type": "done"})

    return Response(generate(), mimetype="text/event-stream")


@app.get("/api/itinerary/latest")
def get_itinerary_latest():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        it = db.get_latest_itinerary(project_id)
        return jsonify({"itinerary": it["html_content"] if it else ""})
    output_path = request.args.get("output", os.path.join("output", "itinerary.html"))
    cache_dir = _cache_dir(output_path)
    path = os.path.join(cache_dir, "itinerary.html")
    if not os.path.exists(path):
        return jsonify({"itinerary": ""})
    with open(path, "r", encoding="utf-8") as f:
        return jsonify({"itinerary": f.read()})


@app.get("/api/itinerary/context/latest")
def get_itinerary_context_latest():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        ctx = db.get_latest_itinerary_context(project_id)
        if ctx:
            summary = _build_itinerary_summary_from_form(ctx.get("form_data", {}))
            return jsonify({"summary_profile": summary, "form_data": ctx.get("form_data", {})})
        return jsonify({"summary_profile": "", "form_data": {}})
    output_path = request.args.get("output", os.path.join("output", "itinerary.html"))
    cache_dir = _cache_dir(output_path)
    summary_path = os.path.join(cache_dir, "itinerary_summary.txt")
    meta_path = os.path.join(cache_dir, "itinerary_summary_meta.json")

    summary = ""
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = f.read()

    meta: Dict[str, Any] = {"form_data": {}}
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

    return jsonify(
        {
            "summary_profile": summary,
            "form_data": meta.get("form_data", {}),
        }
    )


def _build_itinerary_summary_from_form(form_data: Dict[str, Any]) -> str:
    participants = (form_data.get("participants") or "").strip()
    travel_purpose = (form_data.get("travel_purpose") or "").strip()
    start_date = (form_data.get("travel_start_date") or "").strip()
    end_date = (form_data.get("travel_end_date") or "").strip()
    has_any_value = any(
        [
            participants,
            travel_purpose,
            start_date,
            end_date,
        ]
    )
    if not has_any_value:
        return ""

    lines: List[str] = ["Core itinerary inputs:"]
    if participants:
        lines.append(f"- Participant(s): {participants}")
    if start_date and end_date:
        lines.append(f"- Travel period: From {start_date} to {end_date}")
    elif start_date:
        lines.append(f"- travel_start_date: {start_date}")
    elif end_date:
        lines.append(f"- travel_end_date: {end_date}")
    if travel_purpose:
        lines.append(f"- Purpose of travel: {travel_purpose}")

    return "\n".join(lines).strip()


@app.route("/api/itinerary/context/save", methods=["POST"])
def save_itinerary_context():
    payload = request.get_json(force=True) or {}
    output_path = payload.get("output", os.path.join("output", "itinerary.html"))
    form_data = payload.get("form_data") or {}
    project_id = payload.get("project_id")

    if not isinstance(form_data, dict):
        return jsonify({"error": "invalid_form_data"}), 400

    summary_profile = _build_itinerary_summary_from_form(form_data)
    if not summary_profile:
        return jsonify({"error": "missing_context"}), 400

    # Save to file cache
    cache_dir = _cache_dir(output_path)
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "itinerary_summary.txt"), "w", encoding="utf-8") as f:
        f.write(summary_profile)
    with open(os.path.join(cache_dir, "itinerary_summary_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"form_data": form_data}, f, ensure_ascii=False, indent=2)

    # Save to DB
    if project_id:
        db.save_itinerary_context(int(project_id), {"form_data": form_data})

    return jsonify(
        {
            "status": "done",
            "summary_profile": summary_profile,
            "form_data": form_data,
        }
    )


@app.post("/api/run_step")
def run_step():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    step = payload.get("step")
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
    force = bool(payload.get("force", False))
    writer_context = (payload.get("writer_context") or "").strip()
    project_id = payload.get("project_id", type=int) if isinstance(payload.get("project_id"), int) else None

    if step not in STEP_ORDER:
        return jsonify({"error": "invalid_step"}), 400

    cache_dir = _cache_dir(output_path)
    missing = _missing_prereq_step(cache_dir, step)
    if missing and not force:
        return jsonify({"error": "missing_prerequisite", "missing": missing}), 400

    if _is_step_done(cache_dir, step) and not force:
        return jsonify({"status": "cached", "step": step})

    if force:
        _reset_downstream_steps(cache_dir, step)

    state_cache = _load_state(cache_dir)
    llm = ChatOpenAI(model=model, temperature=0)
    state: GraphState = {
        "input_dir": input_dir,
        "output_path": output_path,
        "model": model,
        "llm": llm,
        "files": state_cache.get("files", []),
        "grouped": state_cache.get("grouped", {}),
        "summary_profile": state_cache.get("summary_profile", ""),
        "writer_context": writer_context or state_cache.get("writer_context", ""),
        "letter_full": state_cache.get("letter_full", ""),
    }

    state = _run_single_step(step, state)
    _save_state(cache_dir, state)
    _save_step_output(cache_dir, step, state)

    # Save to DB if project_id provided
    if project_id:
        db_updates = {f"step_{step}": True}
        if step == "summary":
            db_updates["summary_profile"] = state.get("summary_profile", "")
        if step == "writer":
            db_updates["writer_context"] = state.get("writer_context", "")
            db_updates["letter_content"] = state.get("letter_full", "")
        db.save_letter_state(project_id, **db_updates)

    response: Dict[str, Any] = {"status": "done", "step": step}
    if step == "summary":
        response["summary_profile"] = state.get("summary_profile", "")
    if step == "writer":
        response["letter"] = state.get("letter_full", "")
        response["output_path"] = output_path

    return jsonify(response)


@app.post("/api/run_all")
def run_all():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
    force = bool(payload.get("force", False))
    writer_context = (payload.get("writer_context") or "").strip()
    project_id = payload.get("project_id", type=int) if isinstance(payload.get("project_id"), int) else None

    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    llm = ChatOpenAI(model=model, temperature=0)
    state: GraphState = {
        "input_dir": input_dir,
        "output_path": output_path,
        "model": model,
        "llm": llm,
        "files": state_cache.get("files", []),
        "grouped": state_cache.get("grouped", {}),
        "summary_profile": state_cache.get("summary_profile", ""),
        "writer_context": writer_context or state_cache.get("writer_context", ""),
        "letter_full": state_cache.get("letter_full", ""),
    }

    for step in STEP_ORDER:
        if _is_step_done(cache_dir, step) and not force:
            continue
        state = _run_single_step(step, state)
        _save_state(cache_dir, state)
        _save_step_output(cache_dir, step, state)

    # Save final state to DB
    if project_id:
        db.save_letter_state(
            project_id,
            files_data=state.get("files", []),
            summary_profile=state.get("summary_profile", ""),
            writer_context=state.get("writer_context", ""),
            letter_content=state.get("letter_full", ""),
            step_ingest=True,
            step_summary=True,
            step_writer=True,
        )

    return jsonify({"letter": state.get("letter_full", ""), "output_path": output_path})


@app.post("/api/run_add_file")
def run_add_file():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    file_ref = payload.get("file")
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
    writer_context = (payload.get("writer_context") or "").strip()

    if not file_ref:
        return jsonify({"error": "missing_file"}), 400

    resolved_path = _resolve_input_file_path(input_dir, str(file_ref))
    if not resolved_path:
        return jsonify({"error": "file_not_found"}), 404

    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    llm = ChatOpenAI(model=model, temperature=0)
    state: GraphState = {
        "input_dir": input_dir,
        "output_path": output_path,
        "model": model,
        "llm": llm,
        "files": state_cache.get("files", []),
        "grouped": state_cache.get("grouped", {}),
        "summary_profile": state_cache.get("summary_profile", ""),
        "writer_context": writer_context or state_cache.get("writer_context", ""),
        "letter_full": state_cache.get("letter_full", ""),
    }

    filename = os.path.basename(resolved_path)
    text = extract_text_with_openai(llm, resolved_path)
    new_file = {
        "path": resolved_path,
        "name": filename,
        "text": text,
        "domain": detect_domain(filename),
    }
    state["files"] = _upsert_file_record(state.get("files", []), new_file)
    _save_state(cache_dir, state)
    _save_step_output(cache_dir, "ingest", state)

    for step in ["summary", "writer"]:
        state = _run_single_step(step, state)
        _save_state(cache_dir, state)
        _save_step_output(cache_dir, step, state)

    return jsonify(
        {
            "status": "done",
            "added_file": os.path.relpath(resolved_path, input_dir).replace("\\", "/"),
            "summary_profile": state.get("summary_profile", ""),
            "letter": state.get("letter_full", ""),
            "output_path": output_path,
        }
    )


@app.post("/api/itinerary/run")
def run_itinerary():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "itinerary.html"))
    flight_file = payload.get("flight_file")
    hotel_file = payload.get("hotel_file")
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
    project_id = payload.get("project_id")

    if not flight_file or not hotel_file:
        return jsonify({"error": "missing_files"}), 400

    cache_dir = _cache_dir(output_path)
    summary_profile = (payload.get("summary_profile") or "").strip()
    if not summary_profile:
        summary_path = os.path.join(cache_dir, "itinerary_summary.txt")
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_profile = f.read().strip()
    if not summary_profile:
        return jsonify({"error": "missing_itinerary_summary"}), 400

    llm = ChatOpenAI(model=model, temperature=0)
    flight_path = _resolve_input_file_path(input_dir, str(flight_file))
    hotel_path = _resolve_input_file_path(input_dir, str(hotel_file))
    if not flight_path or not hotel_path:
        return jsonify({"error": "missing_files"}), 400

    flight_text = extract_text_with_openai(llm, flight_path)
    hotel_text = extract_text_with_openai(llm, hotel_path)

    itinerary = itinerary_writer(llm, flight_text, hotel_text, summary_profile)

    # Save to file cache
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(itinerary)
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "itinerary.html"), "w", encoding="utf-8") as f:
        f.write(itinerary)

    # Save to DB
    if project_id:
        ctx = db.get_latest_itinerary_context(int(project_id)) or {}
        db.save_itinerary_html(int(project_id), ctx, itinerary)

    return jsonify({"itinerary": itinerary, "output_path": output_path})


# ==================== BOOKING GENERATOR ENDPOINTS ====================

from datetime import datetime, timedelta
from booking.generator import (
    generate_all_bookings,
    fill_hotel_template,
    fill_flight_template,
    generate_bookings_from_ai,
)
from booking.ai_agent import (
    DEFAULT_TRIP_INFO,
    extract_trip_info,
    ai_select_bookings,
    generate_ai_booking,
)


@app.post("/api/booking/generate")
def generate_booking():
    """Generate hotel and flight booking confirmations."""
    payload = request.get_json(force=True) or {}
    
    destination = payload.get("destination", "Australia")
    num_days = int(payload.get("num_days", 10))
    guest_name = payload.get("guest_name", "")
    origin_airport = payload.get("origin_airport", "HAN")
    output_dir = payload.get("output_dir", "output")
    
    # Get guest name from summary if not provided
    if not guest_name:
        guest_name = "NGUYEN VAN A"
    
    # Calculate start date (3 months from now by default)
    start_date_str = payload.get("start_date")
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    else:
        start_date = datetime.now() + timedelta(days=90)
    
    # Generate bookings
    hotel_bookings, flight_booking = generate_all_bookings(
        destination=destination,
        num_days=num_days,
        guest_name=guest_name,
        origin_airport=origin_airport,
        start_date=start_date
    )
    
    # Fill templates and save
    os.makedirs(output_dir, exist_ok=True)
    
    # Hotel template path
    hotel_template_path = os.path.join(
        os.path.dirname(__file__), 
        "templates", 
        "hotel_booking.html"
    )
    
    # Flight template path
    flight_template_path = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "flight_booking.html"
    )
    
    # Generate hotel HTMLs
    hotel_htmls = []
    for i, booking in enumerate(hotel_bookings, 1):
        if os.path.exists(hotel_template_path):
            html = fill_hotel_template(hotel_template_path, booking)
        else:
            # Fallback: return JSON as HTML
            html = f"<pre>{json.dumps(booking, indent=2, ensure_ascii=False)}</pre>"
        
        output_path = os.path.join(output_dir, f"booking_hotel_{i}.html")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        hotel_htmls.append({"path": output_path, "html": html, "data": booking})
    
    # Generate flight HTML
    if os.path.exists(flight_template_path):
        flight_html = fill_flight_template(flight_template_path, flight_booking)
    else:
        flight_html = f"<pre>{json.dumps(flight_booking, indent=2, ensure_ascii=False)}</pre>"
    
    flight_output_path = os.path.join(output_dir, "booking_flight.html")
    with open(flight_output_path, "w", encoding="utf-8") as f:
        f.write(flight_html)
    
    return jsonify({
        "status": "success",
        "hotel_bookings": [h["data"] for h in hotel_htmls],
        "hotel_htmls": [h["html"] for h in hotel_htmls],
        "hotel_paths": [h["path"] for h in hotel_htmls],
        "flight_booking": flight_booking,
        "flight_html": flight_html,
        "flight_path": flight_output_path,
        "guest_name": guest_name,
        "destination": destination,
        "num_days": num_days,
        "start_date": start_date.strftime("%Y-%m-%d")
    })


@app.get("/api/booking/latest")
def get_booking_latest():
    """Get the latest generated booking files."""
    project_id = request.args.get("project_id", type=int)
    if project_id:
        bk = db.get_latest_booking(project_id)
        if bk:
            return jsonify({"hotel_htmls": bk["hotel_htmls"], "flight_html": bk["flight_html"]})
        return jsonify({"hotel_htmls": [], "flight_html": ""})
    output_dir = request.args.get("output_dir", "output")
    result = {"hotel_htmls": [], "flight_html": ""}
    i = 1
    while True:
        hotel_path = os.path.join(output_dir, f"booking_hotel_{i}.html")
        if os.path.exists(hotel_path):
            with open(hotel_path, "r", encoding="utf-8") as f:
                result["hotel_htmls"].append(f.read())
            i += 1
        else:
            break
    flight_path = os.path.join(output_dir, "booking_flight.html")
    if os.path.exists(flight_path):
        with open(flight_path, "r", encoding="utf-8") as f:
            result["flight_html"] = f.read()
    return jsonify(result)


@app.get("/api/booking/destinations")
def get_destinations():
    """Get available destinations from the hotels database."""
    from booking_generator import load_hotels_database
    
    hotels_db = load_hotels_database()
    destinations = [key for key in hotels_db.keys() if key != "flights"]
    
    return jsonify({"destinations": destinations})


# ==================== AI BOOKING ENDPOINTS ====================

@app.post("/api/booking/extract_trip")
def extract_trip():
    """Extract trip information from input files."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
    project_id = payload.get("project_id")

    llm = ChatOpenAI(model=model, temperature=0)

    try:
        trip_info = extract_trip_info(llm, input_dir)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if not isinstance(trip_info, dict):
        trip_info = dict(DEFAULT_TRIP_INFO)

    # Cache trip info to file
    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "booking_trip_info.json"), "w", encoding="utf-8") as f:
        json.dump(trip_info, f, ensure_ascii=False, indent=2)
    booking_cache = os.path.join(cache_dir, "ai_booking_data.json")
    if os.path.exists(booking_cache):
        os.remove(booking_cache)

    # Save to DB
    if project_id:
        db.save_trip_info(int(project_id), trip_info)
        # Update input hash
        input_hash = db.compute_input_hash(input_dir)
        db.update_project(int(project_id), input_hash=input_hash)

    return jsonify({"status": "success", "trip_info": trip_info})


@app.get("/api/booking/trip/latest")
def get_booking_trip_latest():
    """Load cached trip info for editing in frontend."""
    project_id = request.args.get("project_id", type=int)
    if project_id:
        ti = db.get_latest_trip_info(project_id)
        data = ti["data"] if ti else dict(DEFAULT_TRIP_INFO)
        return jsonify({"trip_info": data})
    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    trip_path = os.path.join(cache_dir, "booking_trip_info.json")
    if not os.path.exists(trip_path):
        return jsonify({"trip_info": dict(DEFAULT_TRIP_INFO)})
    with open(trip_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    merged = dict(DEFAULT_TRIP_INFO)
    if isinstance(data, dict):
        merged.update(data)
    return jsonify({"trip_info": merged})


@app.post("/api/booking/trip/save")
def save_booking_trip():
    """Save edited trip info from frontend."""
    payload = request.get_json(force=True) or {}
    trip_info = payload.get("trip_info") or {}
    project_id = payload.get("project_id")
    if not isinstance(trip_info, dict):
        return jsonify({"error": "invalid_trip_info"}), 400

    merged = dict(DEFAULT_TRIP_INFO)
    merged.update(trip_info)

    # Save to file cache
    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "booking_trip_info.json"), "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    booking_cache = os.path.join(cache_dir, "ai_booking_data.json")
    if os.path.exists(booking_cache):
        os.remove(booking_cache)

    # Save to DB
    if project_id:
        db.save_trip_info(int(project_id), merged)

    return jsonify({"status": "success", "trip_info": merged})


@app.post("/api/booking/ai_generate")
def ai_generate_booking():
    """Generate bookings using AI. Uses cached booking data if available to save tokens."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_dir = payload.get("output_dir", "output")
    model = payload.get("model") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
    force_new = payload.get("force_new", False)
    trip_info_override = payload.get("trip_info")
    project_id = payload.get("project_id")

    cache_dir = _cache_dir(os.path.join("output", "letter.txt"))
    booking_cache_path = os.path.join(cache_dir, "ai_booking_data.json")
    trip_cache_path = os.path.join(cache_dir, "booking_trip_info.json")

    # If user edited trip info on frontend, persist and force new booking.
    if isinstance(trip_info_override, dict):
        merged_trip = dict(DEFAULT_TRIP_INFO)
        merged_trip.update(trip_info_override)
        os.makedirs(cache_dir, exist_ok=True)
        with open(trip_cache_path, "w", encoding="utf-8") as f:
            json.dump(merged_trip, f, ensure_ascii=False, indent=2)
        force_new = True
        if os.path.exists(booking_cache_path):
            os.remove(booking_cache_path)

    # --- Check for cached booking data first (skip AI to save tokens) ---
    booking_data = None
    trip_info = None
    used_cache = False

    if not force_new and os.path.exists(booking_cache_path):
        with open(booking_cache_path, "r", encoding="utf-8") as f:
            booking_data = json.load(f)
        if os.path.exists(trip_cache_path):
            with open(trip_cache_path, "r", encoding="utf-8") as f:
                trip_info = json.load(f)
        used_cache = True

    # --- If no cache, call AI ---
    if not booking_data:
        if os.path.exists(trip_cache_path):
            with open(trip_cache_path, "r", encoding="utf-8") as f:
                trip_info = json.load(f)

        llm = ChatOpenAI(model=model, temperature=0)

        try:
            trip_info, booking_data = generate_ai_booking(llm, input_dir, trip_info)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": f"Lỗi AI: {str(e)}"}), 500

        # Cache booking data for next time
        os.makedirs(cache_dir, exist_ok=True)
        with open(booking_cache_path, "w", encoding="utf-8") as f:
            json.dump(booking_data, f, ensure_ascii=False, indent=2)

    # Template paths
    hotel_template_path = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "hotel_booking.html"
    )
    flight_template_path = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "flight_booking.html"
    )

    try:
        # Generate HTML files from AI decisions
        result = generate_bookings_from_ai(
            ai_booking_data=booking_data,
            hotel_template_path=hotel_template_path,
            flight_template_path=flight_template_path,
            output_dir=output_dir,
        )

        # Save to DB
        if project_id:
            db.save_booking(
                int(project_id),
                booking_data=booking_data,
                hotel_htmls=result["hotel_htmls"],
                flight_html=result["flight_html"],
                reasoning=booking_data.get("reasoning", ""),
            )

        return jsonify({
            "status": "success",
            "used_cache": used_cache,
            "trip_info": trip_info,
            "booking_data": {
                "hotels": result["hotel_data"],
                "reasoning": booking_data.get("reasoning", ""),
            },
            "hotel_htmls": result["hotel_htmls"],
            "hotel_paths": result["hotel_paths"],
            "flight_html": result["flight_html"],
            "flight_path": result["flight_path"],
        })
    except Exception as e:
        import traceback
        return jsonify({"error": "Lỗi khi tạo HTML: " + str(e), "traceback": traceback.format_exc()}), 500

# ==================== AI PDF SPLITTER ENDPOINTS ====================

import uuid
import shutil
import zipfile
import threading
from pathlib import Path as SplitterPath

from pdf_tools.pdf_service import pdf_to_images, get_page_count, create_output_files
from pdf_tools.ai_service import classify_all_pages

# Directories for AI splitter
SPLITTER_UPLOAD_DIR = SplitterPath(__file__).parent / "splitter_uploads"
SPLITTER_OUTPUT_DIR = SplitterPath(__file__).parent / "splitter_outputs"
SPLITTER_UPLOAD_DIR.mkdir(exist_ok=True)
SPLITTER_OUTPUT_DIR.mkdir(exist_ok=True)

# In-memory job tracking for AI splitter
splitter_jobs: Dict[str, Dict] = {}


def _run_splitter_job(file_id: str):
    """Run AI PDF splitting in a background thread with its own event loop."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_process_splitter_job(file_id))
    finally:
        loop.close()


async def _process_splitter_job(file_id: str):
    """Process a PDF file: convert → classify → split."""
    job = splitter_jobs[file_id]
    try:
        # Step 1: Convert PDF pages to images
        job["status"] = "converting"
        images = pdf_to_images(job["file_path"])

        # Step 2: Classify each page with AI
        job["status"] = "classifying"

        async def progress_callback(page_num, total, result):
            job["current_page"] = page_num
            job["classifications"].append({
                "page": page_num,
                "document_type_en": result.get("document_type_en", ""),
                "person_name_en": result.get("person_name_en", ""),
                "is_continuation": result.get("is_continuation", False),
            })

        classifications = await classify_all_pages(
            images, progress_callback=progress_callback
        )

        # Update with post-processed data
        job["classifications"] = []
        for idx, cls in enumerate(classifications):
            job["classifications"].append({
                "page": idx + 1,
                "document_type_en": cls.get("document_type_en", ""),
                "person_name_en": cls.get("person_name_en", ""),
                "is_continuation": cls.get("is_continuation", False),
            })

        # Step 3: Create output files
        job["status"] = "splitting"
        job_output_dir = str(SPLITTER_OUTPUT_DIR / file_id)
        output_files = create_output_files(
            job["file_path"], classifications, job_output_dir
        )
        job["output_files"] = output_files

        # Step 4: Create ZIP
        zip_path = str(SPLITTER_OUTPUT_DIR / f"{file_id}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in output_files:
                zf.write(f["path"], f["filename"])
        job["zip_path"] = zip_path
        job["status"] = "completed"

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        print(f"[AI Splitter] Error processing {file_id}: {e}")


@app.post("/api/ai-splitter/upload")
def splitter_upload():
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_pdf"}), 400

    file_id = uuid.uuid4().hex[:8]
    job_dir = SPLITTER_UPLOAD_DIR / file_id
    job_dir.mkdir(exist_ok=True)
    file_path = job_dir / file.filename
    file.save(str(file_path))

    page_count = get_page_count(str(file_path))

    splitter_jobs[file_id] = {
        "status": "uploaded",
        "filename": file.filename,
        "file_path": str(file_path),
        "page_count": page_count,
        "current_page": 0,
        "classifications": [],
        "output_files": [],
        "error": None,
        "zip_path": None,
    }

    return jsonify({
        "file_id": file_id,
        "filename": file.filename,
        "page_count": page_count,
    })


@app.post("/api/ai-splitter/process/<file_id>")
def splitter_process(file_id: str):
    if file_id not in splitter_jobs:
        return jsonify({"error": "not_found"}), 404
    job = splitter_jobs[file_id]
    if job["status"] in ("processing", "classifying", "converting", "splitting"):
        return jsonify({"message": "already_processing"})
    if job["status"] == "completed":
        return jsonify({"message": "already_completed"})

    job["status"] = "processing"
    job["current_page"] = 0
    job["classifications"] = []
    job["output_files"] = []
    job["error"] = None

    # Run in background thread (separate event loop for async code)
    t = threading.Thread(target=_run_splitter_job, args=(file_id,), daemon=True)
    t.start()

    return jsonify({"message": "processing_started", "file_id": file_id})


@app.get("/api/ai-splitter/status/<file_id>")
def splitter_status(file_id: str):
    if file_id not in splitter_jobs:
        return jsonify({"error": "not_found"}), 404
    job = splitter_jobs[file_id]
    resp = {
        "file_id": file_id,
        "filename": job["filename"],
        "status": job["status"],
        "page_count": job["page_count"],
        "current_page": job["current_page"],
        "error": job["error"],
        "classifications": job.get("classifications", []),
    }
    if job["status"] == "completed":
        resp["output_files"] = [
            {
                "filename": f["filename"],
                "document_type": f["document_type"],
                "person_name": f["person_name"],
                "pages": f["pages"],
            }
            for f in job["output_files"]
        ]
    return jsonify(resp)


@app.get("/api/ai-splitter/download/<file_id>/<filename>")
def splitter_download_single(file_id: str, filename: str):
    if file_id not in splitter_jobs:
        return jsonify({"error": "not_found"}), 404
    file_path = SPLITTER_OUTPUT_DIR / file_id / filename
    if not file_path.exists():
        return jsonify({"error": "file_not_found"}), 404
    return send_from_directory(str(SPLITTER_OUTPUT_DIR / file_id), filename,
                                as_attachment=True, mimetype="application/pdf")


@app.get("/api/ai-splitter/download-zip/<file_id>")
def splitter_download_zip(file_id: str):
    if file_id not in splitter_jobs:
        return jsonify({"error": "not_found"}), 404
    job = splitter_jobs[file_id]
    if job["status"] != "completed" or not job.get("zip_path"):
        return jsonify({"error": "not_ready"}), 400
    zip_path = SplitterPath(job["zip_path"])
    return send_from_directory(str(zip_path.parent), zip_path.name,
                                as_attachment=True, mimetype="application/zip")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)

