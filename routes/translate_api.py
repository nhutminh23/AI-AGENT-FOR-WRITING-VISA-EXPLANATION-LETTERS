"""
Translation API routes: bilingual check, upload, pages, templates, CRUD flows,
workspace scan, save/rebuild HTML, output files.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path as SplitterPath
from typing import Dict, List

from flask import jsonify, request

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.errors import QuotaExhaustedError, is_quota_error
from config import Config
import database as db
from routes.translate_core import (
    splitter_translate_bp,
    _BASE_DIR,
    TRANSLATE_TEMPLATE_DIR,
    TRANSLATE_DEFAULT_TEMPLATE,
    TRANSLATE_OUTPUT_DIR,
    TRANSLATE_HTML_SAVE_DIR,
    TRANSLATION_ORIGINALS_DIR,
    SCAN_EXTS,
    translation_upload_cache,
    _is_quota_error,
    _safe_name,
    _resolve_translate_source_path,
    _check_single_file_bilingual,
    _should_skip_by_filename,
    _ensure_translate_template_dir,
    _auto_detect_template,
    _build_translation_html,
    _embed_template_images,
    _convert_image_to_a4_pdf,
    _cleanup_original_file,
)


# =====================================================================
# Translation Workspace APIs (Auto-download from Drive)
# =====================================================================

@splitter_translate_bp.get("/api/translate/workspaces")
def list_translation_workspaces():
    """List all translation workspaces (auto-downloaded from Drive).

    Returns folders in ``translation_workspace/`` that have ``_files_meta.json``.
    Each entry includes the customer name, file count, and Drive folder IDs.
    """
    workspace_root = SplitterPath(Config.TRANSLATION_WORKSPACE_DIR)

    if not workspace_root.is_dir():
        return jsonify({"workspaces": []})

    workspaces = []
    for item in sorted(os.listdir(workspace_root)):
        item_path = workspace_root / item
        if not item_path.is_dir():
            continue

        meta_path = item_path / "_files_meta.json"
        if not meta_path.is_file():
            continue

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # Count actual files (skip _files_meta.json, hidden files, and Translate folder contents)
        file_count = 0
        for root, dirs, files in os.walk(item_path):
            # Skip Translate folder for counting (it's for output)
            rel = os.path.relpath(root, item_path)
            if rel.lower().startswith("translate"):
                continue
            for fn in files:
                if not fn.startswith(".") and not fn.startswith("_"):
                    file_count += 1

        workspaces.append({
            "dir_name": item,
            "local_path": str(item_path),
            "base_name": meta.get("base_name", item),
            "drive_folder_id": meta.get("drive_folder_id", ""),
            "root_folder_id": meta.get("root_folder_id", ""),
            "translate_folder_id": meta.get("translate_folder_id", ""),
            "file_count": file_count,
        })

    return jsonify({"workspaces": workspaces})


@splitter_translate_bp.post("/api/translate/workspace_scan")
def scan_workspace_for_translation():
    """Scan a workspace folder and auto-detect which files need translation.

    Expects JSON body: { "workspace": "ÚC - CHÚ HIỆP CÔ CHÍNH - NHÂN" }

    Reads all image/PDF files from the workspace (excluding Translate/ folder),
    runs bilingual detection on each, and returns categorized results.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from core.helpers import get_vision_model

    payload = request.get_json(force=True) or {}
    workspace_name = payload.get("workspace", "")

    if not workspace_name:
        return jsonify({"error": "missing_workspace"}), 400

    workspace_root = SplitterPath(Config.TRANSLATION_WORKSPACE_DIR)
    workspace_path = workspace_root / workspace_name

    if not workspace_path.is_dir():
        return jsonify({"error": "workspace_not_found", "path": str(workspace_path)}), 404

    # Read meta to get Drive file IDs for each document
    meta_path = workspace_path / "_files_meta.json"
    file_id_map = {}
    if meta_path.is_file():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        # Backward-compatible key support:
        # - new downloader writes `file_id_map`
        # - legacy snapshots may use `file_ids`
        file_id_map = meta.get("file_id_map") or meta.get("file_ids") or {}

    # Scan workspace for image/PDF files
    file_entries = []
    for root_dir, dirs, files in os.walk(workspace_path):
        rel_root = os.path.relpath(root_dir, workspace_path)
        # Skip the Translate output folder
        if rel_root.lower().startswith("translate"):
            continue

        for fn in sorted(files):
            if fn.startswith(".") or fn.startswith("_"):
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext not in SCAN_EXTS:
                continue

            abs_path = os.path.join(root_dir, fn)
            rel_path = os.path.relpath(abs_path, workspace_path).replace("\\", "/")

            # Look up Drive file ID from the meta mapping
            drive_file_id = file_id_map.get(rel_path, "")

            token = uuid.uuid4().hex
            # Save to persistent originals dir for subsequent translation
            out_name = f"translate_{token}{ext}"
            persist_path = os.path.join(TRANSLATION_ORIGINALS_DIR, out_name)
            
            import shutil
            shutil.copy2(abs_path, persist_path)
            translation_upload_cache[token] = {"temp_path": persist_path, "filename": fn}

            file_entries.append({
                "token": token,
                "path": abs_path,
                "filename": fn,
                "rel_path": rel_path,
                "drive_file_id": drive_file_id,
                "file_ref": f"upload_token:{token}",
            })

    if not file_entries:
        return jsonify({"error": "no_scannable_files", "detail": "No image/PDF files found in workspace"}), 400

    # Run bilingual detection in parallel
    llm = ChatOpenAI(model=get_vision_model(), temperature=0)
    results = [None] * len(file_entries)

    with ThreadPoolExecutor(max_workers=min(6, len(file_entries))) as executor:
        future_to_idx = {
            executor.submit(
                _check_single_file_bilingual,
                entry["path"], entry["filename"], llm
            ): i
            for i, entry in enumerate(file_entries)
        }

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result()
                result["upload_token"] = file_entries[idx]["token"]
                result["file_ref"] = file_entries[idx]["file_ref"]
                result["rel_path"] = file_entries[idx].get("rel_path", "")
                result["drive_file_id"] = file_entries[idx].get("drive_file_id", "")
                results[idx] = result
            except Exception as e:
                logging.exception("[Safe Log] Unhandled exception in workspace scan: %s", e)
                results[idx] = {
                    "filename": file_entries[idx]["filename"],
                    "rel_path": file_entries[idx].get("rel_path", ""),
                    "needs_translation": True,
                    "is_bilingual": False,
                    "reason": f"Error: {str(e)}",
                    "upload_token": file_entries[idx]["token"],
                    "file_ref": file_entries[idx]["file_ref"],
                    "drive_file_id": file_entries[idx].get("drive_file_id", ""),
                }

    needs_count = sum(1 for r in results if r and r.get("needs_translation"))
    bilingual_count = sum(1 for r in results if r and not r.get("needs_translation") and r.get("is_bilingual"))
    skipped_count = sum(1 for r in results if r and not r.get("needs_translation") and not r.get("is_bilingual"))

    return jsonify({
        "status": "success",
        "workspace": workspace_name,
        "total": len(results),
        "needs_translation": needs_count,
        "already_bilingual": bilingual_count,
        "skipped": skipped_count,
        "results": results,
    })


# =====================================================================
# Bilingual Check (file upload version)
# =====================================================================

@splitter_translate_bp.post("/api/translate/check_bilingual")
def check_bilingual():
    """Upload multiple files and check which ones need translation.
    
    OCRs only page 1 of each file for speed. Processes in parallel.
    Returns per-file results with bilingual status and upload tokens.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "no_files", "detail": "No files uploaded"}), 400
    
    # Save all files to temp and create upload tokens
    file_entries = []
    for f in files:
        if not f or not f.filename:
            continue
        orig_name = os.path.basename(f.filename)
        safe = _safe_name(orig_name).replace("..", ".")
        if not safe:
            continue
        
        base, ext = os.path.splitext(safe)
        ext = ext or ".bin"
        token = uuid.uuid4().hex
        out_name = f"translate_{token}{ext}"
        out_path = os.path.join(tempfile.gettempdir(), out_name)
        
        try:
            f.save(out_path)
            translation_upload_cache[token] = {"temp_path": out_path, "filename": safe}
            file_entries.append({
                "token": token, 
                "path": out_path, 
                "filename": safe,
                "file_ref": f"upload_token:{token}",
            })
        except Exception as e:
            logging.warning("Failed to save %s: %s", safe, e)
    
    if not file_entries:
        return jsonify({"error": "no_valid_files"}), 400
    
    # Create LLM instance for bilingual check (use project's configured vision model)
    from core.helpers import get_vision_model
    llm = ChatOpenAI(model=get_vision_model(), temperature=0)
    
    # Check all files in parallel
    results = [None] * len(file_entries)
    
    with ThreadPoolExecutor(max_workers=min(6, len(file_entries))) as executor:
        future_to_idx = {
            executor.submit(
                _check_single_file_bilingual, 
                entry["path"], entry["filename"], llm
            ): i 
            for i, entry in enumerate(file_entries)
        }
        
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                result = future.result()
                # Add upload token/ref to result
                result["upload_token"] = file_entries[idx]["token"]
                result["file_ref"] = file_entries[idx]["file_ref"]
                results[idx] = result
            except Exception as e:
                logging.exception("[Safe Log] Unhandled exception in check_bilingual: %s", e)
                results[idx] = {
                    "filename": file_entries[idx]["filename"],
                    "needs_translation": True,
                    "is_bilingual": False,
                    "reason": f"Error: {str(e)}",
                    "upload_token": file_entries[idx]["token"],
                    "file_ref": file_entries[idx]["file_ref"],
                }
    
    needs_count = sum(1 for r in results if r and r.get("needs_translation"))
    bilingual_count = sum(1 for r in results if r and not r.get("needs_translation") and r.get("is_bilingual"))
    skipped_count = sum(1 for r in results if r and not r.get("needs_translation") and not r.get("is_bilingual"))
    
    return jsonify({
        "status": "success",
        "total": len(results),
        "needs_translation": needs_count,
        "already_bilingual": bilingual_count,
        "skipped": skipped_count,
        "results": results,
    })


# =====================================================================
# Templates
# =====================================================================

@splitter_translate_bp.get("/api/translate/templates")
def list_translate_templates():
    _ensure_translate_template_dir()
    templates: List[Dict[str, str]] = []
    for name in sorted(os.listdir(TRANSLATE_TEMPLATE_DIR)):
        path = os.path.join(TRANSLATE_TEMPLATE_DIR, name)
        if os.path.isfile(path) and name.lower().endswith(".html"):
            templates.append({"name": name})
    return jsonify({"templates": templates, "default": TRANSLATE_DEFAULT_TEMPLATE})


# =====================================================================
# Upload
# =====================================================================

@splitter_translate_bp.post("/api/translate/upload")
def translate_upload_file():
    """Upload a file for translation flow — persisted to uploads/translation_originals/."""
    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "missing_filename"}), 400

    orig_name = os.path.basename(f.filename)
    safe_name_val = _safe_name(orig_name)
    safe_name_val = safe_name_val.replace("..", ".")
    if not safe_name_val:
        return jsonify({"error": "invalid_filename"}), 400

    base, ext = os.path.splitext(safe_name_val)
    ext = ext or ".bin"
    token = uuid.uuid4().hex
    out_name = f"translate_{token}{ext}"
    # Save to persistent directory (survives F5 + server restart)
    out_path = os.path.join(TRANSLATION_ORIGINALS_DIR, out_name)

    try:
        f.save(out_path)
    except Exception as e:
        logging.exception("[Safe Log] Upload save failed: %s", e)
        return jsonify({"error": "save_failed", "detail": str(e)}), 500

    # Keep in-memory cache for backwards compat with existing code paths
    translation_upload_cache[token] = {"temp_path": out_path, "filename": safe_name_val}
    file_ref = f"upload_token:{token}"
    return jsonify(
        {
            "status": "success",
            "file_ref": file_ref,
            "filename": safe_name_val,
            "persistent_path": out_path,
        }
    )


# =====================================================================
# Original Pages (render as images)
# =====================================================================

@splitter_translate_bp.post("/api/translate/original_pages")
def translate_original_pages():
    """Render uploaded file pages as base64 PNG images (accepts file upload directly)."""
    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "missing_filename"}), 400

    ext = os.path.splitext(f.filename)[1].lower()

    # Save to temp for processing
    tmp_path = os.path.join(tempfile.gettempdir(), f"origpages_{uuid.uuid4().hex}{ext}")
    try:
        f.save(tmp_path)
    except Exception as e:
        logging.exception("[Safe Log] original_pages save failed: %s", e)
        return jsonify({"error": "save_failed", "detail": str(e)}), 500

    pages = []
    try:
        # Automatically convert input images to A4 PDF
        if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
            tmp_path = _convert_image_to_a4_pdf(tmp_path)
            ext = ".pdf"
            
        if ext == ".pdf":
            import fitz  # PyMuPDF
            doc = fitz.open(tmp_path)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                b64 = base64.b64encode(img_bytes).decode("ascii")
                pages.append({"index": i, "data_url": f"data:image/png;base64,{b64}"})
            doc.close()
        else:
            return jsonify({"error": "unsupported_format", "detail": f"Cannot render {ext} as images"}), 400
    except Exception as e:
        logging.exception("[Safe Log] original_pages render failed: %s", e)
        return jsonify({"error": "render_failed", "detail": str(e)}), 500
    finally:
        # Cleanup temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return jsonify({"pages": pages})


@splitter_translate_bp.post("/api/translate/original_pages_by_ref")
def translate_original_pages_by_ref():
    """Render original file pages as base64 PNG images using file_ref (for restored flows)."""
    payload = request.get_json(force=True, silent=True) or {}
    file_ref = (payload.get("file_ref") or "").strip()
    if not file_ref:
        return jsonify({"error": "missing_file_ref"}), 400

    input_dir = "input"
    source_path = _resolve_translate_source_path(input_dir, file_ref)
    if not source_path:
        return jsonify({"error": "file_not_found", "detail": f"Cannot resolve: {file_ref}"}), 404

    ext = os.path.splitext(source_path)[1].lower()
    pages = []
    tmp_path = None
    try:
        if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
            tmp_path = _convert_image_to_a4_pdf(source_path)
            render_path = tmp_path
        elif ext == ".pdf":
            render_path = source_path
        else:
            return jsonify({"error": "unsupported_format", "detail": f"Cannot render {ext}"}), 400

        import fitz
        doc = fitz.open(render_path)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode("ascii")
            pages.append({"index": i, "data_url": f"data:image/png;base64,{b64}"})
        doc.close()
    except Exception as e:
        logging.exception("[Safe Log] original_pages_by_ref error: %s", e)
        return jsonify({"error": "render_failed", "detail": str(e)}), 500
    finally:
        if tmp_path and tmp_path != source_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return jsonify({"pages": pages})


# =====================================================================
# Certification Template
# =====================================================================

@splitter_translate_bp.get("/api/translate/certification_template")
def translate_certification_template():
    """Return certification HTML template with embedded logo as base64."""
    template_path = os.path.join("dich", "HTML template", "Xác nhận dịch.html")
    logo_path = os.path.join("dich", "HTML template", "passport_lounge.jpg")

    if not os.path.isfile(template_path):
        return jsonify({"error": "template_not_found"}), 404

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Embed logo as base64 data URL
    if os.path.isfile(logo_path):
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode("ascii")
        html = html.replace('src="./passport_lounge.jpg"', f'src="data:image/jpeg;base64,{logo_b64}"')

    return jsonify({"html": html})


# =====================================================================
# Save / Rebuild HTML
# =====================================================================

@splitter_translate_bp.post("/api/translate/save_html")
def translate_save_html():
    payload = request.get_json(force=True) or {}
    html_content = payload.get("html_content") or ""
    file_name = _safe_name(payload.get("file_name") or "").strip()
    if not html_content.strip():
        return jsonify({"error": "missing_html_content"}), 400
    if not file_name:
        return jsonify({"error": "missing_file_name"}), 400
    if not file_name.lower().endswith(".html"):
        file_name = f"{file_name}.html"

    os.makedirs(TRANSLATE_HTML_SAVE_DIR, exist_ok=True)
    out_path = os.path.join(TRANSLATE_HTML_SAVE_DIR, file_name)

    # Avoid overwrite by suffixing
    if os.path.exists(out_path):
        stem, ext = os.path.splitext(file_name)
        idx = 1
        while os.path.exists(out_path):
            out_path = os.path.join(TRANSLATE_HTML_SAVE_DIR, f"{stem} ({idx}){ext}")
            idx += 1

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except Exception as e:
        logging.exception("[Safe Log] save_html failed: %s", e)
        return jsonify({"error": "save_failed", "detail": str(e)}), 500

    return jsonify(
        {
            "status": "success",
            "saved_path": out_path.replace("\\", "/"),
            "saved_name": os.path.basename(out_path),
        }
    )


@splitter_translate_bp.post("/api/translate/rebuild_html")
def translate_rebuild_html():
    """Rebuild HTML from edited translated text without re-OCR."""
    payload = request.get_json(force=True) or {}
    translated_text = (payload.get("translated_text") or "").strip()
    ocr_text = (payload.get("ocr_text") or "").strip()
    template_name = (payload.get("template_name") or TRANSLATE_DEFAULT_TEMPLATE).strip()

    if not translated_text:
        return jsonify({"error": "missing_translated_text"}), 400

    _ensure_translate_template_dir()
    template_name = _safe_name(template_name) or TRANSLATE_DEFAULT_TEMPLATE
    template_path = os.path.abspath(os.path.join(TRANSLATE_TEMPLATE_DIR, template_name))
    template_root = os.path.abspath(TRANSLATE_TEMPLATE_DIR)
    if not template_path.startswith(template_root) or not os.path.exists(template_path):
        return jsonify({"error": "template_not_found"}), 404

    with open(template_path, "r", encoding="utf-8") as f:
        template_html = f.read()

    try:
        llm = ChatOpenAI(model="gpt-5-mini", temperature=0)
        html_result = _build_translation_html(llm, translated_text, template_html, ocr_text or translated_text)
        # Embed local template images as base64
        html_result = _embed_template_images(html_result)
        return jsonify({"html": html_result})
    except QuotaExhaustedError as qe:
        return jsonify({"error": "quota_exceeded", "detail": str(qe)}), 429
    except Exception as e:
        logging.exception("[Safe Log] rebuild_html failed: %s", e)
        if _is_quota_error(e):
            return jsonify({"error": "quota_exceeded", "detail": "⚠️ Đã hết quota OpenAI API! Vui lòng kiểm tra billing."}), 429
        return jsonify({"error": str(e)}), 500


# ─── Serve output files (so previews persist after F5) ───

_OUTPUT_DIR = os.path.join(str(_BASE_DIR), "output")

@splitter_translate_bp.route("/api/output/<path:filename>", methods=["GET"])
def serve_output_file(filename):
    """Serve HTML files from the output directory."""
    safe_name_val = os.path.basename(filename)
    fpath = os.path.join(_OUTPUT_DIR, safe_name_val)
    if os.path.exists(fpath):
        with open(fpath, "r", encoding="utf-8") as f:
            return f.read(), 200, {
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
    return "", 404


@splitter_translate_bp.route("/api/output-files", methods=["GET"])
def list_output_files():
    """List available output files for auto-loading previews."""
    files = {}
    itin_path = os.path.join(_OUTPUT_DIR, "itinerary.html")
    if os.path.exists(itin_path):
        files["itinerary"] = True
    hotel_files = []
    for i in range(1, 10):
        hpath = os.path.join(_OUTPUT_DIR, f"booking_hotel_{i}.html")
        if os.path.exists(hpath):
            hotel_files.append(f"booking_hotel_{i}.html")
        else:
            break
    if hotel_files:
        files["hotel_bookings"] = hotel_files
    return jsonify(files)


# ==================== TRANSLATION FLOW PERSISTENCE ====================

@splitter_translate_bp.get("/api/translate/flows")
def list_translate_flows():
    """List all saved translation flows."""
    flows = db.list_translation_flows()
    return jsonify({"flows": flows})


@splitter_translate_bp.post("/api/translate/flows")
def create_translate_flow():
    """Create (save) a new translation flow."""
    data = request.get_json(force=True, silent=True) or {}
    flow = db.save_translation_flow(
        filename=data.get("filename", ""),
        file_ref=data.get("file_ref", ""),
        template_name=data.get("template_name", "auto"),
        source_lang=data.get("source_lang", "vi"),
        ocr_text=data.get("ocr_text", ""),
        translated_text=data.get("translated_text", ""),
        html_content=data.get("html_content", ""),
        save_name=data.get("save_name", ""),
        status=data.get("status", "done"),
        workspace=data.get("workspace", ""),
        drive_file_id=data.get("drive_file_id", ""),
    )
    return jsonify(flow), 201


@splitter_translate_bp.put("/api/translate/flows/<int:flow_id>")
def update_translate_flow(flow_id):
    """Update an existing translation flow (e.g. after editing HTML)."""
    data = request.get_json(force=True, silent=True) or {}
    # Only allow updating specific fields
    allowed = {"filename", "file_ref", "template_name", "source_lang",
               "ocr_text", "translated_text", "html_content", "save_name", "status",
               "workspace", "drive_file_id"}
    updates = {k: v for k, v in data.items() if k in allowed}
    result = db.update_translation_flow(flow_id, **updates)
    if result is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(result)


@splitter_translate_bp.delete("/api/translate/flows/<int:flow_id>")
def delete_translate_flow(flow_id):
    """Delete a single translation flow + clean up original file on disk."""
    # Get flow data before deletion to find the file_ref
    flow_data = db.get_translation_flow(flow_id)
    if flow_data:
        _cleanup_original_file(flow_data.get("file_ref", ""))
    ok = db.delete_translation_flow(flow_id)
    if not ok:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"deleted": True, "id": flow_id})


@splitter_translate_bp.delete("/api/translate/flows")
def delete_all_translate_flows():
    """Delete all translation flows + clean up ALL original files on disk."""
    # Get all flows to clean up their files
    all_flows = db.list_translation_flows()
    for f in all_flows:
        _cleanup_original_file(f.get("file_ref", ""))
    count = db.delete_all_translation_flows()

    # Also wipe ALL files in translation_originals/ (catch orphans without flows)
    try:
        for fname in os.listdir(TRANSLATION_ORIGINALS_DIR):
            fpath = os.path.join(TRANSLATION_ORIGINALS_DIR, fname)
            if os.path.isfile(fpath):
                try:
                    os.remove(fpath)
                except OSError:
                    pass
        logging.info("[Cleanup] Wiped all files in translation_originals/")
    except Exception as e:
        logging.warning("[Cleanup] Failed to wipe translation_originals: %s", e)

    # Clear in-memory upload cache
    translation_upload_cache.clear()

    return jsonify({"deleted": True, "count": count})
