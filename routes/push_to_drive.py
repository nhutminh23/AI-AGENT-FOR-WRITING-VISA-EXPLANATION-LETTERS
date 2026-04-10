"""
Push-to-Drive routes: Upload processed files back to Google Drive.

After IT finishes renaming/splitting in the Precheck UI, this endpoint:
1. Reads _meta.json to find the original Drive folder.
2. Creates a 'Final' subfolder on Drive.
3. Uploads all files from the local folder into Final/.
4. Renames the Drive folder to '-CHECK' to trigger bot validation.
5. Cleans up the local folder.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

from flask import Blueprint, jsonify, request

push_to_drive_bp = Blueprint("push_to_drive", __name__)
logger = logging.getLogger("routes.push_to_drive")


def _get_drive_ui():
    """Lazily initialise DriveUIHacker with credentials from env."""
    from sync.drive_ui_hacker import DriveUIHacker
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    if not Path(creds_path).exists():
        raise FileNotFoundError(f"Google credentials not found: {creds_path}")
    return DriveUIHacker(creds_path)


@push_to_drive_bp.post("/api/processor/push-to-drive")
def push_to_drive():
    """
    Upload all files from a local input subfolder back to Google Drive.

    Expects JSON body:
        { "local_folder": "input/UC - CHU HIEP_abc123" }

    Workflow:
    1. Read _meta.json → get drive_folder_id + base_name
    2. Create 'Final' subfolder on Drive
    3. Upload every file (skip _meta.json and hidden files)
    4. Rename Drive folder to '{base_name} - CHECK'
    5. Delete local folder
    """
    payload = request.get_json(force=True) or {}
    local_folder = payload.get("local_folder", "")

    if not local_folder or not os.path.isdir(local_folder):
        return jsonify({"error": "folder_not_found", "path": local_folder}), 404

    # 1. Read _meta.json
    meta_path = os.path.join(local_folder, "_meta.json")
    if not os.path.isfile(meta_path):
        return jsonify({
            "error": "no_meta_json",
            "detail": "This folder was not downloaded by Drive Watcher. "
                      "Missing _meta.json — cannot determine Drive target.",
        }), 400

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    drive_folder_id = meta.get("drive_folder_id")
    base_name = meta.get("base_name", "Unknown")

    if not drive_folder_id:
        return jsonify({"error": "invalid_meta", "detail": "drive_folder_id missing"}), 400

    # 2. Connect to Drive
    try:
        ui = _get_drive_ui()
    except FileNotFoundError as exc:
        return jsonify({"error": "credentials_not_found", "detail": str(exc)}), 500

    # 3. Create 'Final' subfolder on Drive
    try:
        final_id = ui.create_subfolder(drive_folder_id, "Final")
    except Exception as exc:
        logger.exception("Failed to create Final subfolder on Drive")
        return jsonify({"error": "drive_create_folder_failed", "detail": str(exc)}), 500

    # 4. Upload all files (recursively)
    uploaded_count = 0
    errors = []

    def _upload_dir(local_dir: str, drive_parent_id: str):
        nonlocal uploaded_count
        for item in sorted(os.listdir(local_dir)):
            item_path = os.path.join(local_dir, item)

            # Skip hidden files and _meta.json
            if item.startswith(".") or item.startswith("_"):
                continue

            if os.path.isdir(item_path):
                # Create subfolder on Drive and recurse
                try:
                    sub_id = ui.create_subfolder(drive_parent_id, item)
                    _upload_dir(item_path, sub_id)
                except Exception as exc:
                    logger.error("Failed to create/upload subfolder '%s': %s", item, exc)
                    errors.append({"file": item, "error": str(exc)})
            else:
                try:
                    ui.upload_file(drive_parent_id, item_path, item)
                    uploaded_count += 1
                except Exception as exc:
                    logger.error("Failed to upload '%s': %s", item, exc)
                    errors.append({"file": item, "error": str(exc)})

    try:
        _upload_dir(local_folder, final_id)
    except Exception as exc:
        logger.exception("Upload loop failed")
        return jsonify({"error": "upload_failed", "detail": str(exc)}), 500

    # 5. Rename Drive folder to trigger -CHECK
    try:
        from sync.validator import extract_base_name
        clean_base = extract_base_name(base_name)
        new_name = f"{clean_base} - CHECK"
        ui.rename(drive_folder_id, new_name)
        logger.info("Renamed Drive folder to '%s'", new_name)
    except Exception as exc:
        logger.error("Failed to rename Drive folder: %s", exc)
        # Non-fatal: files are already uploaded

    # 6. Clean up local folder
    try:
        shutil.rmtree(local_folder)
        logger.info("Cleaned up local folder: %s", local_folder)
    except Exception as exc:
        logger.warning("Failed to clean up local folder: %s", exc)

    return jsonify({
        "status": "done",
        "uploaded_count": uploaded_count,
        "error_count": len(errors),
        "errors": errors,
        "drive_folder_id": drive_folder_id,
        "base_name": base_name,
    })


@push_to_drive_bp.get("/api/processor/drive-folders")
def list_drive_folders():
    """
    List local input subfolders that have _meta.json (were downloaded from Drive).

    Returns a list of folders with their metadata for the UI dropdown.
    """
    project_root = Path(__file__).parent.parent
    input_dir = project_root / "input"

    if not input_dir.is_dir():
        return jsonify({"folders": []})

    folders = []
    for item in sorted(os.listdir(input_dir)):
        item_path = input_dir / item
        if not item_path.is_dir():
            continue

        meta_path = item_path / "_meta.json"
        if meta_path.is_file():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            # Count files (excluding _meta.json and hidden)
            file_count = sum(
                1 for root, _, files in os.walk(item_path)
                for fn in files
                if not fn.startswith(".") and not fn.startswith("_")
            )
            folders.append({
                "local_path": str(item_path),
                "dir_name": item,
                "base_name": meta.get("base_name", item),
                "drive_folder_id": meta.get("drive_folder_id", ""),
                "file_count": file_count,
            })

    return jsonify({"folders": folders})
