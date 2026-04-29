"""
AI PDF Splitter routes: upload, split, classify, download.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import uuid
import zipfile
import threading
from pathlib import Path as SplitterPath
from typing import Dict, Optional

from pypdf import PdfReader, PdfWriter

from flask import Blueprint, Response, jsonify, request, send_from_directory


from pdf_tools.pdf_service import pdf_to_images, get_page_count, create_output_files
from pdf_tools.ai_service import classify_all_pages
from config import Config

splitter_bp = Blueprint("splitter", __name__)

# Base directory (project root, one level up from routes/)
_BASE_DIR = SplitterPath(__file__).parent.parent

# Directories for AI splitter
SPLITTER_UPLOAD_DIR = _BASE_DIR / Config.SPLITTER_UPLOADS_DIR
SPLITTER_OUTPUT_DIR = _BASE_DIR / Config.SPLITTER_OUTPUTS_DIR
SPLITTER_UPLOAD_DIR.mkdir(exist_ok=True)
SPLITTER_OUTPUT_DIR.mkdir(exist_ok=True)

# In-memory job tracking for AI splitter
splitter_jobs: Dict[str, Dict] = {}

# Output dir constant
_OUTPUT_DIR = os.path.join(str(_BASE_DIR), "output")






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

        # Save source metadata for persistent display
        source_meta = {"source_filename": job["filename"], "source_type": "ai"}
        pid = job.get("project_id")
        if pid is not None:
            source_meta["project_id"] = pid
        # Also store original source path from mapping (for save-to-input)
        mapping_file = os.path.join(str(SPLITTER_UPLOAD_DIR), "_source_mapping.json")
        if os.path.isfile(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as mmf:
                    mapping = json.load(mmf)
                orig_path = mapping.get(job["filename"], "")
                if orig_path:
                    source_meta["source_path"] = orig_path
            except Exception as e:
                logging.exception("[Safe Log] Unhandled exception in splitter.py: %s", e)
                logging.debug("Ignored: %s", e)
        with open(os.path.join(job_output_dir, "_source.json"), "w", encoding="utf-8") as mf:
            json.dump(source_meta, mf, ensure_ascii=False)

        # Step 4: Create ZIP
        zip_path = str(SPLITTER_OUTPUT_DIR / f"{file_id}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in output_files:
                zf.write(f["path"], f["filename"])
        job["zip_path"] = zip_path
        job["status"] = "completed"

    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in splitter.py: %s", e)
        job["status"] = "error"
        job["error"] = str(e)
        logging.error(f"[AI Splitter] Error processing {file_id}: {e}")


@splitter_bp.get("/api/ai-splitter/list")
def splitter_list_files():
    """List PDF files already in splitter_uploads folder."""
    upload_dir = str(SPLITTER_UPLOAD_DIR)
    project_id = request.args.get("project_id", type=int)
    if not os.path.isdir(upload_dir):
        return jsonify({"files": []})
    files = []
    for fname in sorted(os.listdir(upload_dir)):
        path = os.path.join(upload_dir, fname)
        if not (os.path.isfile(path) and fname.lower().endswith(".pdf")):
            continue

        display_name = fname
        file_pid: Optional[int] = None

        # New convention: filenames starting with p<id>__ belong to a specific project
        match = re.match(r"p(\d+)__(.+)", fname, re.IGNORECASE)
        if match:
            try:
                file_pid = int(match.group(1))
            except ValueError:
                file_pid = None
            display_name = match.group(2)

        if project_id is not None and file_pid != project_id:
            continue

        files.append(
            {
                "filename": fname,  # stored name used by APIs
                "display_name": display_name,  # original name for UI
                "size": os.path.getsize(path),
            }
        )
    return jsonify({"files": files})


@splitter_bp.post("/api/ai-splitter/delete")
def splitter_delete_file():
    """Delete a single file from splitter_uploads."""
    payload = request.get_json(force=True) or {}
    filename = payload.get("filename", "")
    if not filename:
        return jsonify({"error": "no_filename"}), 400
    file_path = SPLITTER_UPLOAD_DIR / filename
    if not file_path.is_file():
        return jsonify({"error": "file_not_found"}), 404
    os.remove(str(file_path))
    return jsonify({"deleted": filename})


@splitter_bp.post("/api/ai-splitter/delete-all")
def splitter_delete_all():
    """Delete all PDF files from splitter_uploads. If project_id is in body, only delete files with p{id}__ prefix."""
    payload = request.get_json(force=True) or {}
    project_id = payload.get("project_id")
    pid = None
    if isinstance(project_id, int):
        pid = project_id
    elif isinstance(project_id, str) and project_id.isdigit():
        pid = int(project_id)
    upload_dir = str(SPLITTER_UPLOAD_DIR)
    count = 0
    if os.path.isdir(upload_dir):
        for fname in os.listdir(upload_dir):
            fpath = os.path.join(upload_dir, fname)
            if not (os.path.isfile(fpath) and fname.lower().endswith(".pdf")):
                continue
            if pid is not None:
                match = re.match(r"p" + str(pid) + r"__(.+)", fname)
                if not match:
                    continue
            os.remove(fpath)
            count += 1
    return jsonify({"deleted_count": count})


@splitter_bp.post("/api/ai-splitter/process-local")
def splitter_process_local():
    """Process a PDF already in splitter_uploads (no upload needed)."""
    payload = request.get_json(force=True) or {}
    filename = payload.get("filename", "")
    project_id = payload.get("project_id")
    if not filename:
        return jsonify({"error": "no_filename"}), 400

    src_path = SPLITTER_UPLOAD_DIR / filename
    if not src_path.is_file():
        return jsonify({"error": "file_not_found"}), 404

    import threading

    # Normalise project_id to int if possible
    if isinstance(project_id, int):
        pid: Optional[int] = project_id
    elif isinstance(project_id, str) and project_id.isdigit():
        pid = int(project_id)
    else:
        pid = None

    file_id = uuid.uuid4().hex[:8]
    # Copy to sub-folder (same structure as upload flow)
    job_dir = SPLITTER_UPLOAD_DIR / file_id
    job_dir.mkdir(exist_ok=True)
    file_path = job_dir / filename
    shutil.copy2(str(src_path), str(file_path))

    page_count = get_page_count(str(file_path))

    splitter_jobs[file_id] = {
        "status": "uploaded",
        "filename": filename,
        "project_id": pid,
        "file_path": str(file_path),
        "page_count": page_count,
        "current_page": 0,
        "classifications": [],
        "output_files": [],
        "error": None,
        "zip_path": None,
    }

    # Run in background thread (same as upload flow)
    thread = threading.Thread(target=_run_splitter_job, args=(file_id,), daemon=True)
    thread.start()

    return jsonify({"file_id": file_id, "filename": filename, "page_count": page_count})


@splitter_bp.post("/api/ai-splitter/upload")
def splitter_upload():
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400
    file = request.files["file"]
    project_id_raw = request.form.get("project_id")
    if isinstance(project_id_raw, str) and project_id_raw.isdigit():
        pid: Optional[int] = int(project_id_raw)
    else:
        pid = None
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
        "project_id": pid,
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


@splitter_bp.post("/api/ai-splitter/process/<file_id>")
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


@splitter_bp.get("/api/ai-splitter/status/<file_id>")
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


@splitter_bp.get("/api/ai-splitter/download/<file_id>/<filename>")
def splitter_download_single(file_id: str, filename: str):
    # Check both splitter_jobs (AI) and filesystem (manual splits)
    file_path = SPLITTER_OUTPUT_DIR / file_id / filename
    if not file_path.exists():
        return jsonify({"error": "file_not_found"}), 404
    return send_from_directory(str(SPLITTER_OUTPUT_DIR / file_id), filename,
                                as_attachment=True, mimetype="application/pdf")


@splitter_bp.get("/api/ai-splitter/view/<file_id>/<filename>")
def splitter_view_single(file_id: str, filename: str):
    """Serve PDF for in-browser viewing (as_attachment=False)."""
    file_path = SPLITTER_OUTPUT_DIR / file_id / filename
    if not file_path.exists():
        return jsonify({"error": "file_not_found"}), 404
    return send_from_directory(str(SPLITTER_OUTPUT_DIR / file_id), filename,
                                as_attachment=False, mimetype="application/pdf")


@splitter_bp.get("/api/ai-splitter/download-zip/<file_id>")
def splitter_download_zip(file_id: str):
    # Try AI splitter pre-built zip first
    if file_id in splitter_jobs:
        job = splitter_jobs[file_id]
        if job["status"] == "completed" and job.get("zip_path"):
            zip_path = SplitterPath(job["zip_path"])
            if zip_path.exists():
                return send_from_directory(str(zip_path.parent), zip_path.name,
                                            as_attachment=True, mimetype="application/zip")

    # Fallback: create zip on-the-fly from output folder (manual splits)
    output_folder = SPLITTER_OUTPUT_DIR / file_id
    if not output_folder.exists():
        return jsonify({"error": "not_found"}), 404

    import io, zipfile as zf
    buf = io.BytesIO()
    with zf.ZipFile(buf, "w", zf.ZIP_DEFLATED) as z:
        for fname in sorted(os.listdir(str(output_folder))):
            fpath = os.path.join(str(output_folder), fname)
            if os.path.isfile(fpath) and fname.lower().endswith(".pdf"):
                z.write(fpath, fname)
    buf.seek(0)
    return Response(
        buf.read(),
        mimetype="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{file_id}.zip"'}
    )


@splitter_bp.get("/api/ai-splitter/list-outputs")
def splitter_list_outputs():
    """List ALL split output files across all splitter job folders (AI + manual).
    Used by Tab ② to pick a file to re-split manually."""
    output_dir = str(SPLITTER_OUTPUT_DIR)
    project_id = request.args.get("project_id", type=int)
    if not os.path.isdir(output_dir):
        return jsonify({"groups": []})

    groups = []
    for folder_name in sorted(os.listdir(output_dir)):
        folder_path = os.path.join(output_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        files = []
        for fname in sorted(os.listdir(folder_path)):
            fpath = os.path.join(folder_path, fname)
            if os.path.isfile(fpath) and fname.lower().endswith(".pdf"):
                files.append({
                    "filename": fname,
                    "size": os.path.getsize(fpath),
                    "file_id": folder_name,
                })
        if files:
            is_manual = folder_name.startswith("manual_")
            # Read persistent source metadata
            source_name = ""
            source_project_id = None
            source_meta_path = os.path.join(folder_path, "_source.json")
            if os.path.isfile(source_meta_path):
                try:
                    with open(source_meta_path, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                    source_name = meta.get("source_filename", "")
                    source_project_id = meta.get("project_id")
                except Exception as e:
                    logging.exception("[Safe Log] Unhandled exception in splitter.py: %s", e)
                    logging.debug("Ignored: %s", e)
            # Fallback to in-memory splitter_jobs
            if not source_name and not is_manual and folder_name in splitter_jobs:
                source_name = splitter_jobs[folder_name].get("filename", "")
                if source_project_id is None:
                    source_project_id = splitter_jobs[folder_name].get("project_id")

            # Filter by project if requested
            if project_id is not None and source_project_id != project_id:
                continue

            groups.append({
                "folder_id": folder_name,
                "source_type": "manual" if is_manual else "ai",
                "source_filename": source_name,
                "files": files,
            })
    return jsonify({"groups": groups})


@splitter_bp.post("/api/ai-splitter/merge-outputs")
def splitter_merge_outputs():
    """Merge multiple output PDF files into one.
    Expects JSON: { files: [{file_id, filename}, ...], output_name: "optional" }
    Merges in order, saves into the first file's folder, deletes originals."""
    payload = request.get_json(force=True) or {}
    files = payload.get("files", [])
    output_name = (payload.get("output_name") or "").strip()

    if not isinstance(files, list) or len(files) < 2:
        return jsonify({"error": "need_at_least_2_files"}), 400

    # Validate all files exist
    paths = []
    for f in files:
        fid = f.get("file_id", "")
        fname = f.get("filename", "")
        fpath = SPLITTER_OUTPUT_DIR / fid / fname
        if not fpath.is_file():
            return jsonify({"error": f"file_not_found: {fid}/{fname}"}), 404
        paths.append((fid, fname, str(fpath)))

    # Default output name = first file's name (without .pdf)
    if not output_name:
        first_name = os.path.splitext(files[0]["filename"])[0]
        output_name = first_name

    # Sanitize
    output_name = re.sub(r'[\\/:*?"<>|]+', ' ', output_name)
    output_name = re.sub(r'\s+', ' ', output_name).strip() or "Merged"

    # Merge PDFs
    writer = PdfWriter()
    for _, _, fpath in paths:
        try:
            reader = PdfReader(fpath)
            for page in reader.pages:
                writer.add_page(page)
        except Exception as exc:
            logging.exception("[Safe Log] Unhandled exception in splitter.py: %s", exc)
            return jsonify({"error": f"read_failed: {fpath}", "detail": str(exc)}), 500

    # Save to first file's folder
    target_dir = str(SPLITTER_OUTPUT_DIR / files[0]["file_id"])
    out_filename = f"{output_name}.pdf"
    out_path = os.path.join(target_dir, out_filename)
    # Avoid overwriting
    idx = 1
    while os.path.exists(out_path):
        out_path = os.path.join(target_dir, f"{output_name} ({idx}).pdf")
        out_filename = f"{output_name} ({idx}).pdf"
        idx += 1

    try:
        with open(out_path, "wb") as f:
            writer.write(f)
    except Exception as exc:
        logging.exception("[Safe Log] Unhandled exception in splitter.py: %s", exc)
        return jsonify({"error": "write_failed", "detail": str(exc)}), 500

    # Delete originals
    deleted = []
    for fid, fname, fpath in paths:
        try:
            os.remove(fpath)
            deleted.append(f"{fid}/{fname}")
        except Exception as e:
            logging.exception("[Safe Log] Unhandled exception in splitter.py: %s", e)
            logging.debug("Ignored: %s", e)

    return jsonify({
        "status": "done",
        "merged_file": out_filename,
        "file_id": files[0]["file_id"],
        "total_pages": len(writer.pages),
        "deleted": deleted,
    })


@splitter_bp.post("/api/ai-splitter/clear-outputs")
def splitter_clear_outputs():
    """Delete ALL output folders in splitter_outputs/ (AI + manual).
    Also clears in-memory splitter_jobs."""
    output_dir = str(SPLITTER_OUTPUT_DIR)
    deleted_count = 0
    if os.path.isdir(output_dir):
        for name in os.listdir(output_dir):
            path = os.path.join(output_dir, name)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
                deleted_count += 1
            elif os.path.isfile(path):
                os.remove(path)  # remove .zip files etc.
                deleted_count += 1
    splitter_jobs.clear()
    return jsonify({"status": "done", "deleted_count": deleted_count})



