"""
Pipeline routes: classifier, scan-splitter, pdf-tools, itinerary, run.
"""
from __future__ import annotations

import json
import logging
import io
import os
import re
import shutil
import uuid
import zipfile
from pathlib import Path as SplitterPath
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, jsonify, request, send_file

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pypdf import PdfReader, PdfWriter

import database as db
from core.agents import detect_domain, itinerary_writer, extract_text_with_openai
from core.errors import QuotaExhaustedError, is_quota_error
from core.helpers import get_text_model, get_vision_model, list_input_files, cache_dir
from core.state import GraphState
from classifier.agent import classify_files_in_folder
from config import Config

pipeline_bp = Blueprint("pipeline", __name__)

# Base directory (project root, one level up from routes/)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUTPUT_DIR = os.path.join(_BASE_DIR, "output")

# Splitter output directory (needed by manual split routes)
SPLITTER_OUTPUT_DIR = SplitterPath(_BASE_DIR) / Config.SPLITTER_OUTPUTS_DIR

# Alias for backward compat
_is_quota_error = is_quota_error


# get_text_model, get_vision_model, list_input_files, cache_dir → imported from core.helpers

STEP_ORDER = ["ingest", "summary", "writer"]

# Alias for backward compatibility (many routes reference _cache_dir)
_cache_dir = cache_dir


def _is_step_done(cache_directory: str, step: str) -> bool:
    """Check if a pipeline step has been completed."""
    marker = os.path.join(cache_directory, f"step_{step}.json")
    return os.path.exists(marker)


def _load_state(cache_directory: str) -> dict:
    """Load cached pipeline state from JSON file."""
    state_file = os.path.join(cache_directory, "state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def _state_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "state.json")


def _step_marker_path(cache_dir: str, step: str) -> str:
    return os.path.join(cache_dir, f"step_{step}.json")


def _reset_downstream_steps(cache_dir: str, step: str) -> None:
    if step not in STEP_ORDER:
        return
    idx = STEP_ORDER.index(step)
    downstream = STEP_ORDER[idx + 1:]
    for ds in downstream:
        marker = _step_marker_path(cache_dir, ds)
        if os.path.exists(marker):
            os.remove(marker)


def _check_and_raise_quota(response):
    """Check response for quota errors and raise if found."""
    if hasattr(response, "response_metadata"):
        meta = response.response_metadata or {}
        finish = meta.get("finish_reason", "")
        if finish == "error":
            raise QuotaExhaustedError("API quota exceeded")


def _save_state(cache_directory: str, state: dict) -> None:
    """Persist pipeline state (files, model, paths) to disk."""
    os.makedirs(cache_directory, exist_ok=True)
    state_file = os.path.join(cache_directory, "state.json")
    # Filter out non-serialisable values (llm instance, etc.)
    safe_state = {}
    for k, v in state.items():
        try:
            json.dumps(v, ensure_ascii=False)
            safe_state[k] = v
        except (TypeError, ValueError):
            pass  # skip non-serialisable (e.g. llm object)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(safe_state, f, ensure_ascii=False, indent=2)


def _save_step_output(cache_directory: str, step: str, data: dict) -> None:
    """Write a step-completion marker with the step's output."""
    os.makedirs(cache_directory, exist_ok=True)
    marker = os.path.join(cache_directory, f"step_{step}.json")
    safe_data = {}
    for k, v in data.items():
        try:
            json.dumps(v, ensure_ascii=False)
            safe_data[k] = v
        except (TypeError, ValueError):
            pass
    with open(marker, "w", encoding="utf-8") as f:
        json.dump({"step": step, "done": True, "data": safe_data}, f, ensure_ascii=False, indent=2)


def _missing_prereq_step(cache_directory: str, step: str) -> Optional[str]:
    """Return the name of the first prerequisite step that hasn't run yet, or None."""
    if step not in STEP_ORDER:
        return None
    idx = STEP_ORDER.index(step)
    for prereq in STEP_ORDER[:idx]:
        if not _is_step_done(cache_directory, prereq):
            return prereq
    return None


def _run_single_step(state: dict, step: str, **kwargs) -> dict:
    """Execute a single pipeline step and return updated state."""
    from core.agents import (
        ingest_files,
        build_summary_profile,
        letter_writer,
    )
    if step == "ingest":
        return ingest_files(state)
    elif step == "summary":
        return build_summary_profile(state)
    elif step == "writer":
        return letter_writer(state, **kwargs)
    raise ValueError(f"Unknown step: {step}")


def _resolve_input_file_path(input_dir: str, filename: str) -> str:
    """Safely join input_dir + filename, preventing path traversal."""
    base = os.path.abspath(input_dir)
    full = os.path.abspath(os.path.join(input_dir, filename))
    if not full.startswith(base):
        raise ValueError(f"Path traversal detected: {filename}")
    return full


def _upsert_file_record(project_id: int, file_info: dict) -> None:
    """Insert or update a file record in the database for a project."""
    try:
        db.save_letter_state(
            project_id,
            files_data=[file_info],
        )
    except Exception as e:
        import logging; logging.exception("[Safe Log] Unhandled exception in pipeline.py: %s", e)
        logging.debug("_upsert_file_record ignored: %s", e)

@pipeline_bp.post("/api/pipeline/send-to-splitter")
def pipeline_send_to_splitter():
    """Copy selected multi-doc files → splitter_uploads for AI splitting."""
    payload = request.get_json(force=True) or {}
    file_paths = payload.get("file_paths", [])
    project_id = payload.get("project_id")

    if not file_paths:
        return jsonify({"error": "no_files_selected"}), 400

    target_dir = Config.SPLITTER_UPLOADS_DIR
    os.makedirs(target_dir, exist_ok=True)
    copied = []

    # Normalise project_id to int if possible
    pid: Optional[int]
    if isinstance(project_id, int):
        pid = project_id
    elif isinstance(project_id, str) and project_id.isdigit():
        pid = int(project_id)
    else:
        pid = None

    for src in file_paths:
        if not os.path.isfile(src):
            continue
        original_name = os.path.basename(src)

        # Prefix filename with project id so we can filter queue per project later.
        # Old files without prefix will be treated as "global" and ignored when a project_id is provided.
        if pid is not None:
            stored_name = f"p{pid}__{original_name}"
        else:
            stored_name = original_name

        dst = os.path.join(target_dir, stored_name)
        base, ext = os.path.splitext(stored_name)
        idx = 1
        while os.path.exists(dst):
            dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
            idx += 1
        shutil.copy2(src, dst)
        copied.append(stored_name)

    # Save mapping: stored_name → original_path (for save-to-source later)
    mapping_file = os.path.join(target_dir, "_source_mapping.json")
    existing_mapping = {}
    if os.path.isfile(mapping_file):
        try:
            with open(mapping_file, "r", encoding="utf-8") as mf:
                existing_mapping = json.load(mf)
        except Exception as e:
            import logging; logging.exception("[Safe Log] Unhandled exception in pipeline.py: %s", e)
            logging.debug("Ignored: %s", e)
    for src, stored in zip(file_paths, copied):
        existing_mapping[stored] = src
    with open(mapping_file, "w", encoding="utf-8") as mf:
        json.dump(existing_mapping, mf, ensure_ascii=False, indent=2)

    return jsonify({"status": "done", "copied": copied, "count": len(copied)})


@pipeline_bp.post("/api/splitter/save-to-source")
def splitter_save_to_source():
    """Save split output files back to the original file's folder and delete the original."""
    payload = request.get_json(force=True) or {}
    file_id = payload.get("file_id", "")
    original_path = payload.get("original_path", "")

    if not file_id:
        return jsonify({"error": "no_file_id"}), 400
    if not original_path or not os.path.isfile(original_path):
        return jsonify({"error": "original_file_not_found", "path": original_path}), 404

    # Find split output directory
    output_dir = os.path.join(_BASE_DIR, Config.SPLITTER_OUTPUTS_DIR, file_id)
    if not os.path.isdir(output_dir):
        return jsonify({"error": "split_output_not_found"}), 404

    target_dir = os.path.dirname(original_path)
    saved = []
    errors = []

    # Copy each split PDF to the source folder
    for fname in os.listdir(output_dir):
        if not fname.lower().endswith(".pdf"):
            continue
        src = os.path.join(output_dir, fname)
        dst = os.path.join(target_dir, fname)
        # Handle duplicate names
        if os.path.exists(dst):
            base, ext = os.path.splitext(fname)
            idx = 1
            while os.path.exists(dst):
                dst = os.path.join(target_dir, f"{base}_({idx}){ext}")
                idx += 1
        try:
            shutil.copy2(src, dst)
            saved.append(os.path.basename(dst))
        except Exception as e:
            import logging; logging.exception("[Safe Log] Unhandled exception in pipeline.py: %s", e)
            errors.append({"file": fname, "error": str(e)})

    # Delete the original file if at least 1 split file was saved
    deleted_original = False
    if saved:
        try:
            os.remove(original_path)
            deleted_original = True
        except Exception as e:
            import logging; logging.exception("[Safe Log] Unhandled exception in pipeline.py: %s", e)
            logging.debug("Ignored: %s", e)

    return jsonify({
        "status": "done",
        "saved": saved,
        "saved_count": len(saved),
        "deleted_original": deleted_original,
        "original_name": os.path.basename(original_path),
        "target_dir": target_dir,
        "errors": errors,
    })



@pipeline_bp.get("/api/splitter/source-mapping")
def splitter_source_mapping():
    """Return the stored_name → original_path mapping for save-to-source."""
    mapping_file = os.path.join(Config.SPLITTER_UPLOADS_DIR, "_source_mapping.json")
    if os.path.isfile(mapping_file):
        try:
            with open(mapping_file, "r", encoding="utf-8") as mf:
                return jsonify(json.load(mf))
        except Exception as e:
            import logging; logging.exception("[Safe Log] Unhandled exception in pipeline.py: %s", e)
            logging.debug("Ignored: %s", e)
    return jsonify({})


@pipeline_bp.post("/api/pipeline/send-clean-to-classifier")
def pipeline_send_clean_to_classifier():
    """Copy clean (single-doc) files directly → classifier input folder."""
    payload = request.get_json(force=True) or {}
    file_paths = payload.get("file_paths", [])
    target_dir = payload.get("target_dir", Config.CLASSIFIER_INPUT_DIR)

    if not file_paths:
        return jsonify({"error": "no_files_selected"}), 400

    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for src in file_paths:
        if not os.path.isfile(src):
            continue
        fname = os.path.basename(src)
        dst = os.path.join(target_dir, fname)
        base, ext = os.path.splitext(fname)
        idx = 1
        while os.path.exists(dst):
            dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
            idx += 1
        shutil.copy2(src, dst)
        copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied), "target_dir": target_dir})


@pipeline_bp.post("/api/pipeline/send-to-classifier")
def pipeline_send_to_classifier():
    """Copy ALL splitter output files (AI + manual) → classifier input folder.
    Walks splitter_outputs/ recursively, skipping .zip files."""
    payload = request.get_json(force=True) or {}
    file_id = payload.get("file_id", "")
    target_dir = payload.get("target_dir", Config.CLASSIFIER_INPUT_DIR)

    # Find source: specific file_id or all outputs
    source_dir = os.path.join(Config.SPLITTER_OUTPUTS_DIR, file_id) if file_id else ""
    if not source_dir or not os.path.isdir(source_dir):
        source_dir = Config.SPLITTER_OUTPUTS_DIR
        if not os.path.isdir(source_dir):
            return jsonify({"error": "no_splitter_output"}), 404

    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for root, _, files in os.walk(source_dir):
        for fname in files:
            if fname.endswith(".zip"):
                continue
            if not fname.lower().endswith(".pdf"):
                continue
            src = os.path.join(root, fname)
            dst = os.path.join(target_dir, fname)
            # Avoid overwriting: add suffix if exists
            base, ext = os.path.splitext(fname)
            idx = 1
            while os.path.exists(dst):
                dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
                idx += 1
            shutil.copy2(src, dst)
            copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied), "target_dir": target_dir})


# ═══════════════════════════════════════════════════════════════════
# SCAN SPLITTER — Split scanned PDFs by Translation Certification Page
# Detects "PASSPORT LOUNGE" / "undertake to translate" certification pages
# and splits PDF at these boundaries.
# ═══════════════════════════════════════════════════════════════════

_scan_splitter_llm = None

def _get_or_create_llm():
    """Get or create a cached ChatOpenAI instance for vision tasks."""
    global _scan_splitter_llm
    if _scan_splitter_llm is None:
        _scan_splitter_llm = ChatOpenAI(model=get_vision_model(), temperature=0)
    return _scan_splitter_llm


_scan_split_progress = {"total": 0, "done": 0, "current_page": "", "running": False, "results": [], "error": ""}

# Keywords that identify a Passport Lounge translation certification page
_CERT_KEYWORDS = [
    "passport lounge",
    "undertake to translate",
    "cam đoan đã dịch chính xác",
    "cam doan da dich chinh xac",
    "signature of translator",
    "chữ ký của người dịch",
]


def _is_certification_page_by_text(page_text: str) -> bool:
    """Check if page text contains translation certification keywords."""
    if not page_text or len(page_text.strip()) < 20:
        return False
    text_lower = page_text.lower()
    # Must match at least 2 keywords to avoid false positives
    matches = sum(1 for kw in _CERT_KEYWORDS if kw in text_lower)
    return matches >= 2


def _batch_detect_cert_pages_vision(llm, page_images_b64: list, page_numbers: list) -> list:
    """Batch vision: check multiple pages at once for translation certification.
    Sends bottom 40% crop of each page to save tokens.
    Returns list of page numbers that ARE certification pages."""
    from langchain_core.messages import HumanMessage, SystemMessage

    content_parts = [
        {"type": "text", "text": f"""You are analyzing {len(page_images_b64)} scanned document pages.

For EACH page, determine if it is a TRANSLATION CERTIFICATION page.
A translation certification page has ALL of these features:
- Header from "PASSPORT LOUNGE COMPANY LIMITED" (with the Passport Lounge logo)
- A bilingual statement about translating documents accurately
- Translator signature area with company stamp/seal at the bottom

⚠️ IMPORTANT: Do NOT mark pages that have OTHER types of stamps (bank stamps, government stamps, notary stamps). 
ONLY mark pages with the specific PASSPORT LOUNGE translation certification.

Pages shown: {', '.join(str(p) for p in page_numbers)}

Return JSON ONLY: {{"cert_pages": [list of page numbers that ARE certification pages]}}
Example: {{"cert_pages": [2, 5, 8]}} or {{"cert_pages": []}} if none."""}
    ]

    for i, (b64, pnum) in enumerate(zip(page_images_b64, page_numbers)):
        content_parts.append({"type": "text", "text": f"Page {pnum}:"})
        content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    try:
        result = llm.invoke([
            SystemMessage(content="You are an expert document analyzer. Answer ONLY with JSON."),
            HumanMessage(content=content_parts),
        ])
        import json as _json
        text = result.content if hasattr(result, 'content') else str(result)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = _json.loads(text)
        return parsed.get("cert_pages", [])
    except Exception as e:
        import logging; logging.exception("[Safe Log] Unhandled exception in pipeline.py: %s", e)
        print(f"[SCAN-SPLITTER] ❌ Vision batch error: {e}")
        return []


@pipeline_bp.post("/api/ai-splitter/save-to-input")
def splitter_save_to_input():
    """Copy split output files back to the ORIGINAL source file's folder.
    Uses source_path from _source.json to determine correct subfolder.
    Deletes the original source file that was split.
    """
    payload = request.get_json(force=True) or {}
    target_dir = payload.get("target_dir", "input")  # fallback base
    delete_originals = payload.get("delete_originals", True)

    output_base = Config.SPLITTER_OUTPUTS_DIR
    if not os.path.isdir(output_base):
        return jsonify({"error": "no_splitter_output"}), 404

    # Also load the source mapping as fallback
    source_mapping = {}
    mapping_file = os.path.join(Config.SPLITTER_UPLOADS_DIR, "_source_mapping.json")
    if os.path.isfile(mapping_file):
        try:
            with open(mapping_file, "r", encoding="utf-8") as mf:
                source_mapping = json.load(mf)
        except Exception as e:
            import logging; logging.exception("[Safe Log] Unhandled exception in pipeline.py: %s", e)
            logging.debug("Ignored: %s", e)

    copied = []
    originals_deleted = []

    for folder_name in sorted(os.listdir(output_base)):
        folder_path = os.path.join(output_base, folder_name)
        if not os.path.isdir(folder_path):
            continue

        # Read source metadata
        source_path = ""
        source_filename = ""
        source_meta_path = os.path.join(folder_path, "_source.json")
        if os.path.isfile(source_meta_path):
            try:
                with open(source_meta_path, "r", encoding="utf-8") as mf:
                    meta = json.load(mf)
                source_path = meta.get("source_path", "")
                source_filename = meta.get("source_filename", "")
            except Exception as e:
                import logging; logging.exception("[Safe Log] Unhandled exception in pipeline.py: %s", e)
                logging.debug("Ignored: %s", e)

        # If no source_path in _source.json, try the mapping
        if not source_path and source_filename and source_filename in source_mapping:
            source_path = source_mapping[source_filename]

        # Determine destination folder from the original file's location
        if source_path and os.path.isfile(source_path):
            dest_folder = os.path.dirname(source_path)
        elif source_path:
            # source_path set but file already deleted — use its directory
            dest_folder = os.path.dirname(source_path)
        else:
            # Last resort: search for source file in target_dir tree
            dest_folder = target_dir
            # Strip pN__ prefix to get original filename for searching
            search_name = source_filename
            if "__" in search_name:
                search_name = search_name.split("__", 1)[1]
            if search_name:
                for root, _, files in os.walk(target_dir):
                    if search_name in files:
                        dest_folder = root
                        break

        os.makedirs(dest_folder, exist_ok=True)

        # Copy all PDFs to the correct folder
        for fname in sorted(os.listdir(folder_path)):
            fpath = os.path.join(folder_path, fname)
            if not os.path.isfile(fpath) or not fname.lower().endswith(".pdf"):
                continue
            dst = os.path.join(dest_folder, fname)
            base, ext = os.path.splitext(fname)
            idx = 1
            while os.path.exists(dst):
                dst = os.path.join(dest_folder, f"{base} ({idx}){ext}")
                idx += 1
            shutil.copy2(fpath, dst)
            copied.append(fname)

        # Delete original source file
        if delete_originals and source_path and os.path.isfile(source_path):
            try:
                os.remove(source_path)
                originals_deleted.append(os.path.basename(source_path))
            except Exception as e:
                import logging; logging.exception("[Safe Log] Unhandled exception in pipeline.py: %s", e)
                logging.debug("Ignored: %s", e)

    return jsonify({
        "status": "done",
        "copied": copied,
        "count": len(copied),
        "originals_deleted": originals_deleted,
        "target_dir": target_dir,
    })

@pipeline_bp.post("/api/pipeline/send-to-input")
def pipeline_send_to_input():
    """Copy classifier output files → letter/booking input folder."""
    payload = request.get_json(force=True) or {}
    source_dir = payload.get("source_dir", Config.CLASSIFIER_OUTPUT_DIR)
    target_dir = payload.get("target_dir", "input")

    if not os.path.isdir(source_dir):
        return jsonify({"error": "no_classifier_output"}), 404

    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for root, _, files in os.walk(source_dir):
        for fname in files:
            src = os.path.join(root, fname)
            dst = os.path.join(target_dir, fname)
            base, ext = os.path.splitext(fname)
            idx = 1
            while os.path.exists(dst):
                dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
                idx += 1
            shutil.copy2(src, dst)
            copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied), "target_dir": target_dir})

def _safe_join(base: str, rel_path: str) -> str:
    base_abs = os.path.abspath(base)
    candidate = os.path.abspath(os.path.join(base, rel_path))
    if not candidate.startswith(base_abs):
        raise ValueError("Invalid path")
    return candidate


@pipeline_bp.get("/api/steps")
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


@pipeline_bp.get("/api/summary")
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


@pipeline_bp.get("/api/writer_context")
def get_writer_context():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        state = db.get_latest_letter_state(project_id)
        return jsonify({"writer_context": state["writer_context"] if state else ""})
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    cache_dir = _cache_dir(output_path)
    state_cache = _load_state(cache_dir)
    return jsonify({"writer_context": state_cache.get("writer_context", "")})


@pipeline_bp.get("/api/ingest_stream")
def ingest_stream():
    input_dir = request.args.get("input_dir", "input")
    output_path = request.args.get("output", os.path.join("output", "letter.txt"))
    model = request.args.get("model") or get_vision_model()  # ingest reads images
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


@pipeline_bp.post("/api/run_step")
def run_step():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    step = payload.get("step")
    model = payload.get("model") or get_vision_model()  # ingest step reads images
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

    state = _run_single_step(state, step)
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


@pipeline_bp.post("/api/run_all")
def run_all():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    model = payload.get("model") or get_vision_model()  # pipeline includes ingest (images)
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
        state = _run_single_step(state, step)
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


@pipeline_bp.post("/api/run_add_file")
def run_add_file():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "letter.txt"))
    file_ref = payload.get("file")
    model = payload.get("model") or get_vision_model()  # reads input files (images/PDFs)
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
    # Append new file to existing files list (upsert by name)
    existing_files = state.get("files", [])
    existing_files = [f for f in existing_files if f.get("name") != filename]
    existing_files.append(new_file)
    state["files"] = existing_files
    _save_state(cache_dir, state)
    _save_step_output(cache_dir, "ingest", state)

    for step in ["summary", "writer"]:
        state = _run_single_step(state, step)
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



