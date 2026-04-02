"""
DS-160 autofill integration routes.
Serves DS-160 frontend and proxies its API logic under /ds160.
"""
from __future__ import annotations
import logging

import importlib
import json
import sys
from pathlib import Path

from flask import Blueprint, jsonify, send_from_directory

ds160_bp = Blueprint("ds160", __name__)

DS160_BASE_DIR = Path(__file__).resolve().parent.parent / "autofill ds160"
DS160_FRONTEND_DIR = DS160_BASE_DIR / "frontend"
DS160_ASSETS_DIR = DS160_BASE_DIR / "assets"
DS160_INPUT_DIR = DS160_BASE_DIR / "input"
DS160_OUTPUT_DIR = DS160_BASE_DIR / "output"
DS160_SCRIPT_DIR = DS160_BASE_DIR / "script"
DS160_NOTES_PATH = DS160_BASE_DIR / "notes.md"


def _ensure_ds160_path() -> None:
    ds160_path = str(DS160_BASE_DIR)
    if ds160_path not in sys.path:
        sys.path.insert(0, ds160_path)


def _get_ds160_modules():
    _ensure_ds160_path()
    docx_reader = importlib.import_module("docx_reader")
    agent = importlib.import_module("agent")
    config_injector = importlib.import_module("config_injector")
    return docx_reader, agent, config_injector


@ds160_bp.get("/ds160")
@ds160_bp.get("/ds160/")
def ds160_index():
    return send_from_directory(str(DS160_FRONTEND_DIR), "index.html")


@ds160_bp.get("/ds160/static/<path:filename>")
def ds160_static(filename: str):
    return send_from_directory(str(DS160_FRONTEND_DIR), filename)


@ds160_bp.get("/ds160/assets/<path:filename>")
def ds160_assets(filename: str):
    return send_from_directory(str(DS160_ASSETS_DIR), filename)


@ds160_bp.get("/ds160/api/check-input")
def ds160_check_input():
    DS160_INPUT_DIR.mkdir(parents=True, exist_ok=True)
    input_files = []
    for ext in ("*.docx", "*.pdf"):
        input_files.extend(DS160_INPUT_DIR.glob(ext))
    input_files = [f for f in input_files if not f.name.startswith("~$")]
    return jsonify(
        {
            "hasFiles": len(input_files) > 0,
            "files": [f.name for f in input_files],
            "count": len(input_files),
        }
    )


@ds160_bp.get("/ds160/api/output")
def ds160_get_output():
    _, _, config_injector = _get_ds160_modules()
    configs_path = DS160_OUTPUT_DIR / "configs.json"
    if not configs_path.exists():
        return (
            jsonify({"detail": "Chua co ket qua da luu. Hay nhan 'Xu ly du lieu' truoc."}),
            404,
        )

    configs = json.loads(configs_path.read_text(encoding="utf-8"))
    results = []
    for filename, config_key, display_name in config_injector.SCRIPT_ORDER:
        script_path = DS160_OUTPUT_DIR / filename
        full_script = script_path.read_text(encoding="utf-8") if script_path.exists() else ""
        results.append(
            {
                "filename": filename,
                "configKey": config_key,
                "displayName": display_name,
                "config": configs.get(config_key, {}),
                "fullScript": full_script,
            }
        )

    return jsonify({"scripts": results, "source": "saved"})


@ds160_bp.post("/ds160/api/process")
def ds160_process():
    docx_reader, agent, config_injector = _get_ds160_modules()
    DS160_INPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_files = docx_reader.read_all_input_files(str(DS160_INPUT_DIR))
    if not input_files:
        return (
            jsonify(
                {
                    "detail": (
                        "Khong tim thay file .docx hoac .pdf nao trong thu muc /input. "
                        "Hay dat file vao thu muc input/."
                    )
                }
            ),
            400,
        )

    docx_content = "\n\n".join(f"=== FILE: {fname} ===\n{content}" for fname, content in input_files.items())
    rules = docx_reader.read_notes(str(DS160_NOTES_PATH))

    try:
        configs = agent.run_agent(docx_content, rules)
    except Exception as exc:  # pragma: no cover - integration error path
        logging.exception("[Safe Log] Unhandled exception in ds160.py: %s", exc)
        return jsonify({"detail": f"Loi khi goi AI Agent: {exc}"}), 500

    try:
        results = config_injector.inject_configs(str(DS160_SCRIPT_DIR), configs, str(DS160_OUTPUT_DIR))
    except Exception as exc:  # pragma: no cover - integration error path
        logging.exception("[Safe Log] Unhandled exception in ds160.py: %s", exc)
        return jsonify({"detail": f"Loi khi inject config vao script: {exc}"}), 500

    return jsonify({"scripts": results, "source": "generated"})
