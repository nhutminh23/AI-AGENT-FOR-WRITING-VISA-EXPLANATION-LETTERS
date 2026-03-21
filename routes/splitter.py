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
from typing import Any, Dict, List, Optional

from flask import Blueprint, Response, jsonify, request, send_file, send_from_directory

import database as db
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

# Translation directories (aliases from Config for splitter routes)
TRANSLATE_TEMPLATE_DIR = os.path.join(str(_BASE_DIR), Config.TRANSLATION_TEMPLATE_DIR)
TRANSLATE_DEFAULT_TEMPLATE = Config.TRANSLATION_DEFAULT_TEMPLATE
TRANSLATE_OUTPUT_DIR = os.path.join(str(_BASE_DIR), Config.TRANSLATION_OUTPUT_DIR)
TRANSLATE_HTML_SAVE_DIR = os.path.join(str(_BASE_DIR), Config.TRANSLATION_HTML_SAVE_DIR)








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
        mapping_file = os.path.join("splitter_uploads", "_source_mapping.json")
        if os.path.isfile(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as mmf:
                    mapping = json.load(mmf)
                orig_path = mapping.get(job["filename"], "")
                if orig_path:
                    source_meta["source_path"] = orig_path
            except Exception as e:
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
        job["status"] = "error"
        job["error"] = str(e)
        print(f"[AI Splitter] Error processing {file_id}: {e}")


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
    from flask import Response
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


@splitter_bp.post("/api/manual-split/upload-and-split")
def manual_split_upload_and_split():
    """Upload a PDF from computer and split it manually.
    The uploaded file is stored temporarily, split into segments,
    and results go to splitter_outputs/manual_<uuid>/."""
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_pdf"}), 400

    segments_json = request.form.get("segments", "[]")
    project_id_raw = request.form.get("project_id")
    try:
        segments = json.loads(segments_json)
    except Exception as e:
        return jsonify({"error": "invalid_segments"}), 400
    if not isinstance(segments, list) or not segments:
        return jsonify({"error": "missing_segments"}), 400

    # Save uploaded file to temp location
    manual_id = f"manual_{uuid.uuid4().hex[:8]}"
    output_dir = str(SPLITTER_OUTPUT_DIR / manual_id)
    os.makedirs(output_dir, exist_ok=True)

    import tempfile
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename)
    file.save(tmp_path)

    try:
        reader = PdfReader(tmp_path)
    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
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
                "file_id": manual_id,
            }
        )

    # Clean up temp
    shutil.rmtree(tmp_dir, ignore_errors=True)

    # Save source metadata for persistent display
    if created:
        source_meta = {"source_filename": file.filename, "source_type": "manual"}
        if project_id_raw and project_id_raw.isdigit():
            source_meta["project_id"] = int(project_id_raw)
        with open(os.path.join(output_dir, "_source.json"), "w", encoding="utf-8") as mf:
            json.dump(source_meta, mf, ensure_ascii=False)

    return jsonify(
        {
            "status": "done",
            "manual_id": manual_id,
            "output_dir": output_dir,
            "source": file.filename,
            "total_pages": total_pages,
            "segments": created,
        }
    )


@splitter_bp.post("/api/manual-split/send-to-classifier")
def manual_split_send_to_classifier():
    """Send specific manual split results directly to classifier input.
    Use this when user uploads a file from computer and wants to send
    directly to classifier without going through the full pipeline."""
    payload = request.get_json(force=True) or {}
    manual_id = payload.get("manual_id", "")
    target_dir = payload.get("target_dir", os.path.join("phanloai", "input"))

    if not manual_id:
        return jsonify({"error": "missing_manual_id"}), 400

    source_dir = str(SPLITTER_OUTPUT_DIR / manual_id)
    if not os.path.isdir(source_dir):
        return jsonify({"error": "not_found"}), 404

    os.makedirs(target_dir, exist_ok=True)
    copied = []
    for fname in os.listdir(source_dir):
        fpath = os.path.join(source_dir, fname)
        if not os.path.isfile(fpath) or not fname.lower().endswith(".pdf"):
            continue
        dst = os.path.join(target_dir, fname)
        base, ext = os.path.splitext(fname)
        idx = 1
        while os.path.exists(dst):
            dst = os.path.join(target_dir, f"{base} ({idx}){ext}")
            idx += 1
        shutil.copy2(fpath, dst)
        copied.append(fname)

    return jsonify({"status": "done", "copied": copied, "count": len(copied), "target_dir": target_dir})


@splitter_bp.post("/api/manual-split/get-page-count")
def manual_split_get_page_count():
    """Get page count of a file in splitter_outputs (for re-splitting from AI results)."""
    payload = request.get_json(force=True) or {}
    file_id = payload.get("file_id", "")
    filename = payload.get("filename", "")
    if not file_id or not filename:
        return jsonify({"error": "missing_params"}), 400
    file_path = SPLITTER_OUTPUT_DIR / file_id / filename
    if not file_path.is_file():
        return jsonify({"error": "file_not_found"}), 404
    try:
        count = get_page_count(str(file_path))
    except Exception as exc:
        return jsonify({"error": "read_failed", "detail": str(exc)}), 500
    return jsonify({"page_count": count, "filename": filename, "file_id": file_id})


@splitter_bp.post("/api/manual-split/upload-get-page-count")
def manual_split_upload_get_page_count():
    """Upload a PDF and return its page count (for building split form)."""
    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400
    file = request.files["file"]
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "not_pdf"}), 400

    # Save to a temp location under splitter_uploads
    temp_id = f"temp_{uuid.uuid4().hex[:8]}"
    temp_dir = SPLITTER_UPLOAD_DIR / temp_id
    temp_dir.mkdir(exist_ok=True)
    file_path = temp_dir / file.filename
    file.save(str(file_path))

    try:
        count = get_page_count(str(file_path))
    except Exception as exc:
        shutil.rmtree(str(temp_dir), ignore_errors=True)
        return jsonify({"error": "read_failed", "detail": str(exc)}), 500

    return jsonify({
        "page_count": count,
        "filename": file.filename,
        "temp_id": temp_id,
        "temp_path": str(file_path),
    })



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
        return jsonify({"error": "write_failed", "detail": str(exc)}), 500

    # Delete originals
    deleted = []
    for fid, fname, fpath in paths:
        try:
            os.remove(fpath)
            deleted.append(f"{fid}/{fname}")
        except Exception as e:
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


@splitter_bp.get("/api/translate/templates")
def list_translate_templates():
    _ensure_translate_template_dir()
    templates: List[Dict[str, str]] = []
    for name in sorted(os.listdir(TRANSLATE_TEMPLATE_DIR)):
        path = os.path.join(TRANSLATE_TEMPLATE_DIR, name)
        if os.path.isfile(path) and name.lower().endswith(".html"):
            templates.append({"name": name})
    return jsonify({"templates": templates, "default": TRANSLATE_DEFAULT_TEMPLATE})


@splitter_bp.post("/api/translate/upload")
def translate_upload_file():
    """Upload a file for translation flow (temporary, auto-clean)."""
    if "file" not in request.files:
        return jsonify({"error": "missing_file"}), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "missing_filename"}), 400

    orig_name = os.path.basename(f.filename)
    safe_name = _safe_name(orig_name)
    safe_name = safe_name.replace("..", ".")
    if not safe_name:
        return jsonify({"error": "invalid_filename"}), 400

    base, ext = os.path.splitext(safe_name)
    ext = ext or ".bin"
    token = uuid.uuid4().hex
    out_name = f"translate_{token}{ext}"
    out_path = os.path.join(tempfile.gettempdir(), out_name)

    try:
        f.save(out_path)
    except Exception as e:
        return jsonify({"error": "save_failed", "detail": str(e)}), 500

    translation_upload_cache[token] = {"temp_path": out_path, "filename": safe_name}
    file_ref = f"upload_token:{token}"
    return jsonify(
        {
            "status": "success",
            "file_ref": file_ref,
            "filename": safe_name,
            "temporary": True,
        }
    )


@splitter_bp.post("/api/translate/original_pages")
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
        return jsonify({"error": "save_failed", "detail": str(e)}), 500

    pages = []
    try:
        if ext == ".pdf":
            import fitz  # PyMuPDF
            doc = fitz.open(tmp_path)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                b64 = base64.b64encode(img_bytes).decode("ascii")
                pages.append({"index": i, "data_url": f"data:image/png;base64,{b64}"})
            doc.close()
        elif ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
            with open(tmp_path, "rb") as fp:
                img_bytes = fp.read()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"
            b64 = base64.b64encode(img_bytes).decode("ascii")
            pages.append({"index": 0, "data_url": f"data:{mime};base64,{b64}"})
        else:
            return jsonify({"error": "unsupported_format", "detail": f"Cannot render {ext} as images"}), 400
    except Exception as e:
        return jsonify({"error": "render_failed", "detail": str(e)}), 500
    finally:
        # Cleanup temp file
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    return jsonify({"pages": pages})


@splitter_bp.get("/api/translate/certification_template")
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

@splitter_bp.post("/api/translate/run_stream")
def run_translate_stream():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    file_ref = (payload.get("file_ref") or "").strip()
    template_name = (payload.get("template_name") or TRANSLATE_DEFAULT_TEMPLATE).strip()
    flow_id = payload.get("flow_id") or 1
    source_lang = (payload.get("source_lang") or "tiếng Việt").strip()
    ocr_model = payload.get("ocr_model") or "gpt-5-mini"
    translate_model = payload.get("translate_model") or "gpt-5-mini"

    if not file_ref:
        return jsonify({"error": "missing_file_ref"}), 400

    _ensure_translate_template_dir()
    is_auto_template = template_name.lower() in ("auto", "")
    if not is_auto_template:
        template_name = _safe_name(template_name) or TRANSLATE_DEFAULT_TEMPLATE
        template_path = os.path.abspath(os.path.join(TRANSLATE_TEMPLATE_DIR, template_name))
        template_root = os.path.abspath(TRANSLATE_TEMPLATE_DIR)
        if not template_path.startswith(template_root) or not os.path.exists(template_path):
            return jsonify({"error": "template_not_found"}), 404

    source_path = _resolve_translate_source_path(input_dir, file_ref)
    if not source_path:
        return jsonify({"error": "file_not_found"}), 404
    upload_token = ""
    if file_ref.startswith("upload_token:"):
        upload_token = file_ref.split(":", 1)[1].strip()

    def generate():
        nonlocal template_name
        def send_event(step: int, msg: str, data: Optional[Dict[str, Any]] = None):
            evt: Dict[str, Any] = {"step": step, "msg": msg}
            if data is not None:
                evt["data"] = data
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

        try:
            # Step 1: OCR + Translate combined (per-page parallel)
            yield from send_event(1, "⏳ Đang OCR + Dịch tài liệu...")
            llm_ocr = ChatOpenAI(model=ocr_model, temperature=0)
            page_events: List[str] = []

            def on_page(page_idx: int, total: int) -> None:
                page_events.append(f"data: {json.dumps({'step': 1, 'msg': f'⏳ OCR+Dịch trang {page_idx}/{total}...'}, ensure_ascii=False)}\n\n")

            translated_text = _ocr_and_translate_document(llm_ocr, source_path, source_lang=source_lang, page_callback=on_page)
            # Yield page progress events
            for pe in page_events:
                yield pe
            if not translated_text.strip():
                yield from send_event(-1, "❌ Không trích xuất/dịch được từ file")
                return

            # Vietnamese text validation — check for leftover Vietnamese chars
            import re as _re
            viet_chars = _re.findall(r'[àáạảãăắằặẳẵâấầậẩẫèéẹẻẽêếềệểễìíịỉĩòóọỏõôốồộổỗơớờợởỡùúụủũưứừựửữỳýỵỷỹđÀÁẠẢÃĂẮẰẶẲẴÂẤẦẬẨẪÈÉẸẺẼÊẾỀỆỂỄÌÍỊỈĨÒÓỌỎÕÔỐỒỘỔỖƠỚỜỢỞỠÙÚỤỦŨƯỨỪỰỬỮỲÝỴỶỸĐ]', translated_text)
            if len(viet_chars) > 5:  # More than 5 Vietnamese chars = needs cleanup
                yield from send_event(1, "🔄 Phát hiện tiếng Việt còn sót, đang sửa...")
                llm_fix = ChatOpenAI(model=translate_model, temperature=0)
                fix_prompt = (
                    "The following text should be 100% English but contains some Vietnamese words/phrases. "
                    "Translate ALL remaining Vietnamese text to English. Keep the structure and formatting intact. "
                    "Output ONLY the corrected English text:\n\n" + translated_text
                )
                try:
                    fix_result = llm_fix.invoke([SystemMessage(content="Fix Vietnamese text remnants. Output pure English."), HumanMessage(content=fix_prompt)])
                    fixed = (fix_result.content or "").strip()
                    if fixed:
                        translated_text = fixed
                except Exception as e:
                    logging.debug("Ignored: %s", e)  # Keep original if fix fails

            yield from send_event(1, "✅ OCR + Dịch hoàn tất")

            # Auto-detect template from translated text if needed
            if is_auto_template:
                template_name = _auto_detect_template(translated_text)
                yield from send_event(1, f"🔍 Tự động chọn template: {template_name}")

            # Load template HTML
            tpl_path = os.path.abspath(os.path.join(TRANSLATE_TEMPLATE_DIR, template_name))
            tpl_root = os.path.abspath(TRANSLATE_TEMPLATE_DIR)
            if not tpl_path.startswith(tpl_root) or not os.path.exists(tpl_path):
                tpl_path = os.path.join(TRANSLATE_TEMPLATE_DIR, TRANSLATE_DEFAULT_TEMPLATE)
            with open(tpl_path, "r", encoding="utf-8") as f:
                template_html = f.read()

            # Step 2: Build HTML
            yield from send_event(2, "⏳ Đang tạo HTML theo template...")
            llm_translate = ChatOpenAI(model=translate_model, temperature=0)
            html_result = _build_translation_html(
                llm_translate,
                translated_text,
                template_html,
                translated_text,
            )
            if not html_result.strip():
                yield from send_event(-1, "❌ Không tạo được HTML")
                return
            yield from send_event(2, "✅ Tạo HTML hoàn tất")

            file_stem = os.path.splitext(os.path.basename(source_path))[0]
            safe_stem = _safe_name(file_stem) or "translated_document"
            out_dir = os.path.join(TRANSLATE_OUTPUT_DIR, f"flow_{flow_id}")
            os.makedirs(out_dir, exist_ok=True)

            translated_path = os.path.join(out_dir, f"{safe_stem}.translated.txt")
            html_path = os.path.join(out_dir, f"{safe_stem}.translated.html")
            with open(translated_path, "w", encoding="utf-8") as f:
                f.write(translated_text)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_result)

            yield from send_event(
                3,
                "✅ Hoàn tất",
                {
                    "translated_text": translated_text,
                    "html": html_result,
                    "paths": {
                        "translated_path": translated_path,
                        "html_path": html_path,
                    },
                },
            )
        except QuotaExhaustedError as qe:
            yield from send_event(-1, f"⚠️ HẾT QUOTA OpenAI! {str(qe)}")
        except Exception as e:
            # Check if it's a quota error in disguise
            if _is_quota_error(e):
                yield from send_event(-1, "⚠️ HẾT QUOTA OpenAI! Vui lòng kiểm tra billing tại https://platform.openai.com/account/billing")
            else:
                yield from send_event(-1, f"❌ Lỗi: {str(e)}")
        finally:
            # Cleanup temporary uploaded file (if any)
            if upload_token:
                meta = translation_upload_cache.pop(upload_token, None) or {}
                temp_path = meta.get("temp_path", "")
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception as e:
                        logging.debug("Ignored: %s", e)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@splitter_bp.post("/api/translate/save_html")
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
        return jsonify({"error": "save_failed", "detail": str(e)}), 500

    return jsonify(
        {
            "status": "success",
            "saved_path": out_path.replace("\\", "/"),
            "saved_name": os.path.basename(out_path),
        }
    )


@splitter_bp.post("/api/translate/rebuild_html")
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
        return jsonify({"html": html_result})
    except QuotaExhaustedError as qe:
        return jsonify({"error": "quota_exceeded", "detail": str(qe)}), 429
    except Exception as e:
        if _is_quota_error(e):
            return jsonify({"error": "quota_exceeded", "detail": "⚠️ Đã hết quota OpenAI API! Vui lòng kiểm tra billing."}), 429
        return jsonify({"error": str(e)}), 500




# ─── Serve output files (so previews persist after F5) ───

_OUTPUT_DIR = os.path.join(str(_BASE_DIR), "output")

@splitter_bp.route("/api/output/<path:filename>", methods=["GET"])
def serve_output_file(filename):
    """Serve HTML files from the output directory."""
    safe_name = os.path.basename(filename)
    fpath = os.path.join(_OUTPUT_DIR, safe_name)
    if os.path.exists(fpath):
        with open(fpath, "r", encoding="utf-8") as f:
            return f.read(), 200, {
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
    return "", 404


@splitter_bp.route("/api/output-files", methods=["GET"])
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


