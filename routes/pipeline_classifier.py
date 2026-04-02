"""
Classifier routes: list files, run classifier, save output, rename, split manual.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request
from pypdf import PdfReader, PdfWriter

from core.helpers import get_vision_model, list_input_files
from classifier.agent import classify_files_in_folder
from config import Config

from routes.pipeline_helpers import _safe_join

# Base directory (project root, one level up from routes/)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPLITTER_OUTPUT_DIR = Path(_BASE_DIR) / Config.SPLITTER_OUTPUTS_DIR


pipeline_classifier_bp = Blueprint("pipeline_classifier", __name__)


@pipeline_classifier_bp.get("/api/classifier/files")
def list_classifier_files():
    input_dir = request.args.get("input_dir", Config.CLASSIFIER_INPUT_DIR)
    if not os.path.isdir(input_dir):
        return jsonify({"input_dir": input_dir, "files": [], "exists": False})
    items = list_input_files(input_dir)
    return jsonify(
        {
            "input_dir": input_dir,
            "exists": True,
            "files": items,
        }
    )


@pipeline_classifier_bp.post("/api/classifier/delete")
def classifier_delete_file():
    """Delete a single file from classifier input folder."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", os.path.join("phanloai", "input"))
    filename = payload.get("filename", "")
    if not filename:
        return jsonify({"error": "no_filename"}), 400
    file_path = os.path.join(input_dir, filename)
    if not os.path.isfile(file_path):
        return jsonify({"error": "file_not_found"}), 404
    os.remove(file_path)
    return jsonify({"deleted": filename})


@pipeline_classifier_bp.post("/api/classifier/delete-all")
def classifier_delete_all():
    """Delete all files from classifier input folder."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", Config.CLASSIFIER_INPUT_DIR)
    count = 0
    if os.path.isdir(input_dir):
        for fname in os.listdir(input_dir):
            fpath = os.path.join(input_dir, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
                count += 1
    return jsonify({"deleted_count": count})


@pipeline_classifier_bp.post("/api/classifier/run")
def run_classifier():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", Config.CLASSIFIER_INPUT_DIR)
    output_dir = payload.get("output_dir", Config.CLASSIFIER_OUTPUT_DIR)
    save_output = payload.get("save_output", False)  # Don't auto-save by default
    model = payload.get("model") or get_vision_model()  # classifier reads images

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404

    # If save_output is False, use a temp dir so classifier doesn't write to real output
    actual_output = output_dir if save_output else Config.CLASSIFIER_TEMP_OUTPUT_DIR
    result = classify_files_in_folder(input_dir=input_dir, output_dir=actual_output, model=model)
    # Store the temp dir in result so save-output can use it
    result["_temp_output"] = actual_output
    result["_final_output"] = output_dir
    return jsonify({"status": "done", **result})

@pipeline_classifier_bp.get("/api/classifier/last-result")
def classifier_last_result():
    """Scan _temp_output to reconstruct last classification result."""
    temp_output = Config.CLASSIFIER_TEMP_OUTPUT_DIR
    if not os.path.isdir(temp_output):
        return jsonify({"exists": False})

    copied = []
    person_counts = {}
    for person_dir in sorted(os.listdir(temp_output)):
        person_path = os.path.join(temp_output, person_dir)
        if not os.path.isdir(person_path):
            continue
        count = 0
        for fname in sorted(os.listdir(person_path)):
            fpath = os.path.join(person_path, fname)
            if not os.path.isfile(fpath):
                continue
            count += 1
            # Try to extract doc_type from filename: DOMAIN_PERSON_DOCTYPE.ext
            stem = os.path.splitext(fname)[0]
            parts = stem.split("_", 2)  # DOMAIN_PERSON_DOCTYPE or just name
            doc_type = parts[-1] if len(parts) >= 3 else stem
            # Remove trailing (1), (2) etc
            import re
            doc_type = re.sub(r'\s*\(\d+\)$', '', doc_type).strip()

            rel_path = os.path.join(person_dir, fname).replace("\\", "/")
            copied.append({
                "source": fname,
                "person_name": person_dir,
                "doc_type_en": doc_type,
                "to": rel_path,
            })
        if count > 0:
            person_counts[person_dir] = count

    if not copied:
        return jsonify({"exists": False})

    return jsonify({
        "exists": True,
        "status": "done",
        "copied": copied,
        "copied_count": len(copied),
        "skipped_count": 0,
        "person_counts": person_counts,
        "_temp_output": temp_output,
        "_final_output": Config.CLASSIFIER_OUTPUT_DIR,
    })


@pipeline_classifier_bp.post("/api/classifier/save-output")
def classifier_save_output():
    """Copy classified results from temp to final output folder."""
    payload = request.get_json(force=True) or {}
    temp_output = payload.get("temp_output", Config.CLASSIFIER_TEMP_OUTPUT_DIR)
    final_output = payload.get("output_dir", Config.CLASSIFIER_OUTPUT_DIR)

    if not os.path.isdir(temp_output):
        return jsonify({"error": "no_results_to_save"}), 404

    os.makedirs(final_output, exist_ok=True)
    count = 0
    for root, dirs, files in os.walk(temp_output):
        rel = os.path.relpath(root, temp_output)
        dest_dir = os.path.join(final_output, rel) if rel != "." else final_output
        os.makedirs(dest_dir, exist_ok=True)
        for fname in files:
            src = os.path.join(root, fname)
            dst = os.path.join(dest_dir, fname)
            shutil.copy2(src, dst)
            count += 1

    # Auto-cleanup: delete temp output to save disk space
    try:
        shutil.rmtree(temp_output)
    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in pipeline_classifier.py: %s", e)
        logging.debug("Ignored: %s", e)

    # Optional: clean input files too
    clean_input = payload.get("clean_input", False)
    input_dir = payload.get("input_dir", Config.CLASSIFIER_INPUT_DIR)
    if clean_input and os.path.isdir(input_dir):
        try:
            shutil.rmtree(input_dir)
            os.makedirs(input_dir, exist_ok=True)
        except Exception as e:
            logging.exception("[Safe Log] Unhandled exception in pipeline_classifier.py: %s", e)
            logging.debug("Ignored: %s", e)

    return jsonify({"status": "saved", "output_dir": final_output, "file_count": count})


@pipeline_classifier_bp.post("/api/classifier/rename-file")
def classifier_rename_file():
    """Rename/move a classified output file to a different person or doc_type."""
    payload = request.get_json(force=True) or {}
    old_path = payload.get("old_path", "")  # relative path like "UNKNOWN PERSON/FINANCIAL_BANK STATEMENT.pdf"
    new_person = payload.get("new_person", "").strip()
    new_doc_type = payload.get("new_doc_type", "").strip()
    temp_output = payload.get("temp_output", Config.CLASSIFIER_TEMP_OUTPUT_DIR)

    if not old_path or not new_person:
        return jsonify({"error": "old_path and new_person are required"}), 400

    full_old = os.path.join(temp_output, old_path)
    if not os.path.isfile(full_old):
        return jsonify({"error": f"File not found: {old_path}"}), 404

    ext = os.path.splitext(full_old)[1] or ".pdf"

    # Import domain resolver from classifier
    from classifier.agent import _resolve_domain_prefix, _sanitize_name

    doc_type = _sanitize_name(new_doc_type, "DOCUMENT") if new_doc_type else "DOCUMENT"
    person_clean = _sanitize_name(new_person, "UNKNOWN PERSON")
    domain = _resolve_domain_prefix(doc_type)
    pname = person_clean.replace(" ", "_")
    stem = f"{domain}_{pname}_{doc_type}"

    # Create new person directory
    new_person_dir = os.path.join(temp_output, person_clean)
    os.makedirs(new_person_dir, exist_ok=True)
    
    # Pick a unique destination name, but don't increment if the "collision" is just the source file itself
    new_path = os.path.join(new_person_dir, f"{stem}{ext}")
    idx = 1
    while os.path.exists(new_path):
        try:
            if os.path.samefile(full_old, new_path):
                break  # The file already has this name, no collision
        except OSError:
            pass
        new_path = os.path.join(new_person_dir, f"{stem} ({idx}){ext}")
        idx += 1

    # Only move if the path actually changed
    if not (os.path.exists(new_path) and os.path.exists(full_old) and os.path.samefile(full_old, new_path)):
        try:
            shutil.move(full_old, new_path)
        except getattr(__builtins__, "FileNotFoundError", OSError):
            return jsonify({"error": f"File already moved or not found: {old_path}"}), 404

    # Clean up empty old directory
    old_dir = os.path.dirname(full_old)
    if os.path.isdir(old_dir) and not os.listdir(old_dir):
        os.rmdir(old_dir)

    new_rel = os.path.relpath(new_path, temp_output).replace("\\", "/")
    return jsonify({
        "status": "renamed",
        "old_path": old_path,
        "new_path": new_rel,
        "person_name": person_clean,
        "doc_type_en": doc_type,
    })






@pipeline_classifier_bp.post("/api/classifier/split_manual")
def split_manual():
    """Manual PDF splitting. Outputs go to splitter_outputs/manual_<uuid>/.
    If source_file_id + source_filename are provided (from AI results),
    the original AI file is removed from splitter_outputs so it won't be
    transferred to classifier (only the manually split files will be)."""
    payload = request.get_json(force=True) or {}
    # Source can be from AI results or from uploaded file
    source_file_id = (payload.get("source_file_id") or "").strip()
    source_filename = (payload.get("source_filename") or "").strip()
    # Legacy support: direct source path
    input_dir = payload.get("input_dir", Config.CLASSIFIER_INPUT_DIR)
    source = (payload.get("source") or "").strip()
    project_id = payload.get("project_id")
    segments = payload.get("segments") or []

    if not isinstance(segments, list) or not segments:
        return jsonify({"error": "missing_segments"}), 400

    # Determine source PDF path
    src_path = None
    if source_file_id and source_filename:
        # Source from AI splitter output
        candidate = SPLITTER_OUTPUT_DIR / source_file_id / source_filename
        if candidate.is_file():
            src_path = str(candidate)
    if not src_path and source:
        # Legacy: from input_dir
        try:
            src_path = _safe_join(input_dir, source)
        except ValueError:
            return jsonify({"error": "invalid_source"}), 400

    if not src_path or not os.path.exists(src_path):
        return jsonify({"error": "source_not_found"}), 404
    if os.path.splitext(src_path)[1].lower() != ".pdf":
        return jsonify({"error": "source_not_pdf"}), 400

    try:
        reader = PdfReader(src_path)
    except Exception as exc:
        logging.exception("[Safe Log] Unhandled exception in pipeline_classifier.py: %s", exc)
        return jsonify({"error": "read_pdf_failed", "detail": str(exc)}), 500

    total_pages = len(reader.pages)

    # Output goes to splitter_outputs/manual_<uuid>/
    manual_id = f"manual_{uuid.uuid4().hex[:8]}"
    output_dir = str(SPLITTER_OUTPUT_DIR / manual_id)
    os.makedirs(output_dir, exist_ok=True)

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
        except Exception as e:
            logging.exception("[Safe Log] Unhandled exception in pipeline_classifier.py: %s", e)
            logging.debug("Skipped: %s", e)
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
        except Exception as e:
            logging.exception("[Safe Log] Unhandled exception in pipeline_classifier.py: %s", e)
            logging.debug("Skipped: %s", e)
            continue
        created.append(
            {
                "output_name": name,
                "start_page": s,
                "end_page": e,
                "to": os.path.relpath(out_path, output_dir).replace("\\", "/"),
            }
        )

    # If splitting from AI result, remove the original AI file so it won't be
    # transferred to classifier (only the new manual splits will be transferred).
    removed_original = None
    if source_file_id and source_filename and created:
        original_path = SPLITTER_OUTPUT_DIR / source_file_id / source_filename
        if original_path.is_file():
            os.remove(str(original_path))
            removed_original = source_filename

    # Save source metadata for persistent display
    if created:
        src_display = source_filename or source or "unknown"
        source_meta = {"source_filename": src_display, "source_type": "manual"}

        # Normalise project_id to int if possible
        if isinstance(project_id, int):
            pid = project_id
        elif isinstance(project_id, str) and project_id.isdigit():
            pid = int(project_id)
        else:
            pid = None
        if pid is not None:
            source_meta["project_id"] = pid

        with open(os.path.join(output_dir, "_source.json"), "w", encoding="utf-8") as mf:
            json.dump(source_meta, mf, ensure_ascii=False)

    return jsonify(
        {
            "status": "done",
            "manual_id": manual_id,
            "output_dir": output_dir,
            "source": source or source_filename,
            "total_pages": total_pages,
            "segments": created,
            "removed_original": removed_original,
        }
    )


def _pdf_merge_sanitize_name(value: str, fallback: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback


def _pdf_merge_pick_unique(dest_dir: str, stem: str, ext: str) -> str:
    candidate = os.path.join(dest_dir, f"{stem}{ext}")
    idx = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
        idx += 1
    return candidate


