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
from flask_cors import cross_origin
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

    # Build filename from applicant name
    ap_family = (form_fields.get("ap_family_name") or "").strip()
    ap_given = (form_fields.get("ap_given_name") or "").strip()
    if ap_family or ap_given:
        name_part = f"{ap_family}_{ap_given}".replace(" ", "_").upper()
        # Remove any unsafe characters for filename
        name_part = secure_filename(name_part) or str(uuid.uuid4())[:8]
    else:
        name_part = str(uuid.uuid4())[:8]
    output_filename = f"Form54_filled_{name_part}.pdf"
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
        logging.exception("[Safe Log] Unhandled exception in australia_forms.py: %s", exc)
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


# ---------------------------------------------------------------------------
# IMMI AutoFill Hub — Active Profile (Hub & Inject Architecture)
# ---------------------------------------------------------------------------
AU_ACTIVE_DIR = AU_OUTPUT_DIR / "immi_profiles"


@australia_forms_bp.post("/australia/api/active-profile")
@cross_origin()
def australia_set_active_profile():
    """Save the active applicant JSON for the Chrome Extension to fetch.
    
    Accepts either:
    - A single applicant object → saves as the active profile
    - An array of applicants → saves each, sets first as active
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No JSON body provided"}), 400

    AU_ACTIVE_DIR.mkdir(parents=True, exist_ok=True)

    # Normalize: always work with a list
    applicants = data if isinstance(data, list) else [data]
    saved = []

    for i, applicant in enumerate(applicants):
        name = applicant.get("applicant_name", f"applicant_{i+1}").strip()
        safe_name = name.replace(" ", "_").lower()
        profile_path = AU_ACTIVE_DIR / f"{safe_name}.json"
        profile_path.write_text(json.dumps(applicant, ensure_ascii=False, indent=2), encoding="utf-8")
        saved.append({"name": name, "file": profile_path.name})
        logger.info("Saved IMMI profile: %s → %s", name, profile_path)

    # Set the active applicant (first one or the single one)
    active_path = AU_ACTIVE_DIR / "_active.json"
    active_applicant = applicants[0]
    active_path.write_text(json.dumps(active_applicant, ensure_ascii=False, indent=2), encoding="utf-8")

    return jsonify({
        "success": True,
        "active": active_applicant.get("applicant_name", "Unknown"),
        "total_saved": len(saved),
        "profiles": saved,
    })


@australia_forms_bp.get("/australia/api/active-profile")
@cross_origin()
def australia_get_active_profile():
    """Return the active applicant JSON (used by Chrome Extension)."""
    active_path = AU_ACTIVE_DIR / "_active.json"
    if not active_path.exists():
        return jsonify({"error": "No active profile set. Paste JSON in Tab Australia first."}), 404

    try:
        profile = json.loads(active_path.read_text(encoding="utf-8"))
        return jsonify(profile)
    except Exception as exc:
        logger.exception("Failed to read active profile: %s", exc)
        return jsonify({"error": str(exc)}), 500


@australia_forms_bp.post("/australia/api/set-active/<name>")
def australia_switch_active(name: str):
    """Switch the active applicant by name."""
    safe_name = secure_filename(name.replace(" ", "_").lower())
    profile_path = AU_ACTIVE_DIR / f"{safe_name}.json"
    if not profile_path.exists():
        return jsonify({"error": f"Profile '{name}' not found"}), 404

    active_path = AU_ACTIVE_DIR / "_active.json"
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    active_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"success": True, "active": data.get("applicant_name", name)})


@australia_forms_bp.get("/australia/api/profiles")
def australia_list_profiles():
    """List all saved applicant profiles."""
    if not AU_ACTIVE_DIR.exists():
        return jsonify({"profiles": []})

    profiles = []
    active_name = None
    active_path = AU_ACTIVE_DIR / "_active.json"
    if active_path.exists():
        try:
            active_data = json.loads(active_path.read_text(encoding="utf-8"))
            active_name = active_data.get("applicant_name")
        except Exception:
            pass

    for f in sorted(AU_ACTIVE_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            name = d.get("applicant_name", f.stem)
            profiles.append({
                "name": name,
                "file": f.name,
                "is_active": name == active_name,
            })
        except Exception:
            continue

    return jsonify({"profiles": profiles, "active": active_name})


@australia_forms_bp.delete("/australia/api/delete-profile/<name>")
@cross_origin()
def australia_delete_profile(name: str):
    """Delete a saved applicant profile by name."""
    safe_name = secure_filename(name.replace(" ", "_").lower())
    profile_path = AU_ACTIVE_DIR / f"{safe_name}.json"
    if not profile_path.exists():
        return jsonify({"error": f"Profile '{name}' not found"}), 404

    profile_path.unlink()
    logger.info("Deleted IMMI profile: %s → %s", name, profile_path)

    # If deleted profile was the active one, reset active
    active_path = AU_ACTIVE_DIR / "_active.json"
    if active_path.exists():
        try:
            active_data = json.loads(active_path.read_text(encoding="utf-8"))
            if active_data.get("applicant_name", "").strip() == name.strip():
                # Switch to next available profile, or clear
                remaining = [f for f in sorted(AU_ACTIVE_DIR.glob("*.json")) if not f.name.startswith("_")]
                if remaining:
                    new_active = json.loads(remaining[0].read_text(encoding="utf-8"))
                    active_path.write_text(json.dumps(new_active, ensure_ascii=False, indent=2), encoding="utf-8")
                    logger.info("Switched active profile to: %s", new_active.get("applicant_name"))
                else:
                    active_path.unlink()
                    logger.info("No profiles left, cleared active profile")
        except Exception as exc:
            logger.warning("Error resetting active profile: %s", exc)

    return jsonify({"success": True, "deleted": name})


# ---------------------------------------------------------------------------
# IMMI AutoFill Hub — Grok Prompt
# ---------------------------------------------------------------------------
@australia_forms_bp.get("/australia/api/grok-prompt-immi")
def australia_grok_prompt_immi():
    """Return the Grok prompt template for IMMI online form extraction."""
    prompt_path = AU_BASE_DIR / "grok_prompt_immi.md"
    if not prompt_path.exists():
        return jsonify({"error": "Prompt file not found"}), 404

    content = prompt_path.read_text(encoding="utf-8")

    # Extract just the PROMPT section
    marker = "## PROMPT (Copy từ đây)"
    idx = content.find(marker)
    if idx != -1:
        prompt_text = content[idx + len(marker):].strip()
    else:
        prompt_text = content

    return jsonify({"prompt": prompt_text})
