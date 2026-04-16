"""
Letter Generation V3 routes.
Serves frontend + API endpoints for the explanation letter generator.

Workflow: Copy Prompt → Paste JSON → AI Generate → Review → Download DOCX
"""
from __future__ import annotations

import io
import json
import logging
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

logger = logging.getLogger(__name__)

letter_gen_bp = Blueprint("letter_gen", __name__)

# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------
LETTER_GEN_BASE = Path(__file__).resolve().parent.parent / "letter_gen"


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
# API: Build Group Participant List PDF (direct download)
# ---------------------------------------------------------------------------
@letter_gen_bp.post("/api/letter-gen/build-group-pdf")
def letter_gen_build_group_pdf():
    """Build Group Tour Participant List as PDF and return for direct download."""
    data = request.get_json(silent=True) or {}
    participants = data.get("participants", [])
    group_id = data.get("group_id", "")
    group_label = data.get("group_label", "")

    if not participants or len(participants) < 2:
        return jsonify({"error": "Need at least 2 participants for group list"}), 400

    try:
        import io
        import fitz  # PyMuPDF

        doc = fitz.open()
        page = doc.new_page(width=595, height=842)  # A4

        # Title
        title_rect = fitz.Rect(40, 40, 555, 70)
        page.insert_textbox(
            title_rect, "GROUP TOUR PARTICIPANT LIST",
            fontsize=16, fontname="helv", align=fitz.TEXT_ALIGN_CENTER,
            color=(0, 0, 0),
        )

        # Group ID line
        id_text = f"GROUP ID: {group_id or '___________'}"
        if group_label:
            id_text += f" ({group_label})"
        id_rect = fitz.Rect(40, 70, 555, 95)
        page.insert_textbox(
            id_rect, id_text,
            fontsize=12, fontname="helv", align=fitz.TEXT_ALIGN_CENTER,
            color=(0, 0, 0),
        )

        # Table
        headers = ["No.", "Full Name", "Passport No.", "Date of Birth", "Sex", "Date of Expiry"]
        col_x = [40, 75, 235, 340, 420, 475, 555]  # column boundaries
        row_h = 22
        table_y = 110

        # Draw header row
        for i, h in enumerate(headers):
            rect = fitz.Rect(col_x[i], table_y, col_x[i + 1], table_y + row_h)
            page.draw_rect(rect, color=(0, 0, 0), width=0.5)
            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(fill=(0.9, 0.9, 0.9), color=None)
            shape.commit()
            page.draw_rect(rect, color=(0, 0, 0), width=0.5)
            page.insert_textbox(
                fitz.Rect(col_x[i] + 2, table_y + 2, col_x[i + 1] - 2, table_y + row_h - 2),
                h, fontsize=9, fontname="helv", align=fitz.TEXT_ALIGN_CENTER,
                color=(0, 0, 0),
            )

        # Draw data rows
        for idx, p in enumerate(participants):
            y = table_y + row_h * (idx + 1)
            row_data = [
                str(idx + 1),
                p.get("full_name", ""),
                p.get("passport_no", ""),
                p.get("dob", ""),
                p.get("sex", ""),
                p.get("passport_expiry", ""),
            ]
            for i, val in enumerate(row_data):
                rect = fitz.Rect(col_x[i], y, col_x[i + 1], y + row_h)
                page.draw_rect(rect, color=(0, 0, 0), width=0.5)
                align = fitz.TEXT_ALIGN_LEFT if i == 1 else fitz.TEXT_ALIGN_CENTER
                page.insert_textbox(
                    fitz.Rect(col_x[i] + 3, y + 3, col_x[i + 1] - 3, y + row_h - 3),
                    val, fontsize=9, fontname="helv", align=align,
                    color=(0, 0, 0),
                )

        # Save to buffer
        buf = io.BytesIO()
        doc.save(buf)
        doc.close()
        buf.seek(0)

        safe_id = group_id.replace(" ", "_") if group_id else "DRAFT"
        filename = f"Group_Participant_List_{safe_id}.pdf"

        return send_file(
            buf,
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf",
        )
    except Exception as exc:
        logger.exception("Group PDF build failed")
        return jsonify({"error": f"Group PDF build failed: {str(exc)}"}), 500


# ---------------------------------------------------------------------------
# API: Build Invitation Letter DOCX
# ---------------------------------------------------------------------------
@letter_gen_bp.post("/api/letter-gen/build-invitation")
def letter_gen_build_invitation():
    """Build Invitation Letter DOCX and return for direct download."""
    data = request.get_json(silent=True) or {}

    host = data.get("host")

    # Normalize: convert old "guest" (single) → "guests" (array)
    guests = data.get("guests")
    if not guests and data.get("guest"):
        guests = [data["guest"]]
        data["guests"] = guests
        data.pop("guest", None)

    if not host or not guests or len(guests) < 1:
        return jsonify({"error": "Missing host or guests data"}), 400

    try:
        from letter_gen.invitation_builder import build_invitation_letter_docx

        file_stream = build_invitation_letter_docx(data)

        first_guest_name = (guests[0].get("full_name") or "Guest").replace(" ", "_")
        if len(guests) > 1:
            filename = f"Invitation_Letter_{first_guest_name}_and_{len(guests)-1}_others.docx"
        else:
            filename = f"Invitation_Letter_{first_guest_name}.docx"

        return send_file(
            file_stream,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception as exc:
        logger.exception("Invitation letter build failed")
        return jsonify({"error": f"Invitation letter build failed: {str(exc)}"}), 500


# ---------------------------------------------------------------------------
# API: Simulate Scan — convert any uploaded PDF to "scanned" PDF
# ---------------------------------------------------------------------------
@letter_gen_bp.post("/api/tools/simulate-scan")
def simulate_scan_pdf():
    """
    Accept a PDF file upload, apply scan effects, return scanned PDF.
    Optional form fields:
      - grayscale: "true"/"false" (default true)
      - preserve_color: "true"/"false" (default false)
      - noise: int 0-30 (default 12)
      - tilt: float 0-3 (default 0.8)
    """
    if "pdf_file" not in request.files:
        return jsonify({"error": "Missing pdf_file in upload"}), 400

    pdf_file = request.files["pdf_file"]
    if not pdf_file.filename:
        return jsonify({"error": "Empty filename"}), 400

    try:
        from services.scan_simulator import simulate_scan

        pdf_bytes = pdf_file.read()

        # Parse optional params
        grayscale = request.form.get("grayscale", "true").lower() == "true"
        preserve_color = request.form.get("preserve_color", "false").lower() == "true"
        noise = int(request.form.get("noise", "12"))
        tilt = float(request.form.get("tilt", "0.8"))

        scanned_bytes = simulate_scan(
            pdf_bytes,
            grayscale=grayscale,
            preserve_signature_color=preserve_color,
            noise_level=min(max(noise, 0), 30),
            tilt_max=min(max(tilt, 0), 3.0),
        )

        result_stream = io.BytesIO(scanned_bytes)
        result_stream.seek(0)

        # Derive filename
        orig_name = pdf_file.filename.rsplit(".", 1)[0] if "." in pdf_file.filename else pdf_file.filename
        filename = f"{orig_name}_scanned.pdf"

        return send_file(
            result_stream,
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf",
        )
    except Exception as exc:
        logger.exception("Scan simulation failed")
        return jsonify({"error": f"Scan simulation failed: {str(exc)}"}), 500


# ---------------------------------------------------------------------------
# API: Build Invitation Letter DOCX with Signature → Convert to PDF → Scan
# ---------------------------------------------------------------------------
@letter_gen_bp.post("/api/letter-gen/build-invitation-scan")
def letter_gen_build_invitation_scan():
    """
    Build invitation letter DOCX, optionally insert signature image,
    convert to PDF via docx2pdf (MS Word on Windows),
    then apply scan simulation effects.

    Accepts multipart/form-data:
      - invitation_data: JSON string with host/guests/trip info
      - signature_image: (optional) PNG/JPG signature image file
      - grayscale: "true"/"false" (default true)
      - preserve_color: "true"/"false" (default false)
    """
    import tempfile
    import os

    invitation_json = request.form.get("invitation_data")
    if not invitation_json:
        return jsonify({"error": "Missing invitation_data"}), 400

    try:
        data = json.loads(invitation_json)
    except json.JSONDecodeError as e:
        return jsonify({"error": f"Invalid invitation_data JSON: {e}"}), 400

    host = data.get("host")
    guests = data.get("guests")
    if not guests and data.get("guest"):
        guests = [data["guest"]]
        data["guests"] = guests
        data.pop("guest", None)

    if not host or not guests or len(guests) < 1:
        return jsonify({"error": "Missing host or guests data"}), 400

    try:
        from letter_gen.invitation_builder import build_invitation_letter_docx
        from services.scan_simulator import simulate_scan

        # --- Step 1: Build invitation DOCX (in memory) ---
        signature_file = request.files.get("signature_image")
        file_stream = build_invitation_letter_docx(data, signature_image=signature_file)

        # --- Step 2: DOCX → PDF via docx2pdf (needs temp files) ---
        with tempfile.TemporaryDirectory() as tmpdir:
            docx_path = os.path.join(tmpdir, "invitation.docx")
            pdf_path = os.path.join(tmpdir, "invitation.pdf")

            with open(docx_path, "wb") as f:
                f.write(file_stream.read())

            from docx2pdf import convert
            convert(docx_path, pdf_path)

            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

        # --- Step 3: Apply scan effects ---
        grayscale = request.form.get("grayscale", "true").lower() == "true"
        preserve_color = request.form.get("preserve_color", "false").lower() == "true"

        scanned_bytes = simulate_scan(
            pdf_bytes,
            grayscale=grayscale,
            preserve_signature_color=preserve_color,
        )

        result_stream = io.BytesIO(scanned_bytes)
        result_stream.seek(0)

        first_guest_name = (guests[0].get("full_name") or "Guest").replace(" ", "_")
        filename = f"Invitation_Letter_{first_guest_name}_SCANNED.pdf"

        return send_file(
            result_stream,
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf",
        )
    except Exception as exc:
        logger.exception("Invitation scan build failed")
        return jsonify({"error": f"Invitation scan build failed: {str(exc)}"}), 500

