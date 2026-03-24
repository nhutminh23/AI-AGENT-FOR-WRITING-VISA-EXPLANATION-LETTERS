"""
Canada visa form auto-fill routes.
Serves the Canada forms frontend and handles document upload, AI extraction,
and PDF form filling.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
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
CANADA_INPUT_DIR = Path(Config.CANADA_FORMS_INPUT_DIR)
CANADA_OUTPUT_DIR = Path(Config.CANADA_FORMS_OUTPUT_DIR)
CANADA_TEMPLATE_DIR = Path(Config.CANADA_FORMS_TEMPLATE_DIR)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}


def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


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
# API: Upload documents
# ---------------------------------------------------------------------------
@canada_forms_bp.post("/canada/api/upload")
def canada_upload():
    """Upload document files for extraction."""
    CANADA_INPUT_DIR.mkdir(parents=True, exist_ok=True)

    if "files" not in request.files:
        return jsonify({"error": "No files uploaded"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files selected"}), 400

    # Create a unique session folder
    session_id = str(uuid.uuid4())[:8]
    session_dir = CANADA_INPUT_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    for f in files:
        if f.filename and _allowed_file(f.filename):
            filename = secure_filename(f.filename)
            filepath = session_dir / filename
            f.save(str(filepath))
            uploaded.append({
                "filename": filename,
                "size": os.path.getsize(str(filepath)),
            })
        else:
            logger.warning("Skipped unsupported file: %s", f.filename)

    if not uploaded:
        return jsonify({"error": "No valid files uploaded"}), 400

    return jsonify({
        "session_id": session_id,
        "files": uploaded,
        "count": len(uploaded),
    })


# ---------------------------------------------------------------------------
# API: AI Extract family info
# ---------------------------------------------------------------------------
@canada_forms_bp.post("/canada/api/extract")
def canada_extract():
    """Extract family information from uploaded documents using AI."""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")

    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400

    session_dir = CANADA_INPUT_DIR / session_id
    if not session_dir.exists():
        return jsonify({"error": "Session not found. Please upload files first."}), 404

    # Collect all files
    file_paths = []
    for f in session_dir.iterdir():
        if f.is_file() and _allowed_file(f.name):
            file_paths.append(str(f))

    if not file_paths:
        return jsonify({"error": "No valid files found in session"}), 400

    try:
        from canada_forms.agent import extract_family_info
        result = extract_family_info(file_paths)

        # Save extraction result for later use
        result_path = session_dir / "extraction_result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return jsonify({
            "raw": result["raw"],
            "form_fields": result["form_fields"],
            "confidence": result["confidence"],
            "files_processed": len(file_paths),
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("AI extraction failed")
        return jsonify({"error": f"AI extraction failed: {str(exc)}"}), 500


# ---------------------------------------------------------------------------
# API: Fill IMM5645E PDF
# ---------------------------------------------------------------------------
@canada_forms_bp.post("/canada/api/fill")
def canada_fill():
    """Fill IMM5645E PDF form with provided data."""
    data = request.get_json(silent=True) or {}
    form_fields = data.get("form_fields")
    session_id = data.get("session_id", "manual")

    if not form_fields:
        return jsonify({"error": "Missing form_fields"}), 400

    # Find template
    template_path = CANADA_TEMPLATE_DIR / "imm5645e.pdf"
    if not template_path.exists():
        return jsonify({
            "error": f"Template not found: {template_path}. Please place imm5645e.pdf in {CANADA_TEMPLATE_DIR}"
        }), 404

    # Output path
    CANADA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
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
# API: Get field metadata (for frontend form building)
# ---------------------------------------------------------------------------
@canada_forms_bp.get("/canada/api/fields")
def canada_fields():
    """Return field metadata for IMM5645E form."""
    from canada_forms.fill_imm5645 import get_field_list
    return jsonify({"fields": get_field_list()})


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
