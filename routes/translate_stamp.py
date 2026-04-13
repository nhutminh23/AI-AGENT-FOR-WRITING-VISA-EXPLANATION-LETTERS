"""
Stamp & Drive routes: stamp_pdf, stamp_preview, push_stamped_to_drive, mark_complete.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path as SplitterPath

from flask import jsonify, request, send_file

from config import Config
from routes.translate_core import (
    splitter_translate_bp,
    _BASE_DIR,
    TRANSLATION_ORIGINALS_DIR,
    _resolve_translate_source_path,
    _html_to_pdf,
    _convert_pdf_to_grayscale,
    _convert_image_to_a4_pdf,
)


# =====================================================================
# Stamp PDF endpoint (simple upload → stamp → return)
# =====================================================================

@splitter_translate_bp.post("/api/translate/stamp_pdf")
def stamp_pdf_endpoint():
    """Stamp a PDF file with company seal + edge seal (giáp lai).

    Accepts a PDF file upload, applies stamps, returns the stamped PDF.
    """
    from pdf_tools.stamper import stamp_pdf
    import tempfile

    if "file" not in request.files:
        return jsonify({"error": "no_file"}), 400

    pdf_file = request.files["file"]
    if not pdf_file.filename:
        return jsonify({"error": "empty_filename"}), 400

    # Save uploaded PDF to temp
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, dir=TRANSLATION_ORIGINALS_DIR) as tmp:
        pdf_file.save(tmp)
        tmp_path = tmp.name

    try:
        # Output path
        base = os.path.splitext(pdf_file.filename)[0]
        output_name = f"{base}_stamped.pdf"
        output_path = os.path.join(TRANSLATION_ORIGINALS_DIR, output_name)

        stamp_pdf(tmp_path, output_path)

        return send_file(
            output_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=output_name,
        )
    except Exception as exc:
        logging.exception("Stamp PDF failed")
        return jsonify({"error": str(exc)}), 500
    finally:
        # Clean up temp input
        try:
            os.remove(tmp_path)
        except OSError:
            pass


# =====================================================================
# Stamp Preview (merge Original + Translated + Certification → stamp)
# =====================================================================

@splitter_translate_bp.post("/api/translate/stamp_preview")
def stamp_preview():
    """Step 1: Merge Original PDF + Translated PDF + Certification PDF → Stamp → Preview.

    Expects JSON body:
    {
        "workspace": "ÚC - CHÚ HIỆP CÔ CHÍNH - NHÂN",
        "filename": "original_file.pdf",
        "html_content": "<html>...</html>"
    }

    Process:
    1. Convert html_content (bản dịch) → raw translated PDF
    2. Build certification HTML (template Xác nhận dịch) → certification PDF
    3. Find original PDF file in translation_workspace/
    4. Merge: Original → Translated → Certification
    5. Apply stamp_pdf (company stamp + giáp lai)
    6. Return merged + stamped PDF for inline preview.
    """
    from pdf_tools.stamper import stamp_pdf
    import re

    payload = request.get_json(force=True) or {}
    workspace_name = payload.get("workspace", "")
    filename = payload.get("filename", "")
    file_ref = payload.get("file_ref", "")
    html_content = payload.get("html_content", "")

    if not workspace_name or not filename or not html_content:
        return jsonify({"error": "missing_fields", "detail": "workspace, filename, and html_content are required"}), 400

    workspace_root = SplitterPath(Config.TRANSLATION_WORKSPACE_DIR)
    workspace_path = workspace_root / workspace_name

    if not workspace_path.is_dir():
        return jsonify({"error": "workspace_not_found"}), 404

    base_name = os.path.splitext(filename)[0]
    final_pdf_name = f"{base_name}_translated.pdf"

    # Pre-define ALL temp paths with FIXED names (no random garbage)
    html_tmp_path = os.path.join(str(workspace_path), f"_tmp_{base_name}_translate.html")
    translated_pdf_path = os.path.join(str(workspace_path), f"_tmp_{base_name}_translated_raw.pdf")
    cert_html_tmp_path = os.path.join(str(workspace_path), f"_tmp_{base_name}_cert.html")
    cert_pdf_path_tmp = os.path.join(str(workspace_path), f"_tmp_{base_name}_cert_raw.pdf")
    merged_pdf_path = os.path.join(str(workspace_path), f"_tmp_{base_name}_merged.pdf")
    grayscale_pdf_path = os.path.join(str(workspace_path), f"_tmp_{base_name}_grayscale.pdf")
    _converted_img_tmp = None

    # Clean up leftover temp files from previous runs
    for old in [html_tmp_path, translated_pdf_path, cert_html_tmp_path, cert_pdf_path_tmp, merged_pdf_path, grayscale_pdf_path]:
        try: os.remove(old)
        except OSError: pass

    try:
        # ──── Step 1: Convert Translated HTML → PDF ────
        with open(html_tmp_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        _html_to_pdf(html_tmp_path, translated_pdf_path)

        # ──── Step 2: Build Certification HTML → PDF ────
        cert_pdf_path = None
        try:
            cert_template_path = os.path.join("dich", "HTML template", "Xác nhận dịch.html")
            cert_logo_path = os.path.join("dich", "HTML template", "passport_lounge.jpg")

            if os.path.isfile(cert_template_path):
                with open(cert_template_path, "r", encoding="utf-8") as cf:
                    cert_html = cf.read()

                # Embed logo as base64
                if os.path.isfile(cert_logo_path):
                    cert_logo_b64 = base64.b64encode(open(cert_logo_path, "rb").read()).decode("ascii")
                    cert_html = cert_html.replace('src="./passport_lounge.jpg"', f'src="data:image/jpeg;base64,{cert_logo_b64}"')

                # Replace date
                from datetime import datetime as _dt
                now = _dt.now()
                current_date = now.strftime("%d/%m/%Y")
                cert_html = re.sub(r"Date:\s*\d{2}/\d{2}/\d{4}", f"Date: {current_date}", cert_html)

                # Write cert HTML (fixed name — no random)
                with open(cert_html_tmp_path, "w", encoding="utf-8") as cert_f:
                    cert_f.write(cert_html)

                cert_pdf_path = cert_pdf_path_tmp
                _html_to_pdf(cert_html_tmp_path, cert_pdf_path)
        except Exception as cert_err:
            logging.warning("Certification PDF generation failed (skipping): %s", cert_err)
            cert_pdf_path = None

        # ──── Step 3: Locate Original PDF via file_ref ────
        import fitz
        original_pdf_path = None

        # Primary: use file_ref to find the persistent original in uploads/translation_originals/
        if file_ref:
            resolved = _resolve_translate_source_path("input", file_ref)
            if resolved and os.path.isfile(resolved):
                ext = os.path.splitext(resolved)[1].lower()
                if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
                    _converted_img_tmp = _convert_image_to_a4_pdf(resolved)
                    original_pdf_path = _converted_img_tmp
                else:
                    original_pdf_path = resolved
                logging.info("  📄 Found original via file_ref: %s", resolved)

        # Fallback: try workspace folder (in case file was placed there directly)
        if not original_pdf_path:
            candidate = os.path.join(str(workspace_path), filename)
            if os.path.isfile(candidate):
                original_pdf_path = candidate
            else:
                for ext in [".pdf", ".jpg", ".jpeg", ".png"]:
                    candidate = os.path.join(str(workspace_path), base_name + ext)
                    if os.path.isfile(candidate):
                        if ext != ".pdf":
                            _converted_img_tmp = _convert_image_to_a4_pdf(candidate)
                            original_pdf_path = _converted_img_tmp
                        else:
                            original_pdf_path = candidate
                        break

        # ──── Step 4: Merge → Original + Translated + Certification ────
        merged_doc = fitz.open()

        # Part A: Original pages
        if original_pdf_path and os.path.isfile(original_pdf_path):
            try:
                orig_doc = fitz.open(original_pdf_path)
                merged_doc.insert_pdf(orig_doc)
                orig_doc.close()
                logging.info("  📄 Merged original: %s (%d pages)", original_pdf_path, merged_doc.page_count)
            except Exception as e:
                logging.warning("Failed to merge original PDF: %s", e)

        # Part B: Translated pages
        if os.path.isfile(translated_pdf_path):
            try:
                trans_doc = fitz.open(translated_pdf_path)
                merged_doc.insert_pdf(trans_doc)
                trans_doc.close()
                logging.info("  📝 Merged translated: %d total pages", merged_doc.page_count)
            except Exception as e:
                logging.warning("Failed to merge translated PDF: %s", e)

        # Part C: Certification page
        if cert_pdf_path and os.path.isfile(cert_pdf_path):
            try:
                cert_doc = fitz.open(cert_pdf_path)
                merged_doc.insert_pdf(cert_doc)
                cert_doc.close()
                logging.info("  📜 Merged certification: %d total pages", merged_doc.page_count)
            except Exception as e:
                logging.warning("Failed to merge certification PDF: %s", e)

        if merged_doc.page_count == 0:
            merged_doc.close()
            return jsonify({"error": "empty_merge", "detail": "No pages to merge"}), 500

        merged_doc.save(merged_pdf_path, garbage=4, deflate=True)
        merged_doc.close()

        # ──── Step 4.5: Convert to Grayscale (black & white) ────
        grayscale_pdf_path = os.path.join(str(workspace_path), f"{base_name}_grayscale.pdf")
        _convert_pdf_to_grayscale(merged_pdf_path, grayscale_pdf_path)

        # ──── Step 5: Stamp the grayscale PDF ────
        # Save into Translate/ subfolder (maps to Google Drive Translate folder)
        translate_folder = os.path.join(str(workspace_path), "Translate")
        os.makedirs(translate_folder, exist_ok=True)
        stamped_pdf_path = os.path.join(translate_folder, final_pdf_name)
        stamp_pdf(grayscale_pdf_path, stamped_pdf_path)

        # Return the stamped PDF inline for preview
        return send_file(
            stamped_pdf_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name=final_pdf_name,
        )

    except Exception as exc:
        logging.exception("stamp_preview failed")
        return jsonify({"error": str(exc)}), 500

    finally:
        # Always cleanup ALL temp files, even on error
        for p in [html_tmp_path, translated_pdf_path, cert_html_tmp_path,
                   cert_pdf_path_tmp, merged_pdf_path, grayscale_pdf_path]:
            try: os.remove(p)
            except OSError: pass
        if _converted_img_tmp:
            try: os.remove(_converted_img_tmp)
            except OSError: pass


# =====================================================================
# Push Stamped PDF to Drive
# =====================================================================

@splitter_translate_bp.post("/api/translate/push_to_drive")
def push_stamped_to_drive():
    """Step 2: Push an already-stamped PDF to Drive + rename original.

    Expects JSON body:
    {
        "workspace": "...",
        "filename": "original_file.pdf",
        "drive_file_id": "abc123"   (optional)
    }

    The stamped PDF must already exist in the workspace from stamp_preview.
    """
    payload = request.get_json(force=True) or {}
    workspace_name = payload.get("workspace", "")
    filename = payload.get("filename", "")
    drive_file_id = payload.get("drive_file_id", "")

    if not workspace_name or not filename:
        return jsonify({"error": "missing_fields", "detail": "workspace and filename are required"}), 400

    workspace_root = SplitterPath(Config.TRANSLATION_WORKSPACE_DIR)
    workspace_path = workspace_root / workspace_name
    meta_path = workspace_path / "_files_meta.json"

    if not meta_path.is_file():
        return jsonify({"error": "workspace_not_found"}), 404

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    translate_folder_id = meta.get("translate_folder_id", "")

    base_name = os.path.splitext(filename)[0]
    translated_pdf_name = f"{base_name}_translated.pdf"
    # Check Translate/ subfolder first (new location), fallback to workspace root (legacy)
    stamped_pdf_path = os.path.join(str(workspace_path), "Translate", translated_pdf_name)
    if not os.path.isfile(stamped_pdf_path):
        stamped_pdf_path = os.path.join(str(workspace_path), translated_pdf_name)

    if not os.path.isfile(stamped_pdf_path):
        return jsonify({"error": "stamped_pdf_not_found", "detail": f"File {translated_pdf_name} not found. Run stamp_preview first."}), 404

    drive_upload_ok = False
    uploaded_drive_id = None
    rename_ok = False

    try:
        if translate_folder_id or drive_file_id:
            from routes.push_to_drive import _get_drive_ui
            ui = _get_drive_ui()

            # Upload stamped PDF to Translate/ folder
            if translate_folder_id:
                try:
                    uploaded_drive_id = ui.upload_file_to_folder(
                        translate_folder_id, stamped_pdf_path, translated_pdf_name
                    )
                    drive_upload_ok = True
                    logging.info("Uploaded stamped PDF to Drive: %s → folder %s", translated_pdf_name, translate_folder_id)
                except Exception as exc:
                    logging.exception("Drive upload failed")

            # Rename original file with [Đã dịch] prefix
            if drive_file_id:
                try:
                    new_name = f"[Đã dịch] - {filename}"
                    ui.rename_file(drive_file_id, new_name)
                    rename_ok = True
                    logging.info("Renamed original on Drive: %s → %s", filename, new_name)
                except Exception as exc:
                    logging.warning("Drive rename failed (non-fatal): %s", exc)

        return jsonify({
            "status": "success",
            "stamped_pdf": translated_pdf_name,
            "drive_uploaded": drive_upload_ok,
            "drive_file_id": uploaded_drive_id,
            "original_renamed": rename_ok,
        })

    except Exception as exc:
        logging.exception("push_to_drive failed")
        return jsonify({"error": str(exc)}), 500


# =====================================================================
# Mark Translation Complete (rename Drive folder to "Đang khai")
# =====================================================================

@splitter_translate_bp.post("/api/translate/mark_complete")
def mark_translation_complete():
    """Mark a workspace as fully translated → rename Drive folder to 'Đang khai'.

    Expects JSON body: { "workspace": "ÚC - CHÚ HIỆP CÔ CHÍNH - NHÂN" }

    Workflow:
    1. Read _files_meta.json to get root_folder_id and base_name.
    2. Rename Drive folder from '✅ ... - Đang dịch' to '✅ ... - Đang khai'.
    3. Clean up local workspace directory.
    """
    import shutil

    payload = request.get_json(force=True) or {}
    workspace_name = payload.get("workspace", "")

    if not workspace_name:
        return jsonify({"error": "missing_workspace"}), 400

    workspace_root = SplitterPath(Config.TRANSLATION_WORKSPACE_DIR)
    workspace_path = workspace_root / workspace_name

    meta_path = workspace_path / "_files_meta.json"
    if not meta_path.is_file():
        return jsonify({"error": "workspace_not_found"}), 404

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    root_folder_id = meta.get("root_folder_id", "")
    base_name = meta.get("base_name", workspace_name)

    if not root_folder_id:
        return jsonify({"error": "no_root_folder_id", "detail": "Cannot find Drive root folder ID in metadata"}), 400

    # 1. Rename on Drive
    try:
        from routes.push_to_drive import _get_drive_ui
        ui = _get_drive_ui()
        ui.mark_done_translating(root_folder_id, base_name)
    except Exception as exc:
        logging.exception("Failed to rename Drive folder to 'Đang khai'")
        return jsonify({"error": "drive_rename_failed", "detail": str(exc)}), 500

    # 2. Clean up local workspace
    try:
        shutil.rmtree(workspace_path)
        logging.info("Cleaned up workspace: %s", workspace_path)
    except Exception as exc:
        logging.warning("Failed to clean up workspace (non-fatal): %s", exc)

    return jsonify({
        "status": "done",
        "message": f"Đã chuyển '{base_name}' sang trạng thái Đang khai",
        "drive_folder_id": root_folder_id,
    })
