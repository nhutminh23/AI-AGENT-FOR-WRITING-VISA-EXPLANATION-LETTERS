"""
Letter Generation V3 routes.
Serves frontend + API endpoints for the explanation letter generator.

Workflow: Copy Prompt → Paste JSON → AI Generate → Review → Download DOCX
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from config import Config

logger = logging.getLogger(__name__)

letter_gen_bp = Blueprint("letter_gen", __name__)

# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------
LETTER_GEN_BASE = Path(__file__).resolve().parent.parent / "letter_gen"
LETTER_GEN_OUTPUT = Path(Config.LETTER_GEN_OUTPUT_DIR)


# ---------------------------------------------------------------------------
# API: Get Grok prompt template
# ---------------------------------------------------------------------------
@letter_gen_bp.get("/api/letter-gen/prompt-template")
def letter_gen_prompt_template():
    """Return the Grok prompt template text for the frontend to display."""
    template_path = LETTER_GEN_BASE / "grok_prompt_letter.md"
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
# API: Generate letters from JSON profile
# ---------------------------------------------------------------------------
@letter_gen_bp.post("/api/letter-gen/generate")
def letter_gen_generate():
    """Generate explanation letter(s) from JSON profile."""
    data = request.get_json(silent=True) or {}
    profile = data.get("profile")
    additional_context = data.get("additional_context", "")

    if not profile:
        return jsonify({"error": "Missing profile JSON"}), 400

    if not isinstance(profile, dict):
        return jsonify({"error": "profile must be a JSON object"}), 400

    # Validate minimal required fields
    applicant = profile.get("applicant")
    if not applicant or not applicant.get("full_name"):
        return jsonify({"error": "Profile must contain applicant.full_name"}), 400

    # Group info (optional — sent by frontend when group detected)
    group_info = data.get("group_info")  # {participants, group_id, group_label}

    try:
        from letter_gen.generator import generate_letters
        result = generate_letters(profile, additional_context, group_info=group_info)
        return jsonify(result)
    except Exception as exc:
        logging.exception("[Safe Log] Unhandled exception in letter_gen.py: %s", exc)
        logger.exception("Letter generation failed")
        return jsonify({"error": f"Generation failed: {str(exc)}"}), 500


# ---------------------------------------------------------------------------
# API: Build DOCX from letter text and return download
# ---------------------------------------------------------------------------
@letter_gen_bp.post("/api/letter-gen/build-docx")
def letter_gen_build_docx():
    """Build DOCX from letter text and return download URL."""
    data = request.get_json(silent=True) or {}
    letter_text = data.get("letter_text", "")
    applicant_name = data.get("applicant_name", "Applicant")
    filename_prefix = data.get("filename_prefix", "Explanation_Letter")

    if not letter_text.strip():
        return jsonify({"error": "Missing letter_text"}), 400

    try:
        from letter_gen.docx_builder import build_letter_docx, _sanitize_filename
        import uuid
        
        # Pass output_dir=None to get an in-memory BytesIO object
        file_stream = build_letter_docx(
            letter_text=letter_text,
            applicant_name=applicant_name,
            output_dir=None,
            filename_prefix=filename_prefix,
        )
        
        safe_name = _sanitize_filename(applicant_name)
        session_id = str(uuid.uuid4())[:8]
        filename = f"{filename_prefix}_{safe_name}_{session_id}.docx"

        return send_file(
            file_stream,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as exc:
        logging.exception("[Safe Log] Unhandled exception in letter_gen.py: %s", exc)
        logger.exception("DOCX build failed")
        return jsonify({"error": f"DOCX build failed: {str(exc)}"}), 500


# ---------------------------------------------------------------------------
# API: Download generated DOCX
# ---------------------------------------------------------------------------
@letter_gen_bp.get("/api/letter-gen/download/<filename>")
def letter_gen_download(filename: str):
    """Download a generated DOCX file."""
    filepath = LETTER_GEN_OUTPUT / secure_filename(filename)
    if not filepath.exists():
        return jsonify({"error": "File not found"}), 404

    return send_file(
        str(filepath),
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


# ---------------------------------------------------------------------------
# API: Detect group participants from JSON profile(s)
# ---------------------------------------------------------------------------
@letter_gen_bp.post("/api/letter-gen/detect-group")
def letter_gen_detect_group():
    """
    Detect group participants from one or more JSON profiles.
    Returns participant list if ≥2 people detected.
    """
    data = request.get_json(silent=True) or {}
    profiles = data.get("profiles")  # can be list or dict

    if not profiles:
        return jsonify({"is_group": False, "participants": []})

    try:
        from letter_gen.group_builder import detect_group_participants
        participants = detect_group_participants(profiles)
        return jsonify({
            "is_group": len(participants) >= 2,
            "participants": participants,
            "count": len(participants),
        })
    except Exception as exc:
        logger.exception("Group detection failed")
        return jsonify({"error": f"Detection failed: {str(exc)}"}), 500


# ---------------------------------------------------------------------------
# API: Build Group Participant List DOCX
# ---------------------------------------------------------------------------
@letter_gen_bp.post("/api/letter-gen/build-group-docx")
def letter_gen_build_group_docx():
    """Build Group Tour Participant List DOCX and return for download."""
    data = request.get_json(silent=True) or {}
    participants = data.get("participants", [])
    group_id = data.get("group_id", "")

    if not participants or len(participants) < 2:
        return jsonify({"error": "Need at least 2 participants for group list"}), 400

    try:
        from letter_gen.group_builder import build_group_docx
        import uuid

        file_stream = build_group_docx(participants, group_id)
        session_id = str(uuid.uuid4())[:8]
        filename = f"Group_Participant_List_{session_id}.docx"

        return send_file(
            file_stream,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as exc:
        logger.exception("Group DOCX build failed")
        return jsonify({"error": f"Group DOCX build failed: {str(exc)}"}), 500
