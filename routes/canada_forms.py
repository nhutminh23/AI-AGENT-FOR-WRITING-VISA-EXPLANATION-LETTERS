"""
Canada visa form auto-fill routes.
Serves the Canada forms frontend and handles JSON-based form filling
and PDF generation for IMM5645E.

Simplified workflow: Copy Prompt → Paste JSON → Review → Fill PDF
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory, send_file
from werkzeug.utils import secure_filename

from config import Config

logger = logging.getLogger(__name__)

canada_forms_bp = Blueprint("canada_forms", __name__)

# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------
CANADA_BASE_DIR = Path(__file__).resolve().parent.parent / "canada_forms"
CANADA_FRONTEND_DIR = CANADA_BASE_DIR / "frontend"
CANADA_OUTPUT_DIR = Path(Config.CANADA_FORMS_OUTPUT_DIR)
CANADA_TEMPLATE_DIR = Path(Config.CANADA_FORMS_TEMPLATE_DIR)


# ---------------------------------------------------------------------------
# Frontend serving
# ---------------------------------------------------------------------------
@canada_forms_bp.get("/canada")
@canada_forms_bp.get("/canada/")
def canada_index():
    return send_from_directory(str(CANADA_FRONTEND_DIR), "index.html")


@canada_forms_bp.get("/canada/static/<path:filename>")
def canada_static(filename: str):
    return send_from_directory(str(CANADA_FRONTEND_DIR), filename)


# ---------------------------------------------------------------------------
# API: Get Grok prompt template
# ---------------------------------------------------------------------------
@canada_forms_bp.get("/canada/api/prompt-template")
def canada_prompt_template():
    """Return the Grok prompt template text for the frontend to display."""
    template_path = CANADA_BASE_DIR / "grok_prompt_template.md"
    if not template_path.exists():
        return jsonify({"error": "Prompt template not found"}), 404

    content = template_path.read_text(encoding="utf-8")

    # Extract just the prompt section (after "## PROMPT (Copy từ đây)")
    marker = "## PROMPT (Copy từ đây)"
    idx = content.find(marker)
    if idx != -1:
        prompt_text = content[idx + len(marker):].strip()
    else:
        prompt_text = content

    return jsonify({"prompt": prompt_text})


# ---------------------------------------------------------------------------
# API: Fill IMM5645E PDF
# ---------------------------------------------------------------------------
@canada_forms_bp.post("/canada/api/fill")
def canada_fill():
    """Fill IMM5645E PDF form with provided data."""
    data = request.get_json(silent=True) or {}
    form_fields = data.get("form_fields")

    if not form_fields:
        return jsonify({"error": "Missing form_fields"}), 400

    # DEBUG: Log child/sibling keys to trace duplicate issue
    child_sib_keys = {k: v for k, v in sorted(form_fields.items())
                      if 'child' in k or 'sibling' in k or 'accomp' in k}
    logger.info("=== FORM DATA DEBUG: child/sibling keys ===")
    for k, v in child_sib_keys.items():
        logger.info("  %s = %s", k, str(v)[:50])

    # Find template
    template_path = CANADA_TEMPLATE_DIR / "imm5645e.pdf"
    if not template_path.exists():
        return jsonify({
            "error": f"Template not found: {template_path}. "
                     f"Please place imm5645e.pdf in {CANADA_TEMPLATE_DIR}"
        }), 404

    # Output path
    CANADA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    import uuid
    session_id = str(uuid.uuid4())[:8]
    output_filename = f"IMM5645E_filled_{session_id}.pdf"
    output_path = CANADA_OUTPUT_DIR / output_filename

    try:
        from canada_forms.fill_imm5645 import fill_imm5645
        fill_imm5645(form_fields, template_path, output_path)

        return jsonify({
            "success": True,
            "filename": output_filename,
            "download_url": f"/canada/api/download/{output_filename}",
        })
    except Exception as exc:
        logger.exception("PDF fill failed")
        return jsonify({"error": f"PDF fill failed: {str(exc)}"}), 500


# ---------------------------------------------------------------------------
# API: Download filled PDF
# ---------------------------------------------------------------------------
@canada_forms_bp.get("/canada/api/download/<filename>")
def canada_download(filename: str):
    """Download a filled PDF."""
    filepath = CANADA_OUTPUT_DIR / secure_filename(filename)
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
@canada_forms_bp.get("/canada/api/check-template")
def canada_check_template():
    """Check if the IMM5645E template PDF is available."""
    template_path = CANADA_TEMPLATE_DIR / "imm5645e.pdf"
    return jsonify({
        "available": template_path.exists(),
        "path": str(template_path),
    })
