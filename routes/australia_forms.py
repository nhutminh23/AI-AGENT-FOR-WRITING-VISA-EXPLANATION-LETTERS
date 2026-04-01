"""
Australia visa form auto-fill routes.
Serves the Australia forms frontend and handles JSON-based form filling
and PDF generation for Form 54 (Family Composition).

Workflow: Copy Prompt → Paste JSON → Review → Fill PDF
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory, send_file
from werkzeug.utils import secure_filename

from config import Config

logger = logging.getLogger(__name__)

australia_forms_bp = Blueprint("australia_forms", __name__)

# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------
AU_BASE_DIR = Path(__file__).resolve().parent.parent / "australia_forms"
AU_FRONTEND_DIR = AU_BASE_DIR / "frontend"
AU_OUTPUT_DIR = Path(Config.AUSTRALIA_FORMS_OUTPUT_DIR)
AU_TEMPLATE_DIR = Path(Config.AUSTRALIA_FORMS_TEMPLATE_DIR)


# ---------------------------------------------------------------------------
# Frontend serving
# ---------------------------------------------------------------------------
@australia_forms_bp.get("/australia")
@australia_forms_bp.get("/australia/")
def australia_index():
    return send_from_directory(str(AU_FRONTEND_DIR), "index.html")


@australia_forms_bp.get("/australia/static/<path:filename>")
def australia_static(filename: str):
    return send_from_directory(str(AU_FRONTEND_DIR), filename)


# ---------------------------------------------------------------------------
# API: Get Grok prompt template
# ---------------------------------------------------------------------------
@australia_forms_bp.get("/australia/api/prompt-template-54")
def australia_prompt_template_54():
    """Return the Grok prompt template text for Form 54."""
    template_path = AU_BASE_DIR / "grok_prompt_54.md"
    if not template_path.exists():
        return jsonify({"error": "Prompt template not found"}), 404

    content = template_path.read_text(encoding="utf-8")

    # Extract just the prompt section
    marker = "## PROMPT (Copy từ đây)"
    idx = content.find(marker)
    if idx != -1:
        prompt_text = content[idx + len(marker):].strip()
    else:
        prompt_text = content

    return jsonify({"prompt": prompt_text})


# ---------------------------------------------------------------------------
# API: Fill Form 54 PDF
# ---------------------------------------------------------------------------
@australia_forms_bp.post("/australia/api/fill-54")
def australia_fill_54():
    """Fill Australia Form 54 PDF with provided JSON data."""
    data = request.get_json(silent=True) or {}
    form_fields = data.get("form_fields")

    if not form_fields:
        return jsonify({"error": "Missing form_fields"}), 400

    logger.info("=== AU FORM 54 FILL: %d keys ===", len(form_fields))

    # Find template
    template_path = AU_TEMPLATE_DIR / "54.pdf"
    if not template_path.exists():
        return jsonify({
            "error": f"Template not found: {template_path}. "
                     f"Please place 54.pdf in {AU_TEMPLATE_DIR}"
        }), 404

    # Output path
    AU_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session_id = str(uuid.uuid4())[:8]
    output_filename = f"Form54_filled_{session_id}.pdf"
    output_path = AU_OUTPUT_DIR / output_filename

    try:
        from australia_forms.fill_54 import fill_form54
        fill_form54(form_fields, template_path, output_path)

        return jsonify({
            "success": True,
            "filename": output_filename,
            "download_url": f"/australia/api/download/{output_filename}",
        })
    except Exception as exc:
        import logging; logging.exception("[Safe Log] Unhandled exception in australia_forms.py: %s", exc)
        logger.exception("Form 54 PDF fill failed")
        return jsonify({"error": f"PDF fill failed: {str(exc)}"}), 500


# ---------------------------------------------------------------------------
# API: Download filled PDF
# ---------------------------------------------------------------------------
@australia_forms_bp.get("/australia/api/download/<filename>")
def australia_download(filename: str):
    """Download a filled PDF."""
    filepath = AU_OUTPUT_DIR / secure_filename(filename)
    if not filepath.exists():
        return jsonify({"error": "File not found"}), 404

    return send_file(
        str(filepath),
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


# ---------------------------------------------------------------------------
# API: Check template availability
# ---------------------------------------------------------------------------
@australia_forms_bp.get("/australia/api/check-template")
def australia_check_template():
    """Check if PDF template is available."""
    t54 = AU_TEMPLATE_DIR / "54.pdf"
    return jsonify({
        "available": t54.exists(),
        "form54_available": t54.exists(),
        "path": str(AU_TEMPLATE_DIR),
    })
