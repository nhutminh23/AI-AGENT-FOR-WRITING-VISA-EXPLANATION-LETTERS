"""
Project management routes.
CRUD operations for projects + clear project data.
"""
from __future__ import annotations

import json
import logging
import os
import shutil

from flask import Blueprint, jsonify, request

import database as db
from config import Config

projects_bp = Blueprint("projects", __name__)


@projects_bp.post("/api/projects")
def create_project():
    payload = request.get_json(force=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Project name is required"}), 400
    project = db.create_project(name)
    return jsonify(project)


@projects_bp.get("/api/projects")
def list_projects():
    projects = db.list_projects()
    return jsonify({"projects": projects})


@projects_bp.get("/api/projects/<int:project_id>")
def get_project(project_id):
    project = db.get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(project)


@projects_bp.put("/api/projects/<int:project_id>")
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


@projects_bp.delete("/api/projects/<int:project_id>")
def delete_project(project_id):
    """Delete project from DB AND purge all associated files from disk."""
    project = db.get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    # --- Cascade: purge files from disk before removing DB record ---
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 1. Remove uploaded source PDFs (splitter_uploads/p{id}__*.pdf)
    upload_dir = os.path.join(base_dir, Config.SPLITTER_UPLOADS_DIR)
    prefix = f"p{project_id}__"
    deleted_uploads = 0
    if os.path.isdir(upload_dir):
        for fname in os.listdir(upload_dir):
            if fname.startswith(prefix) and fname.lower().endswith(".pdf"):
                try:
                    os.remove(os.path.join(upload_dir, fname))
                    deleted_uploads += 1
                except OSError:
                    pass

    # 2. Remove output folders in storage/splitter whose _source.json matches
    output_dir = os.path.join(base_dir, Config.SPLITTER_OUTPUTS_DIR)
    deleted_output_dirs = 0
    if os.path.isdir(output_dir):
        for folder_name in os.listdir(output_dir):
            folder_path = os.path.join(output_dir, folder_name)
            if not os.path.isdir(folder_path):
                continue
            meta_path = os.path.join(folder_path, "_source.json")
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                    if meta.get("project_id") == project_id:
                        shutil.rmtree(folder_path, ignore_errors=True)
                        deleted_output_dirs += 1
                        zip_path = os.path.join(output_dir, f"{folder_name}.zip")
                        if os.path.isfile(zip_path):
                            try:
                                os.remove(zip_path)
                            except OSError:
                                pass
                except Exception as e:
                    logging.debug("Error reading meta %s: %s", meta_path, e)

    # --- Finally remove from DB ---
    db.delete_project(project_id)

    logging.info(
        "Deleted project %d: removed %d uploads, %d output dirs",
        project_id, deleted_uploads, deleted_output_dirs,
    )
    return jsonify({
        "status": "deleted",
        "deleted_uploads": deleted_uploads,
        "deleted_output_dirs": deleted_output_dirs,
    })



@projects_bp.post("/api/projects/<int:project_id>/clear")
def clear_project(project_id: int):
    """Xóa toàn bộ dữ liệu của hồ sơ (DB + file tách AI) để làm người mới. Giữ lại project."""
    project = db.get_project(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    db.clear_project_data(project_id)
    # Xóa file trong splitter_uploads có prefix p{id}__
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level since this file is in routes/
    base_dir = os.path.dirname(base_dir)
    upload_dir = os.path.join(base_dir, Config.SPLITTER_UPLOADS_DIR)
    prefix = f"p{project_id}__"
    deleted_uploads = 0
    if os.path.isdir(upload_dir):
        for fname in os.listdir(upload_dir):
            if fname.startswith(prefix) and fname.lower().endswith(".pdf"):
                try:
                    os.remove(os.path.join(upload_dir, fname))
                    deleted_uploads += 1
                except OSError:
                    pass
    # Xóa thư mục trong splitter_outputs có _source.json với project_id trùng
    output_dir = os.path.join(base_dir, Config.SPLITTER_OUTPUTS_DIR)
    deleted_output_dirs = 0
    if os.path.isdir(output_dir):
        for folder_name in os.listdir(output_dir):
            folder_path = os.path.join(output_dir, folder_name)
            if not os.path.isdir(folder_path):
                continue
            meta_path = os.path.join(folder_path, "_source.json")
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                    if meta.get("project_id") == project_id:
                        shutil.rmtree(folder_path, ignore_errors=True)
                        deleted_output_dirs += 1
                        zip_path = os.path.join(output_dir, f"{folder_name}.zip")
                        if os.path.isfile(zip_path):
                            try:
                                os.remove(zip_path)
                            except OSError:
                                pass
                except Exception as e:
                    logging.exception("[Safe Log] Unhandled exception in projects.py: %s", e)
                    logging.debug("Error reading meta %s: %s", meta_path, e)
    return jsonify({
        "status": "cleared",
        "deleted_uploads": deleted_uploads,
        "deleted_output_dirs": deleted_output_dirs,
    })
