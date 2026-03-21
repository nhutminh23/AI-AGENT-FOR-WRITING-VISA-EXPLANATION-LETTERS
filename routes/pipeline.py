"""
Pipeline routes: classifier, scan-splitter, pdf-tools, itinerary, run.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import re
import shutil
import tempfile
import traceback
import uuid
import zipfile
from pathlib import Path as SplitterPath
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, Response, jsonify, request, send_file, send_from_directory

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pypdf import PdfReader, PdfWriter

import database as db
from core.agents import detect_domain
from core.errors import QuotaExhaustedError, is_quota_error
from core.helpers import get_text_model, get_vision_model, list_input_files, cache_dir
from config import Config

pipeline_bp = Blueprint("pipeline", __name__)

# Base directory (project root, one level up from routes/)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUTPUT_DIR = os.path.join(_BASE_DIR, "output")


# get_text_model, get_vision_model, list_input_files, cache_dir → imported from core.helpers

STEP_ORDER = ["ingest", "summary", "writer"]


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
            errors.append({"file": fname, "error": str(e)})

    # Delete the original file if at least 1 split file was saved
    deleted_original = False
    if saved:
        try:
            os.remove(original_path)
            deleted_original = True
        except Exception as e:
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


@pipeline_bp.get("/api/classifier/files")
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


@pipeline_bp.post("/api/classifier/delete")
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


@pipeline_bp.post("/api/classifier/delete-all")
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


@pipeline_bp.post("/api/classifier/run")
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

@pipeline_bp.get("/api/classifier/last-result")
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


@pipeline_bp.post("/api/classifier/save-output")
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
        logging.debug("Ignored: %s", e)

    # Optional: clean input files too
    clean_input = payload.get("clean_input", False)
    input_dir = payload.get("input_dir", Config.CLASSIFIER_INPUT_DIR)
    if clean_input and os.path.isdir(input_dir):
        try:
            shutil.rmtree(input_dir)
            os.makedirs(input_dir, exist_ok=True)
        except Exception as e:
            logging.debug("Ignored: %s", e)

    return jsonify({"status": "saved", "output_dir": final_output, "file_count": count})


@pipeline_bp.post("/api/classifier/rename-file")
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
        print(f"[SCAN-SPLITTER] ❌ Vision batch error: {e}")
        return []


@pipeline_bp.post("/api/scan-splitter/split")
def scan_splitter_split():
    """Upload a scanned PDF, detect translation certification pages, and split."""
    import fitz
    import base64
    global _scan_split_progress

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported"}), 400

    # Save uploaded file to temp
    scan_output_dir = Config.SCAN_SPLITTER_OUTPUTS_DIR
    os.makedirs(scan_output_dir, exist_ok=True)

    original_name = file.filename
    stem = os.path.splitext(original_name)[0]
    temp_pdf = os.path.join(scan_output_dir, f"_src_{original_name}")
    file.save(temp_pdf)

    # Reset progress
    _scan_split_progress = {"total": 0, "done": 0, "current_page": "", "running": True, "results": [], "error": ""}

    def _do_scan_split():
        global _scan_split_progress
        try:
            doc = fitz.open(temp_pdf)
            total_pages = len(doc)
            _scan_split_progress["total"] = total_pages

            # Phase 1: Detect certification pages
            # Step 1a: Quick text-based pass (free, instant)
            cert_pages = set()  # 0-indexed
            needs_vision = []   # pages that need vision check
            for i in range(total_pages):
                page = doc[i]
                page_text = page.get_text() or ""
                if _is_certification_page_by_text(page_text):
                    cert_pages.add(i)
                else:
                    needs_vision.append(i)

            print(f"[SCAN-SPLITTER] Text scan done: {len(cert_pages)} cert pages found by text, {len(needs_vision)} pages need vision check")
            _scan_split_progress["current_page"] = f"Text scan xong. {len(cert_pages)} trang xác nhận tìm thấy. Đang quét ảnh {len(needs_vision)} trang còn lại..."
            _scan_split_progress["done"] = len(cert_pages)

            # Step 1b: Batch vision for remaining pages (8 pages per API call, ALL PARALLEL)
            if needs_vision:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                llm = _get_or_create_llm()
                BATCH_SIZE = 8

                # Phase A: Pre-render ALL page images (CPU work, fast)
                _scan_split_progress["current_page"] = "📸 Đang render ảnh tất cả trang..."
                all_images = {}  # idx -> (b64, page_num_1indexed)
                for idx in needs_vision:
                    try:
                        page = doc[idx]
                        rect = page.rect
                        clip = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + rect.height / 2)
                        pix = page.get_pixmap(dpi=100, clip=clip)
                        img_bytes = pix.tobytes("png")
                        b64 = base64.b64encode(img_bytes).decode()
                        all_images[idx] = (b64, idx + 1)
                    except Exception as e:
                        print(f"[SCAN-SPLITTER] ❌ Error rendering page {idx}: {e}")

                # Phase B: Build batches and send ALL to vision API concurrently
                batches = []
                for batch_start in range(0, len(needs_vision), BATCH_SIZE):
                    batch_indices = needs_vision[batch_start:batch_start + BATCH_SIZE]
                    batch_images = []
                    batch_page_nums = []
                    for idx in batch_indices:
                        if idx in all_images:
                            b64, pnum = all_images[idx]
                            batch_images.append(b64)
                            batch_page_nums.append(pnum)
                    if batch_images:
                        batches.append((batch_images, batch_page_nums))

                total_batches = len(batches)
                _scan_split_progress["current_page"] = f"🔍 Đang gửi {total_batches} batch song song đến AI..."
                print(f"[SCAN-SPLITTER] 🚀 Sending {total_batches} batches in PARALLEL ({len(all_images)} pages total)")

                def _process_batch(batch_idx, images, page_nums):
                    """Worker: send one batch to vision API."""
                    found = _batch_detect_cert_pages_vision(llm, images, page_nums)
                    print(f"[SCAN-SPLITTER] ✅ Batch {batch_idx+1}/{total_batches} done: cert_pages={found}")
                    return found

                # Fire all batches concurrently (max 4 parallel to avoid rate limits)
                with ThreadPoolExecutor(max_workers=min(4, total_batches)) as executor:
                    futures = {
                        executor.submit(_process_batch, i, imgs, pnums): i
                        for i, (imgs, pnums) in enumerate(batches)
                    }
                    done_count = 0
                    for future in as_completed(futures):
                        done_count += 1
                        _scan_split_progress["current_page"] = f"🔍 Hoàn tất {done_count}/{total_batches} batch..."
                        _scan_split_progress["done"] = len(cert_pages) + done_count * BATCH_SIZE
                        try:
                            found_pages = future.result()
                            for pnum in found_pages:
                                cert_pages.add(pnum - 1)  # Convert back to 0-indexed
                        except Exception as e:
                            print(f"[SCAN-SPLITTER] ❌ Batch error: {e}")

            cert_pages = sorted(cert_pages)

            # Phase 2: Split PDF at certification boundaries
            # Each certification page = last page of a document group
            # Pages after last cert until next cert = one document
            _scan_split_progress["current_page"] = "Đang tách file..."

            if not cert_pages:
                _scan_split_progress["error"] = "Không tìm thấy trang xác nhận dịch nào trong file này."
                _scan_split_progress["running"] = False
                doc.close()
                return

            # Clean old output files (except source)
            for f in os.listdir(scan_output_dir):
                fp = os.path.join(scan_output_dir, f)
                if os.path.isfile(fp) and not f.startswith("_src_"):
                    os.remove(fp)

            results = []
            doc_start = 0
            for doc_idx, cert_page_idx in enumerate(cert_pages):
                doc_end = cert_page_idx  # inclusive
                page_range = f"{doc_start + 1}-{doc_end + 1}"
                out_name = f"{stem}_part{doc_idx + 1}_p{doc_start + 1}-{doc_end + 1}.pdf"
                out_path = os.path.join(scan_output_dir, out_name)

                # Create new PDF with these pages
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=doc_start, to_page=doc_end)
                new_doc.save(out_path)
                new_doc.close()

                results.append({
                    "filename": out_name,
                    "pages": page_range,
                    "page_count": doc_end - doc_start + 1,
                    "start_page": doc_start + 1,
                    "end_page": doc_end + 1,
                })
                doc_start = cert_page_idx + 1

            # Handle remaining pages after last certification (if any)
            if doc_start < total_pages:
                page_range = f"{doc_start + 1}-{total_pages}"
                out_name = f"{stem}_part{len(cert_pages) + 1}_p{doc_start + 1}-{total_pages}.pdf"
                out_path = os.path.join(scan_output_dir, out_name)

                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=doc_start, to_page=total_pages - 1)
                new_doc.save(out_path)
                new_doc.close()

                results.append({
                    "filename": out_name,
                    "pages": page_range,
                    "page_count": total_pages - doc_start,
                    "start_page": doc_start + 1,
                    "end_page": total_pages,
                    "no_cert": True,  # Flag: these pages had no certification
                })

            doc.close()
            _scan_split_progress["results"] = results
            _scan_split_progress["done"] = total_pages
            _scan_split_progress["current_page"] = f"Hoàn tất! Tách thành {len(results)} file."
            _scan_split_progress["running"] = False

        except Exception as e:
            _scan_split_progress["error"] = str(e)
            _scan_split_progress["running"] = False

    # Run in background thread
    import threading
    t = threading.Thread(target=_do_scan_split, daemon=True)
    t.start()

    return jsonify({"status": "started", "filename": original_name})


@pipeline_bp.get("/api/scan-splitter/progress")
def scan_splitter_progress():
    """Polling endpoint for scan split progress."""
    return jsonify(_scan_split_progress)


@pipeline_bp.get("/api/scan-splitter/download/<path:filename>")
def scan_splitter_download(filename):
    """Download a single split file."""
    scan_output_dir = Config.SCAN_SPLITTER_OUTPUTS_DIR
    fpath = os.path.join(scan_output_dir, filename)
    if not os.path.isfile(fpath):
        return jsonify({"error": "File not found"}), 404
    return send_file(fpath, as_attachment=True, download_name=filename)


@pipeline_bp.get("/api/scan-splitter/view/<path:filename>")
def scan_splitter_view(filename):
    """View a single split file inline in browser."""
    scan_output_dir = Config.SCAN_SPLITTER_OUTPUTS_DIR
    fpath = os.path.join(scan_output_dir, filename)
    if not os.path.isfile(fpath):
        return jsonify({"error": "File not found"}), 404
    return send_file(fpath, as_attachment=False, mimetype="application/pdf")


@pipeline_bp.get("/api/scan-splitter/download-zip")
def scan_splitter_download_zip():
    """Download all split files as ZIP."""
    import zipfile
    import io
    scan_output_dir = Config.SCAN_SPLITTER_OUTPUTS_DIR
    if not os.path.isdir(scan_output_dir):
        return jsonify({"error": "No output files"}), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(scan_output_dir)):
            if f.startswith("_src_"):
                continue
            fp = os.path.join(scan_output_dir, f)
            if os.path.isfile(fp) and f.endswith(".pdf"):
                zf.write(fp, f)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name="scan_split_results.zip")


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


@pipeline_bp.post("/api/classifier/split_manual")
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


@pipeline_bp.route("/api/pdf/merge-upload", methods=["POST"])
def merge_pdf_upload():
    """Merge PDFs uploaded from user's computer. Order of form fields = page order."""
    output_dir = Config.PDF_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    output_name = (request.form.get("output_name") or "").strip()
    if not output_name:
        return jsonify({"error": "missing_output_name"}), 400

    files = request.files.getlist("file")
    if not files:
        return jsonify({"error": "missing_files"}), 400

    writer = PdfWriter()
    total_pages = 0
    used_names: List[str] = []

    for f in files:
        if not f or not getattr(f, "filename", None):
            continue
        if not str(f.filename).lower().endswith(".pdf"):
            continue
        try:
            reader = PdfReader(f.stream)
        except Exception as e:
            logging.debug("Skipped: %s", e)
            continue
        for page in reader.pages:
            writer.add_page(page)
            total_pages += 1
        used_names.append(f.filename)

    if not used_names:
        return jsonify({"error": "no_valid_pdfs"}), 400

    safe_name = _pdf_merge_sanitize_name(output_name, "MERGED")
    out_path = _pdf_merge_pick_unique(output_dir, safe_name, ".pdf")
    try:
        with open(out_path, "wb") as fp:
            writer.write(fp)
    except Exception as exc:
        return jsonify({"error": "write_failed", "detail": str(exc)}), 500

    return jsonify(
        {
            "status": "done",
            "output_dir": output_dir,
            "files": used_names,
            "file_count": len(used_names),
            "total_pages": total_pages,
            "output_file": os.path.relpath(out_path, output_dir).replace("\\", "/"),
        }
    )


@pipeline_bp.route("/api/pdf/merge", methods=["POST"])
def merge_pdf():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", Config.INPUT_DIR)
    output_dir = payload.get("output_dir", Config.PDF_OUTPUT_DIR)
    files = payload.get("files") or []
    output_name = (payload.get("output_name") or "").strip()

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404
    os.makedirs(output_dir, exist_ok=True)

    if not isinstance(files, list) or not files:
        return jsonify({"error": "missing_files"}), 400
    if not output_name:
        return jsonify({"error": "missing_output_name"}), 400

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
        except Exception as e:
            logging.debug("Skipped: %s", e)
            continue
        for page in reader.pages:
            writer.add_page(page)
            total_pages += 1
        used_files.append(os.path.relpath(src_path, input_dir).replace("\\", "/"))

    if not used_files:
        return jsonify({"error": "no_valid_pdfs"}), 400

    safe_name = _pdf_merge_sanitize_name(output_name, "MERGED")
    out_path = _pdf_merge_pick_unique(output_dir, safe_name, ".pdf")
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


@pipeline_bp.route("/api/pdf/rename", methods=["POST"])
def rename_pdf():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", Config.INPUT_DIR)
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


@pipeline_bp.route("/api/pdf/rename_suggest_name", methods=["POST"])
def pdf_rename_suggest_name():
    payload = request.get_json(force=True) or {}
    input_text = (payload.get("input_text") or "").strip()
    model = payload.get("model") or get_text_model()  # text analysis

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
        if _is_quota_error(exc):
            return jsonify({"error": "quota_exceeded", "detail": "⚠️ Đã hết quota OpenAI API! Vui lòng kiểm tra billing."}), 429
        return jsonify({"error": "llm_error", "detail": str(exc)}), 500

    suggested = (getattr(result, "content", "") or "").strip().upper()
    suggested = re.sub(r"[^A-Z0-9\s]", " ", suggested)
    suggested = re.sub(r"\s+", " ", suggested).strip()

    if not suggested:
        return jsonify({"error": "empty_suggestion"}), 500

    return jsonify({"suggested_name": suggested})


@pipeline_bp.route("/api/pdf/extract-objects", methods=["POST"])
def extract_pdf_objects():
    """Extract text blocks from PDF with bbox, font, size, color info."""
    import fitz
    import io

    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_a_pdf"}), 400

    try:
        pdf_bytes = f.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page_idx, page in enumerate(doc):
            rect = page.rect
            page_info = {
                "pageIndex": page_idx,
                "width": rect.width,
                "height": rect.height,
                "blocks": [],
            }
            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:  # text block only
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        c = span.get("color", 0)
                        if isinstance(c, int):
                            color_hex = "#{:06x}".format(c)
                        else:
                            color_hex = "#000000"
                        flags = span.get("flags", 0)
                        page_info["blocks"].append({
                            "text": text,
                            "bbox": list(bbox),
                            "font": span.get("font", ""),
                            "fontSize": round(span.get("size", 12), 1),
                            "color": color_hex,
                            "bold": bool(flags & 16),
                            "italic": bool(flags & 2),
                        })
            pages.append(page_info)
        doc.close()
        return jsonify({"pages": pages})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# Mapping common PDF font names to PyMuPDF built-in fonts
_FONT_MAP = {
    "helv": "helv", "helvetica": "helv", "arial": "helv",
    "arialmt": "helv", "arial-boldmt": "hebo",
    "tiro": "tiro", "times": "tiro", "timesnewroman": "tiro",
    "timesnewromanpsmt": "tiro", "timesnewromanps-boldmt": "tibo",
    "cour": "cour", "courier": "cour", "couriernew": "cour",
    "couriernewpsmt": "cour",
    "symbol": "symb", "zapfdingbats": "zadb",
}

def _resolve_font(pdf_font_name, is_bold=False, is_italic=False):
    """Map a PDF font name to a PyMuPDF built-in font name, preserving bold/italic."""
    if not pdf_font_name:
        pdf_font_name = "helv"
    key = pdf_font_name.lower().replace(" ", "").replace("-", "")

    # Detect bold/italic from font name itself
    name_bold = "bold" in key or is_bold
    name_italic = ("italic" in key or "oblique" in key) or is_italic

    # Find base font family
    base = "helv"  # default
    if key in _FONT_MAP:
        base = _FONT_MAP[key]
    else:
        for k, v in _FONT_MAP.items():
            if k in key:
                base = v
                break

    # Pick bold/italic variant based on base font family
    # Helvetica family: helv, hebo, heit, hebi
    # Times family: tiro, tibo, tiit, tibi
    # Courier family: cour, cobo, coit, cobi
    family_variants = {
        "helv": {"b": "hebo", "i": "heit", "bi": "hebi"},
        "hebo": {"b": "hebo", "i": "hebi", "bi": "hebi"},
        "heit": {"b": "hebi", "i": "heit", "bi": "hebi"},
        "hebi": {"b": "hebi", "i": "hebi", "bi": "hebi"},
        "tiro": {"b": "tibo", "i": "tiit", "bi": "tibi"},
        "tibo": {"b": "tibo", "i": "tibi", "bi": "tibi"},
        "tiit": {"b": "tibi", "i": "tiit", "bi": "tibi"},
        "tibi": {"b": "tibi", "i": "tibi", "bi": "tibi"},
        "cour": {"b": "cobo", "i": "coit", "bi": "cobi"},
        "cobo": {"b": "cobo", "i": "cobi", "bi": "cobi"},
        "coit": {"b": "cobi", "i": "coit", "bi": "cobi"},
        "cobi": {"b": "cobi", "i": "cobi", "bi": "cobi"},
    }

    if name_bold and name_italic:
        return family_variants.get(base, {}).get("bi", base)
    if name_bold:
        return family_variants.get(base, {}).get("b", base)
    if name_italic:
        return family_variants.get(base, {}).get("i", base)
    return base


@pipeline_bp.route("/api/pdf/edit", methods=["POST"])
def edit_pdf():
    """Find & replace text in an uploaded PDF using PyMuPDF."""
    import fitz
    import json as _json
    import io

    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400
    f = request.files["file"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_a_pdf"}), 400

    raw_replacements = request.form.get("replacements", "[]")
    try:
        replacements = _json.loads(raw_replacements)
    except Exception as e:
        return jsonify({"error": "invalid_replacements_json"}), 400

    if not replacements or not isinstance(replacements, list):
        return jsonify({"error": "empty_replacements"}), 400

    try:
        pdf_bytes = f.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        for pair in replacements:
            find_text = pair.get("find", "")
            replace_text = pair.get("replace", "")
            if not find_text:
                continue

            # Use fontname from request if provided, else detect from PDF
            req_font = pair.get("fontname", "")

            for page in doc:
                hits = page.search_for(find_text)
                if not hits:
                    continue

                # Detect font info from the first hit's span
                span_font = req_font or "helv"
                span_color = (0, 0, 0)
                span_size = 0
                span_bold = False
                span_italic = False
                try:
                    text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
                    for block in text_dict.get("blocks", []):
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                if find_text in span.get("text", ""):
                                    if not req_font:
                                        span_font = span.get("font", "helv")
                                    span_size = span.get("size", 0)
                                    sflags = span.get("flags", 0)
                                    span_bold = bool(sflags & 16)
                                    span_italic = bool(sflags & 2)
                                    c = span.get("color", 0)
                                    if isinstance(c, int):
                                        span_color = (
                                            ((c >> 16) & 0xFF) / 255.0,
                                            ((c >> 8) & 0xFF) / 255.0,
                                            (c & 0xFF) / 255.0,
                                        )
                                    raise StopIteration
                except StopIteration:
                    pass

                # Try to extract & register the actual embedded font from the PDF
                use_fontname = None
                use_fontfile = None
                print(f"[PDF-EDIT] Detected font='{span_font}', size={span_size}, color={span_color}")
                try:
                    page_fonts = page.get_fonts(full=True)
                    print(f"[PDF-EDIT] Page fonts: {[(name, basefont) for xref, ext, ftype, basefont, name, enc in page_fonts]}")
                    for xref, ext, ftype, basefont, name, enc in page_fonts:
                        if name == span_font or basefont == span_font:
                            font_data = doc.extract_font(xref)
                            # font_data = (basename, ext, subtype, buffer)
                            if font_data and len(font_data) >= 4 and font_data[3]:
                                buf = font_data[3]
                                print(f"[PDF-EDIT] ✅ Extracted font '{name}' ({len(buf)} bytes), re-registering...")
                                # Register extracted font on the page
                                registered = page.insert_font(
                                    fontname=name or basefont,
                                    fontbuffer=buf,
                                )
                                use_fontname = registered
                                print(f"[PDF-EDIT] ✅ Registered as '{use_fontname}'")
                            else:
                                print(f"[PDF-EDIT] ⚠️ Font '{name}' found but no buffer data")
                            break
                except Exception as font_err:
                    print(f"[PDF-EDIT] ❌ Font extraction failed: {font_err}")

                # Fallback to built-in font mapping
                if not use_fontname:
                    use_fontname = _resolve_font(span_font, is_bold=span_bold, is_italic=span_italic)
                    print(f"[PDF-EDIT] ⚠️ Fallback to built-in font: '{span_font}' (bold={span_bold}, italic={span_italic}) → '{use_fontname}'")

                # Collect rects for redaction + text insertion
                insert_jobs = []
                for rect in hits:
                    fontsize = span_size if span_size > 4 else rect.height * 0.75
                    if fontsize < 4:
                        fontsize = 10
                    # Add redaction annotation WITHOUT fill (preserves background)
                    page.add_redact_annot(rect, fill=False)
                    insert_jobs.append((rect, fontsize))

                # Apply all redactions (removes text, keeps background)
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

                # Insert new text at original positions
                for rect, fontsize in insert_jobs:
                    page.insert_text(
                        fitz.Point(rect.x0, rect.y0 + rect.height * 0.8),
                        replace_text,
                        fontname=use_fontname,
                        fontsize=fontsize,
                        color=span_color,
                    )

        out_buf = io.BytesIO()
        doc.save(out_buf, garbage=4, deflate=True)
        doc.close()
        out_buf.seek(0)

        from flask import send_file
        return send_file(
            out_buf,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=f.filename.replace(".pdf", "_edited.pdf"),
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


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


@pipeline_bp.get("/api/itinerary/latest")
def get_itinerary_latest():
    project_id = request.args.get("project_id", type=int)
    if project_id:
        it = db.get_latest_itinerary(project_id)
        return jsonify({"itinerary": it["html_content"] if it else ""})
    output_path = request.args.get("output", os.path.join("output", "itinerary.html"))
    # Priority: output file (user-editable) → cache file (AI-generated)
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            return jsonify({"itinerary": f.read()})
    cache_dir = _cache_dir(output_path)
    path = os.path.join(cache_dir, "itinerary.html")
    if not os.path.exists(path):
        return jsonify({"itinerary": ""})
    with open(path, "r", encoding="utf-8") as f:
        return jsonify({"itinerary": f.read()})


@pipeline_bp.get("/api/itinerary/context/latest")
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
    additional_info = (form_data.get("additional_info") or "").strip()
    travel_purpose = (form_data.get("travel_purpose") or "").strip()
    start_date = (form_data.get("travel_start_date") or "").strip()
    end_date = (form_data.get("travel_end_date") or "").strip()
    has_any_value = any(
        [
            participants,
            additional_info,
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
    if additional_info:
        lines.append(f"- Additional information: {additional_info}")
    if start_date and end_date:
        lines.append(f"- Travel period: From {start_date} to {end_date}")
    elif start_date:
        lines.append(f"- travel_start_date: {start_date}")
    elif end_date:
        lines.append(f"- travel_end_date: {end_date}")
    if travel_purpose:
        lines.append(f"- Purpose of travel: {travel_purpose}")

    return "\n".join(lines).strip()


@pipeline_bp.route("/api/itinerary/context/save", methods=["POST"])
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


@pipeline_bp.post("/api/itinerary/run")
def run_itinerary():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "itinerary.html"))
    flight_file = payload.get("flight_file")
    hotel_file = payload.get("hotel_file")
    from_db = payload.get("from_db", False)
    model = payload.get("model") or get_text_model()  # itinerary generation (text reasoning)
    project_id = payload.get("project_id")

    cache_dir = _cache_dir(output_path)
    summary_profile = (payload.get("summary_profile") or "").strip()
    if not summary_profile:
        summary_path = os.path.join(cache_dir, "itinerary_summary.txt")
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_profile = f.read().strip()
    # Only fall back to DB trip info when explicitly using DB mode
    if not summary_profile and from_db and project_id:
        ti = db.get_latest_trip_info(int(project_id))
        if ti and ti.get("data"):
            d = ti["data"]
            parts = []
            if d.get("guest_names"):
                names = d["guest_names"] if isinstance(d["guest_names"], list) else [d["guest_names"]]
                parts.append("- participants: " + ", ".join(str(n) for n in names))
            if d.get("travel_start_date"):
                parts.append(f"- travel_start_date: {d['travel_start_date']}")
            if d.get("travel_end_date"):
                parts.append(f"- travel_end_date: {d['travel_end_date']}")
            if d.get("travel_purpose"):
                parts.append(f"- travel_purpose: {d['travel_purpose']}")
            if parts:
                summary_profile = "\n".join(parts)
    if not summary_profile:
        summary_profile = "Create itinerary from the provided flight and hotel booking data."

    llm = ChatOpenAI(model=model, temperature=0)

    # ── Load flight/hotel text from DB or files ──
    if from_db and project_id:
        booking = db.get_latest_booking(int(project_id))
        if not booking:
            return jsonify({"error": "no_booking_in_db", "message": "Không tìm thấy booking trong database. Hãy tạo booking AI trước."}), 400
        # Extract text from HTML (strip tags for AI processing)
        import re as _re_it
        def _html_to_text(html_str):
            text = _re_it.sub(r'<style[^>]*>.*?</style>', '', html_str, flags=_re_it.DOTALL)
            text = _re_it.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re_it.DOTALL)
            text = _re_it.sub(r'<[^>]+>', ' ', text)
            text = _re_it.sub(r'\s+', ' ', text).strip()
            return text

        flight_text = _html_to_text(booking.get("flight_html", ""))
        # Combine all hotel HTMLs
        hotel_htmls = booking.get("hotel_htmls", [])
        hotel_text = "\n\n---\n\n".join(_html_to_text(h) for h in hotel_htmls)
    else:
        # New: accept HTML content directly from browser file upload
        uploaded_flight_html = payload.get("flight_html")
        uploaded_hotel_htmls = payload.get("hotel_htmls")  # list of HTML strings
        if uploaded_flight_html and uploaded_hotel_htmls:
            flight_text = _html_to_text(uploaded_flight_html)
            hotel_text = "\n\n---\n\n".join(_html_to_text(h) for h in uploaded_hotel_htmls)
        elif flight_file and hotel_file:
            flight_path = _resolve_input_file_path(input_dir, str(flight_file))
            hotel_path = _resolve_input_file_path(input_dir, str(hotel_file))
            if not flight_path or not hotel_path:
                return jsonify({"error": "missing_files"}), 400
            flight_text = extract_text_with_openai(llm, flight_path)
            hotel_text = extract_text_with_openai(llm, hotel_path)
        else:
            return jsonify({"error": "missing_files"}), 400

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


@pipeline_bp.post("/api/itinerary/run_stream")
def run_itinerary_stream():
    """Generate itinerary with SSE progress streaming."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    output_path = payload.get("output", os.path.join("output", "itinerary.html"))
    flight_file = payload.get("flight_file")
    hotel_file = payload.get("hotel_file")
    # New: accept HTML content directly from browser file upload
    uploaded_flight_html = payload.get("flight_html")
    uploaded_hotel_htmls = payload.get("hotel_htmls")  # list of HTML strings
    from_db = payload.get("from_db", False)
    model = payload.get("model") or get_text_model()
    project_id = payload.get("project_id")

    def generate():
        def send_event(step, msg, data=None):
            evt = {"step": step, "msg": msg}
            if data is not None:
                evt["data"] = data
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

        # Build summary profile
        cache_dir = _cache_dir(output_path)
        summary_profile = (payload.get("summary_profile") or "").strip()
        if not summary_profile:
            summary_path = os.path.join(cache_dir, "itinerary_summary.txt")
            if os.path.exists(summary_path):
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary_profile = f.read().strip()
        # Only fall back to DB trip info when explicitly using DB mode
        if not summary_profile and from_db and project_id:
            ti = db.get_latest_trip_info(int(project_id))
            if ti and ti.get("data"):
                d = ti["data"]
                parts = []
                if d.get("guest_names"):
                    names = d["guest_names"] if isinstance(d["guest_names"], list) else [d["guest_names"]]
                    parts.append("- participants: " + ", ".join(str(n) for n in names))
                if d.get("travel_start_date"):
                    parts.append(f"- travel_start_date: {d['travel_start_date']}")
                if d.get("travel_end_date"):
                    parts.append(f"- travel_end_date: {d['travel_end_date']}")
                if d.get("travel_purpose"):
                    parts.append(f"- travel_purpose: {d['travel_purpose']}")
                if parts:
                    summary_profile = "\n".join(parts)
        if not summary_profile:
            summary_profile = "Create itinerary from the provided flight and hotel booking data."

        llm = ChatOpenAI(model=model, temperature=0)

        try:
            # Step 1: Load booking data
            yield from send_event(1, "⏳ Đang tải dữ liệu booking...")

            import re as _re_it
            def _html_to_text(html_str):
                text = _re_it.sub(r'<style[^>]*>.*?</style>', '', html_str, flags=_re_it.DOTALL)
                text = _re_it.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re_it.DOTALL)
                text = _re_it.sub(r'<[^>]+>', ' ', text)
                text = _re_it.sub(r'\s+', ' ', text).strip()
                return text

            if from_db and project_id:
                booking = db.get_latest_booking(int(project_id))
                if not booking:
                    yield from send_event(-1, "❌ Không tìm thấy booking trong database")
                    return
                yield from send_event(1, "✅ Đã tải booking từ database")

                # Step 2: Extract text
                yield from send_event(2, "⏳ Đang trích xuất nội dung booking...")
                flight_text = _html_to_text(booking.get("flight_html", ""))
                hotel_htmls = booking.get("hotel_htmls", [])
                hotel_text = "\n\n---\n\n".join(_html_to_text(h) for h in hotel_htmls)
                yield from send_event(2, "✅ Trích xuất nội dung hoàn tất")
            else:
                # Option A: HTML content uploaded directly from browser
                if uploaded_flight_html and uploaded_hotel_htmls:
                    yield from send_event(1, "✅ Đã nhận file từ trình duyệt")
                    yield from send_event(2, "⏳ Đang trích xuất nội dung booking...")
                    flight_text = _html_to_text(uploaded_flight_html)
                    hotel_text = "\n\n---\n\n".join(_html_to_text(h) for h in uploaded_hotel_htmls)
                    yield from send_event(2, "✅ Trích xuất nội dung hoàn tất")
                # Option B: Legacy file path approach (backward compatible)
                elif flight_file and hotel_file:
                    flight_path = _resolve_input_file_path(input_dir, str(flight_file))
                    hotel_path = _resolve_input_file_path(input_dir, str(hotel_file))
                    if not flight_path or not hotel_path:
                        yield from send_event(-1, "❌ Không tìm thấy file đã chọn")
                        return
                    yield from send_event(1, "✅ Đã tìm thấy file")
                    yield from send_event(2, "⏳ AI đang đọc vé máy bay & khách sạn...")
                    flight_text = extract_text_with_openai(llm, flight_path)
                    hotel_text = extract_text_with_openai(llm, hotel_path)
                    yield from send_event(2, "✅ Đọc nội dung file hoàn tất")
                else:
                    yield from send_event(-1, "❌ Vui lòng chọn đủ file vé máy bay và khách sạn")
                    return

            # Step 3: Generate itinerary
            yield from send_event(3, "⏳ AI đang viết lịch trình chi tiết...")
            itinerary = itinerary_writer(llm, flight_text, hotel_text, summary_profile)
            yield from send_event(3, "✅ Viết lịch trình hoàn tất")

            # Step 4: Save
            yield from send_event(4, "⏳ Đang lưu kết quả...")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(itinerary)
            os.makedirs(cache_dir, exist_ok=True)
            with open(os.path.join(cache_dir, "itinerary.html"), "w", encoding="utf-8") as f:
                f.write(itinerary)
            if project_id:
                ctx = db.get_latest_itinerary_context(int(project_id)) or {}
                db.save_itinerary_html(int(project_id), ctx, itinerary)
            yield from send_event(4, "✅ Đã lưu")

            # Final result
            yield from send_event(5, "✅ Hoàn tất!", {"itinerary": itinerary, "output_path": output_path})

        except Exception as e:
            yield from send_event(-1, f"❌ Lỗi: {str(e)}")

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })
