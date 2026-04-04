"""
Insurance PDF Editor Blueprint.
Extract text data from insurance PDFs, allow AI-assisted editing,
and produce corrected PDFs with exact font/position matching.
"""
from __future__ import annotations
import logging

import json
import os
import re
import copy
import random
import traceback
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, send_file
import requests as http_requests

import fitz  # PyMuPDF

insurance_bp = Blueprint("insurance_bp", __name__)

# ── Paths to the two insurance templates ──────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSURANCE_TEMPLATES = {
    "chubb": os.path.join(BASE_DIR, "templates", "insurance", "chubb.pdf"),
    "standard": os.path.join(BASE_DIR, "templates", "insurance", "standard.pdf"),
}
INSURANCE_OUTPUT_DIR = os.path.join(BASE_DIR, "insurance_outputs")
os.makedirs(INSURANCE_OUTPUT_DIR, exist_ok=True)


from services.insurance.liberty_api import fetch_liberty_premium
from services.insurance.chubb_api import fetch_chubb_premium
from services.insurance.random_utils import random_policy_no, random_customer_code, random_membership_no, calc_trip_days, random_chubb_policy
from services.insurance.prompts import build_grok_prompt
from services.insurance.pdf_engine import _extract_fields_from_pdf, _build_extraction_summary, _apply_changes_to_pdf

# API ROUTES
# ══════════════════════════════════════════════════════════════════

@insurance_bp.route("/api/insurance/templates", methods=["GET"])
def insurance_list_templates():
    """List available insurance templates."""
    templates = []
    for key, path in INSURANCE_TEMPLATES.items():
        exists = os.path.isfile(path)
        name = os.path.basename(path) if exists else f"(missing) {key}"
        templates.append({
            "key": key,
            "name": name,
            "exists": exists,
            "path": path,
        })
    return jsonify({"templates": templates})


@insurance_bp.route("/api/insurance/extract", methods=["POST"])
def insurance_extract():
    """
    Extract data from an insurance PDF template.
    Body: {
        "template": "chubb" | "standard",
        "period_from": "DD/MM/YYYY" (optional),
        "period_to": "DD/MM/YYYY" (optional),
        "destination": "Singapore" (optional),
        "adults": 1 (optional),
        "children": 0 (optional)
    }
    Returns: { summary, auto_fields, full_data, grok_prompt }
    """
    try:
        data = request.get_json() or {}
        template_key = data.get("template", "chubb")
        period_from = data.get("period_from", "")
        period_to = data.get("period_to", "")
        destination = data.get("destination", "Worldwide")
        policy_type = data.get("policy_type", "AMT") # "AMT" (Annual) or "SIT" (Single)
        cover_type = data.get("cover_type", "CT.IND")
        adults = int(data.get("adults", 1))
        children = int(data.get("children", 0))

        if template_key not in INSURANCE_TEMPLATES:
            return jsonify({"error": f"Unknown template: {template_key}"}), 400

        pdf_path = INSURANCE_TEMPLATES[template_key]
        if not os.path.isfile(pdf_path):
            return jsonify({"error": f"Template file not found: {pdf_path}"}), 404

        # Extract full data with positions
        full_data = _extract_fields_from_pdf(pdf_path)

        # Build summary from PDF
        summary = _build_extraction_summary(full_data)

        # ── Auto-generate fields ──────────────────────────────────
        if template_key == "standard":
            # Chubb specific fields
            auto_fields = {
                "policy_no": random_chubb_policy(),
                "plan": "GOLD",
                "category": "Individual" if cover_type == "CT.IND" else "Family",
                "region": "Worldwide" if destination == "Toàn Cầu" else "South East Asia",
                "issued_date": datetime.now().strftime("%d/%m/%Y"),
            }
        else:
            # Liberty specific fields
            auto_fields = {
                "policy_no": random_policy_no(),
                "customer_code": random_customer_code(),
                "membership_no": random_membership_no(),
                "plan": "Classic",           # Fixed
                "nationality": "Vietnamese", # Fixed
                "region": "Worldwide",       # Fixed
            }

        # Calculate trip days if dates provided
        if period_from and period_to:
            trip_days = calc_trip_days(period_from, period_to)
            if template_key == "standard":
                auto_fields["total_days"] = str(trip_days)
            else:
                auto_fields["period_from"] = period_from
                auto_fields["period_to"] = period_to
                auto_fields["length_of_trip"] = str(trip_days)

            # Convert DD/MM/YYYY to start/end dates for API
            try:
                dt_from = datetime.strptime(period_from, "%d/%m/%Y")
                dt_to = datetime.strptime(period_to, "%d/%m/%Y")
            except:
                dt_from = datetime.now()
                dt_to = datetime.now() + timedelta(days=trip_days)

            fetch_start = dt_from.strftime("%Y-%m-%d")
            fetch_end = dt_to.strftime("%Y-%m-%d")

            # Fetch real premium from API
            if template_key == "standard":
                premium = fetch_chubb_premium(
                    start_date=fetch_start,
                    end_date=fetch_end,
                    policy_type=policy_type,
                    cover_type=cover_type,
                    region=destination,
                    adults=adults,
                    children=children
                )
            else:
                premium = fetch_liberty_premium(trip_days, destination, adults, children)

            if premium:
                auto_fields["total_premium"] = premium
        else:
            trip_days = None

        # Build Grok prompt with ONLY the fields Grok needs to fill
        # (excludes auto-generated fields like policy_no, dates, premium, etc.)
        grok_prompt = build_grok_prompt(summary, template_key)

        return jsonify({
            "summary": summary,
            "auto_fields": auto_fields,
            "full_data": full_data,
            "grok_prompt": grok_prompt,
            "template": template_key,
        })

    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in insurance.py: %s", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@insurance_bp.route("/api/insurance/apply", methods=["POST"])
def insurance_apply():
    """
    Apply changes from Grok JSON + auto-generated fields to the PDF.
    Body: {
        "template": "chubb" | "standard",
        "original": { ... extracted summary ... },
        "updated": { ... new values from Grok ... },
        "auto_fields": { ... auto-generated values (policy_no, etc.) ... }
    }
    Returns: { download_url, results }
    """
    try:
        data = request.get_json() or {}
        template_key = data.get("template", "chubb")
        original = data.get("original", {})
        updated = data.get("updated", {})
        auto_fields = data.get("auto_fields", {})

        if template_key not in INSURANCE_TEMPLATES:
            return jsonify({"error": f"Unknown template: {template_key}"}), 400

        pdf_path = INSURANCE_TEMPLATES[template_key]
        if not os.path.isfile(pdf_path):
            return jsonify({"error": f"Template file not found"}), 404

        # Build changes map: {old_value: new_value}
        changes = {}

        # 1) Auto-fields: replace original PDF values with generated ones
        #    Map auto_field keys to original summary keys
        auto_field_map = {
            "policy_no": "policy_no",
            "customer_code": "customer_code",
            "membership_no": "membership_no",
            "period_from": "period_from",
            "period_to": "period_to",
            "total_premium": "total_premium",
            "plan": "plan",
            "category": "category",
            "region": "region",
            "issued_date": "issued_date",
            "total_days": "total_days",
        }
        for af_key, orig_key in auto_field_map.items():
            new_val = auto_fields.get(af_key, "")
            old_val = original.get(orig_key, "")
            if new_val and old_val and str(old_val) != str(new_val):
                changes[str(old_val)] = str(new_val)

        # Length of trip (find the old "23" or similar number)
        if auto_fields.get("length_of_trip"):
            old_trip = original.get("length_of_trip", "")
            if old_trip and old_trip != auto_fields["length_of_trip"]:
                changes[old_trip] = auto_fields["length_of_trip"]

        # 2) Grok-provided changes (name, DOB, passport, etc.)
        for key in original:
            if key in auto_field_map or key == "length_of_trip":
                continue  # already handled above
            old_val = str(original.get(key, ""))
            new_val = str(updated.get(key, old_val))
            if old_val and old_val != new_val:
                changes[old_val] = new_val

        if not changes:
            return jsonify({"error": "Không có thay đổi nào để áp dụng."}), 400

        # Generate output filename
        out_name = f"insurance_{template_key}_edited.pdf"
        output_path = os.path.join(INSURANCE_OUTPUT_DIR, out_name)

        # Apply changes
        results = _apply_changes_to_pdf(pdf_path, changes, output_path)

        return jsonify({
            "success": True,
            "download_url": f"/api/insurance/download/{out_name}",
            "results": results,
            "changes_applied": len([r for r in results if r["status"] == "replaced"]),
            "changes_failed": len([r for r in results if r["status"] == "not_found"]),
        })

    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in insurance.py: %s", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@insurance_bp.route("/api/insurance/download/<filename>", methods=["GET"])
def insurance_download(filename):
    """Download an edited insurance PDF."""
    filepath = os.path.join(INSURANCE_OUTPUT_DIR, filename)
    if not os.path.isfile(filepath):
        return jsonify({"error": "File not found"}), 404
    return send_file(filepath, as_attachment=False)
