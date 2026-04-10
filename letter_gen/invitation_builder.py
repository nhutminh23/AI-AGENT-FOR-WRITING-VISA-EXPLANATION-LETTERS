"""
Build Invitation Letter for Australian Visa Application as DOCX.
Template follows EXACT structure from reference PDF.

Dynamic fields (filled from JSON profile):
  - Host info: name, DOB, nationality, passport, address, phone, occupation, income, visa status
  - Guest info: name, DOB, passport, relationship
  - Trip: start_date, end_date, purpose
  - Accompanying persons (if any)
  - Financial commitments

Signature section is LEFT BLANK for manual addition.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Any, Dict, List, Optional

from docx import Document
from docx.shared import Pt, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger(__name__)


def _sanitize(val: Any, fallback: str = "___________") -> str:
    """Return string value or fallback placeholder."""
    if val is None:
        return fallback
    s = str(val).strip()
    return s if s else fallback


def build_invitation_letter_docx(data: Dict[str, Any]) -> io.BytesIO:
    """
    Build the Invitation Letter DOCX from structured data.

    Expected `data` keys:
      host: {full_name, dob, nationality, passport_no, address, phone, occupation, annual_income, visa_status}
      guest: {full_name, dob, passport_no, relationship}
      trip: {start_date, end_date, purpose}
      accompanying: [{full_name, relationship, note}]  (optional)
      financial_commitments: [str]  (optional, defaults provided)
    """
    doc = Document()

    # Page setup: A4
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

    # Default style
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Times New Roman"
    font.size = Pt(12)
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.line_spacing = 1.15

    host = data.get("host", {})
    guest = data.get("guest", {})
    trip = data.get("trip", {})
    accompanying = data.get("accompanying", [])

    # ============================================================
    # TITLE
    # ============================================================
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("INVITATION LETTER FOR AUSTRALIAN VISA APPLICATION")
    run.bold = True
    run.font.size = Pt(14)
    title.paragraph_format.space_after = Pt(18)

    # ============================================================
    # TO:
    # ============================================================
    doc.add_paragraph("To: The Australian Consulate,")

    # ============================================================
    # HOST INFO
    # ============================================================
    host_info = doc.add_paragraph()
    host_info.add_run(f"My name is: {_sanitize(host.get('full_name'))}").bold = False
    host_info.add_run(f"\nDate of Birth: {_sanitize(host.get('dob'))}")
    host_info.add_run(f"\nNationality: {_sanitize(host.get('nationality'), 'Vietnamese')}")
    host_info.add_run(f"\nPassport Number: {_sanitize(host.get('passport_no'))}")

    # ============================================================
    # HOST LIVING/WORKING DETAILS
    # ============================================================
    visa_status = _sanitize(
        host.get("visa_status"),
        "living and working in Australia"
    )
    doc.add_paragraph(
        f"I am currently {visa_status} with the following details:"
    )

    # Bullet list for host details
    details = [
        f"Address: {_sanitize(host.get('address'))}",
        f"Phone number: {_sanitize(host.get('phone'))}",
        f"Occupation: {_sanitize(host.get('occupation'))}",
        f"Annual income: {_sanitize(host.get('annual_income'))}",
    ]
    for d in details:
        p = doc.add_paragraph(d, style="List Bullet")
        p.paragraph_format.space_after = Pt(2)

    # Visa status paragraph (optional extra line)
    visa_note = host.get("visa_note")
    if visa_note:
        doc.add_paragraph(visa_note)

    # ============================================================
    # GUEST INFO — "I am writing to invite..."
    # ============================================================
    relationship = _sanitize(guest.get("relationship"), "relative")
    guest_name = _sanitize(guest.get("full_name"))
    guest_dob = _sanitize(guest.get("dob"))
    guest_passport = _sanitize(guest.get("passport_no"))

    invite_para = doc.add_paragraph()
    invite_para.add_run(f"I am writing to invite my {relationship}: ")
    run_name = invite_para.add_run(guest_name)
    run_name.bold = False
    invite_para.add_run(f"\nDate of Birth: {guest_dob}")
    invite_para.add_run(f"\nPassport Number: {guest_passport}")

    # ============================================================
    # TRIP DETAILS
    # ============================================================
    start_date = _sanitize(trip.get("start_date"))
    end_date = _sanitize(trip.get("end_date"))
    purpose = _sanitize(
        trip.get("purpose"),
        "the purpose of family visit and tourism"
    )

    doc.add_paragraph(
        f"to visit me in Australia for a short stay from {start_date} to {end_date} for {purpose}."
    )

    # ============================================================
    # ACCOMPANYING PERSONS (optional)
    # ============================================================
    if accompanying:
        parts = []
        for person in accompanying:
            name = _sanitize(person.get("full_name"))
            rel = _sanitize(person.get("relationship"), "")
            note = person.get("note", "")
            part = f"{name}"
            if rel:
                part = f"{rel}: {name}"
            if note:
                part += f" ({note})"
            parts.append(part)

        if len(parts) == 1:
            acc_text = parts[0]
        else:
            acc_text = ", ".join(parts[:-1]) + f" and {parts[-1]}"

        doc.add_paragraph(
            f"During this trip, my {relationship} will be accompanied by {acc_text}."
        )

    # ============================================================
    # FINANCIAL COMMITMENTS — "I hereby confirm that:"
    # ============================================================
    doc.add_paragraph("I hereby confirm that:")

    default_commitments = [
        f"I will cover all travel expenses for my {relationship}, including airfare, accommodation, living expenses, and any other related costs.",
        f"I will provide accommodation for {'him' if _guess_gender(guest) == 'M' else 'her'} at my residence throughout {'his' if _guess_gender(guest) == 'M' else 'her'} stay in Australia.",
        f"I will take full financial responsibility and provide support for {'him' if _guess_gender(guest) == 'M' else 'her'} during the entire visit.",
        f"I will ensure that {'he' if _guess_gender(guest) == 'M' else 'she'} complies with all Australian laws and visa conditions and leaves Australia before {'his' if _guess_gender(guest) == 'M' else 'her'} visa expires.",
    ]

    commitments = data.get("financial_commitments") or default_commitments
    for c in commitments:
        p = doc.add_paragraph(c, style="List Bullet")
        p.paragraph_format.space_after = Pt(2)

    # ============================================================
    # CLOSING STATEMENTS
    # ============================================================
    doc.add_paragraph(
        "This visit is purely for family reunion and short-term tourism purposes, "
        "with no intention to overstay or engage in any unlawful employment."
    )

    doc.add_paragraph(
        f"I kindly request the Consulate to consider and grant a visa for my {relationship}."
    )

    doc.add_paragraph("Thank you for your time and consideration.")

    # ============================================================
    # SIGNATURE BLOCK (left blank for manual addition)
    # ============================================================
    closing = doc.add_paragraph()
    closing.paragraph_format.space_before = Pt(18)
    closing.add_run("Yours sincerely,")

    # Blank space for signature
    sig_space = doc.add_paragraph()
    sig_space.paragraph_format.space_before = Pt(36)
    sig_space.paragraph_format.space_after = Pt(0)

    # Host name under signature
    name_para = doc.add_paragraph()
    run = name_para.add_run(_sanitize(host.get("full_name")).upper())
    run.bold = True
    run.font.size = Pt(13)

    # Save to BytesIO
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream


def _guess_gender(guest: Dict[str, Any]) -> str:
    """Guess gender from sex field or name patterns. Returns 'M' or 'F'."""
    sex = (guest.get("sex") or guest.get("gender") or "").strip().upper()
    if sex in ("M", "MALE", "NAM"):
        return "M"
    if sex in ("F", "FEMALE", "NỮ", "NU"):
        return "F"
    # Guess from Vietnamese name patterns
    name = (guest.get("full_name") or "").upper()
    female_indicators = ["THI ", "NGOC ", "MY ", "LINH", "HUONG", "PHUONG", "HANH", "TRANG"]
    for ind in female_indicators:
        if ind in name:
            return "F"
    return "M"  # default
