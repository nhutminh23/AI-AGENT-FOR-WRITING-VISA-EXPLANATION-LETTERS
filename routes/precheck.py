"""
Pre-check routes: file listing, document scanning with AI classification.
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Blueprint, jsonify, request

from core.helpers import get_vision_model, list_input_files

from routes.precheck_helpers import classify_one

precheck_bp = Blueprint("precheck", __name__)


@precheck_bp.get("/api/files")
def list_files():
    input_dir = request.args.get("input_dir", "input")
    files = list_input_files(input_dir)
    return jsonify({"input_dir": input_dir, "files": files})


# ── Progress tracking for precheck scan ──
_precheck_progress = {"total": 0, "done": 0, "current_file": "", "running": False}

@precheck_bp.get("/api/precheck/progress")
def precheck_progress():
    """Poll endpoint for scan progress."""
    return jsonify(_precheck_progress)

@precheck_bp.post("/api/precheck/scan")
def precheck_scan():
    """Scan all files in input/ subfolders: classify doc type + detect multi-doc + suggest rename."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    model = payload.get("model") or get_vision_model()

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404

    from langchain_openai import ChatOpenAI
    from classifier.agent import normalize_vietnamese_name

    llm = ChatOpenAI(model=model, temperature=0)

    import re
    # Collect files grouped by person subfolder (RECURSIVE with os.walk)
    folders_data = {}
    for item in sorted(os.listdir(input_dir)):
        folder_path = os.path.join(input_dir, item)
        if not os.path.isdir(folder_path):
            continue
        if item.startswith('.') or item.startswith('_'):
            continue
            
        clean_item = re.sub(r'_[a-zA-Z0-9\-_]{20,}$', '', item)
        person_normalized = normalize_vietnamese_name(clean_item)
        files_in_folder = []
        # Walk recursively into all subfolders
        for root, _dirs, filenames in os.walk(folder_path):
            current_folder_name = os.path.basename(root)
            if current_folder_name == item:
                file_person_name = person_normalized
            else:
                display_name = re.sub(r'(?i)^(HỒ SƠ( CỦA)?|HOSO|HO SO)\s+', '', current_folder_name).strip()
                file_person_name = normalize_vietnamese_name(display_name)
                
            for fname in sorted(filenames):
                if fname.startswith('.') or fname.startswith('_'):
                    continue
                fpath = os.path.join(root, fname)
                if not os.path.isfile(fpath):
                    continue
                rel_path = os.path.relpath(fpath, input_dir).replace("\\", "/")
                sub_path = os.path.relpath(fpath, folder_path).replace("\\", "/")
                ext = os.path.splitext(fname)[1].lower()
                files_in_folder.append({
                    "filename": fname,
                    "path": fpath,
                    "rel_path": rel_path,
                    "sub_path": sub_path,
                    "ext": ext,
                    "person_name": file_person_name,
                })
        if files_in_folder:
            folders_data[item] = {
                "folder_name": item,
                "person_name": person_normalized,
                "files": files_in_folder,
            }

    # Also collect files in root (not in any subfolder)
    root_files = []
    for fname in sorted(os.listdir(input_dir)):
        if fname.startswith('.') or fname.startswith('_'):
            continue
        fpath = os.path.join(input_dir, fname)
        if os.path.isfile(fpath):
            ext = os.path.splitext(fname)[1].lower()
            root_files.append({
                "filename": fname,
                "path": fpath,
                "rel_path": fname,
                "sub_path": fname,
                "ext": ext,
                "person_name": "UNKNOWN",
            })
    if root_files:
        folders_data["__ROOT__"] = {
            "folder_name": "(Root)",
            "person_name": "UNKNOWN",
            "files": root_files,
        }

    # ── Classify all files in parallel ──
    _quota_stop = threading.Event()

    all_results = []

    # Setup progress tracking
    total_files = sum(len(fd["files"]) for fd in folders_data.values())
    _precheck_progress.update({"total": total_files, "done": 0, "current_file": "", "running": True})

    # Build flat list of (file_info, person_name, folder_key)
    all_tasks = []
    for folder_key, folder_data in folders_data.items():
        for file_info in folder_data["files"]:
            file_person_name = file_info.get("person_name", folder_data["person_name"])
            all_tasks.append((file_info, file_person_name, folder_key))

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_map = {}
        for file_info, person_name, folder_key in all_tasks:
            if _quota_stop.is_set():
                # Quota exhausted — skip remaining
                all_results.append({
                    **file_info,
                    "person_name": person_name,
                    "doc_type_en": "QUOTA ERROR",
                    "doc_owner": "",
                    "suggested_name": file_info["filename"],
                    "needs_split": False,
                    "doc_count": 1,
                    "doc_types": ["ERROR"],
                    "error": "Skipped: API quota exhausted",
                    "quota_error": True,
                })
                continue
            future = executor.submit(classify_one, file_info, person_name, llm, _quota_stop)
            future_map[future] = (folder_key, file_info, person_name)

        for future in as_completed(future_map):
            result = future.result()
            folder_key, file_info, person_name = future_map[future]
            _precheck_progress["done"] = _precheck_progress.get("done", 0) + 1
            _precheck_progress["current_file"] = file_info["filename"]
            all_results.append(result)
            if _quota_stop.is_set():
                for pending in future_map:
                    pending.cancel()

    # Group results back by folder
    folder_results = {}
    for r in all_results:
        for folder_key, folder_data in folders_data.items():
            if any(f["path"] == r["path"] for f in folder_data["files"]):
                if folder_key not in folder_results:
                    folder_results[folder_key] = {
                        "folder_name": folder_data["folder_name"],
                        "person_name": folder_data["person_name"],
                        "files": [],
                    }
                folder_results[folder_key]["files"].append(r)
                break

    # Handle duplicate suggested names within each folder
    for folder_key, folder_data in folder_results.items():
        name_counts = {}
        for f in sorted(folder_data["files"], key=lambda x: x["filename"]):
            sname = f["suggested_name"]
            if sname in name_counts:
                name_counts[sname] += 1
                base, ext = os.path.splitext(sname)
                f["suggested_name"] = f"{base}_({name_counts[sname]}){ext}"
            else:
                name_counts[sname] = 0

    # Sort files within each folder
    for folder_data in folder_results.values():
        folder_data["files"].sort(key=lambda x: x["filename"])

    folders_output = sorted(folder_results.values(), key=lambda x: x["folder_name"])

    total_files = sum(len(f["files"]) for f in folders_output)
    multi_count = sum(1 for r in all_results if r.get("needs_split"))
    quota_errors = sum(1 for r in all_results if r.get("quota_error"))
    translate_count = sum(1 for r in all_results if r.get("is_translate"))

    # Reset progress
    _precheck_progress.update({"total": total_files, "done": total_files, "current_file": "", "running": False})

    return jsonify({
        "status": "done",
        "input_dir": input_dir,
        "total_files": total_files,
        "multi_doc_count": multi_count,
        "clean_count": total_files - multi_count - translate_count,
        "translate_count": translate_count,
        "folders": folders_output,
        "quota_exhausted": quota_errors > 0,
        "quota_error_count": quota_errors,
    })
