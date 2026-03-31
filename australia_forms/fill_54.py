"""
Fill Australia Form 54 (Family Composition) PDF using AcroForm fields.

Strategy: Use pypdf to update standard AcroForm fields directly.
No XFA manipulation needed — much simpler than Canada forms.

Field naming convention in the PDF:
  ap.*     = Applicant
  as.*     = Accompanying spouse/de facto partner
  fm.*     = Family members (parents, siblings)
  m.*      = Applicant's children (members)
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

import pypdf

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------
# Form 54 Relationship status codes (bottom legend of the form)
_MARITAL_CODE_MAP = {
    # Full word → single letter code
    "married":       "M",
    "engaged":       "E",
    "de facto":      "F",
    "defacto":       "F",
    "separated":     "S",
    "divorced":      "D",
    "widowed":       "W",
    "never married": "N",
    "single":        "N",
    "minor":         "N",
    # Already codes → pass through
    "m": "M", "e": "E", "f": "F",
    "s": "S", "d": "D", "w": "W", "n": "N",
}

def _normalize_marital(value: str) -> str:
    """Convert full marital status word to Form 54 single-letter code."""
    if not value:
        return ""
    code = _MARITAL_CODE_MAP.get(value.strip().lower(), "")
    return code or value.strip()  # fallback: return as-is if unknown

def _normalize_date(value: str) -> str:
    """
    Normalize date to DD-Mon-YYYY format (e.g. '10-Jun-1961').
    This is exactly 11 characters, matching the PDF's MaxLen=11.
    The template has /MK /BG white background to cover static '/' separators.
    """
    if not value:
        return ""

    import re
    from datetime import datetime

    value = value.strip()

    def _to_output(dt: datetime) -> str:
        # Output: DD-Mon-YYYY (exactly 11 chars, fits MaxLen=11)
        return f"{dt.day:02d}-{dt.strftime('%b').capitalize()}-{dt.year}"

    # 1. Match Day, Month-word, Year: "10-Jun-1961/" or "10 Jun 1961"
    m_word = re.search(r"(\d{1,2})[^A-Za-z0-9]*([A-Za-z]{3,})[^A-Za-z0-9]*(\d{4})", value)
    if m_word:
        day, month_str, year = m_word.groups()
        try:
            dt = datetime.strptime(f"{day} {month_str[:3].capitalize()} {year}", "%d %b %Y")
            return _to_output(dt)
        except Exception:
            pass

    # 2. YYYY-MM-DD (ISO format)
    m_iso = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", value)
    if m_iso:
        year, month, day = m_iso.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            return _to_output(dt)
        except Exception:
            pass

    # 3. DD/MM/YYYY or DD-MM-YYYY
    m_eu = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", value)
    if m_eu:
        day, month, year = m_eu.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            return _to_output(dt)
        except Exception:
            pass

    logger.warning("Could not normalize date: %s", value)
    return value


# ---------------------------------------------------------------------------
# Field mapping: semantic JSON key → PDF AcroForm field name
# ---------------------------------------------------------------------------
# Applicant (ap.*)
# NOTE: ap.prev = "Previous visits to Australia" (date field, NOT country)
#       We do NOT fill it automatically — user fills it manually if needed.
#       ap.dec 1 / ap.dec 2 = Signature dates, auto-filled with today's date.
APPLICANT_FIELDS = {
    "ap_family_name": "ap.name fam",
    "ap_given_name":  "ap.name giv",
    "ap_dob":         "ap.dob",
    "ap_marital":     "ap.mar",
    "ap_home_addr1":  "ap.home ad 1",
    "ap_home_addr2":  "ap.home ad 2",
    # ap.dec 1 / ap.dec 2 filled automatically (today's date) in fill_form54()
}

# Accompanying Spouse (as.*)
# NOTE: as.prev / as.defacto prev = "Previous visits to Australia" date — not filled automatically
SPOUSE_FIELDS = {
    "as_family_name":     "as.name fam",
    "as_given_name":      "as.name giv",
    "as_dob":             "as.dob",
    "as_marital":         "as.mar",
    "as_home_addr1":      "as.home ad 1",
    "as_home_addr2":      "as.home ad 2",
    # De facto partner
    "as_defacto_family":  "as.name defacto",
    "as_defacto_given":   "as.given def",
    "as_defacto_dob":     "as.dob def",
    "as_defacto_marital": "as.mar def",
    "as_defacto_addr1":   "as.defacto home ad 1",
    "as_defacto_addr2":   "as.defacto home ad 2",
}

# Parents (fm.par*)
# NOTE: fm.par prev 1/2 = "Previous visits to Australia" — NOT filled automatically
PARENT_FIELDS = [
    # Parent 1
    {
        "family_name": "fm.par name fam 1",
        "given_name":  "fm.par name giv 1",
        "dob":         "fm.par dob 1",
        "marital":     "fm.par mar 1",
        "home_addr1":  "fm.par1 home ad 1",
        "home_addr2":  "fm.par1 home ad 2",
    },
    # Parent 2
    {
        "family_name": "fm.par name fam 2",
        "given_name":  "fm.par name giv 2",
        "dob":         "fm.par dob 2",
        "marital":     "fm.par mar 2",
        "home_addr1":  "fm.par2 home ad 1",
        "home_addr2":  "fm.par2 home ad 2",
    },
]

# Siblings (fm.sib*)
# NOTE: fm.sib prev 1/2/3 = "Previous visits to Australia" — NOT filled automatically
SIBLING_FIELDS = [
    {
        "family_name": "fm.sib name fam 1",
        "given_name":  "fm.sib name giv 1",
        "dob":         "fm.sib dob 1",
        "marital":     "fm.sib mar 1",
        "home_addr1":  "fm.sib1 home ad 1",
        "home_addr2":  "fm.sib1 home ad 2",
    },
    {
        "family_name": "fm.sib name fam 2",
        "given_name":  "fm.sib name giv 2",
        "dob":         "fm.sib dob 2",
        "marital":     "fm.sib mar 2",
        "home_addr1":  "fm.sib2 home ad 1",
        "home_addr2":  "fm.sib2 home ad 2",
    },
    {
        "family_name": "fm.sib name fam 3",
        "given_name":  "fm.sib name giv 3",
        "dob":         "fm.sib dob 3",
        "marital":     "fm.sib mar 3",
        "home_addr1":  "fm.sib3 home ad 1",
        "home_addr2":  "fm.sib3 home ad 2",
    },
]

# Children / members (m.*)
# NOTE: m.prev 1/2/3 = "Previous visits to Australia" — NOT filled automatically
CHILD_FIELDS = [
    {
        "family_name": "m.name fam 1",
        "given_name":  "m.name giv 1",
        "dob":         "m.dob 1",
        "marital":     "m.mar 1",
        "home_addr1":  "m.home 1 ad 1",
        "home_addr2":  "m.home 2 ad 1",
    },
    {
        "family_name": "m.name fam 2",
        "given_name":  "m.name giv 2",
        "dob":         "m.dob 2",
        "marital":     "m.mar 2",
        "home_addr1":  "m.home 1 ad 2",
        "home_addr2":  "m.home 2 ad 2",
    },
    {
        "family_name": "m.name fam 3",
        "given_name":  "m.name giv 3",
        "dob":         "m.dob 3",
        "marital":     "m.mar 3",
        "home_addr1":  "m.home 1 ad 3",
        "home_addr2":  "m.home 2 ad 3",
    },
]

# All semantic keys (flat), for frontend field list
ALL_FIELDS = {
    **APPLICANT_FIELDS,
    **SPOUSE_FIELDS,
}
for i, pf in enumerate(PARENT_FIELDS):
    for k, v in pf.items():
        ALL_FIELDS[f"parent_{i}_{k}"] = v
for i, sf in enumerate(SIBLING_FIELDS):
    for k, v in sf.items():
        ALL_FIELDS[f"sibling_{i}_{k}"] = v
for i, cf in enumerate(CHILD_FIELDS):
    for k, v in cf.items():
        ALL_FIELDS[f"child_{i}_{k}"] = v


def fill_form54(
    data: dict,
    template_path: str | Path,
    output_path: str | Path,
) -> Path:
    """
    Fill Australia Form 54 using standard AcroForm fields.
    `data` is a flat dict of semantic keys → values.

    Automatic:
    - Visitor visa (600) checkbox is always ticked.
    - Signature date fields (ap.dec 1 / ap.dec 2) are set to today's date.
    - prev_country fields removed — ap.prev etc. = "Previous visits to Australia"
      which is a date the user fills in manually if they've been to AU before.
    """
    from datetime import date as _date
    template_path = Path(template_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(str(template_path))
    writer = pypdf.PdfWriter(clone_from=reader)

    # Build PDF field name → value mapping (with normalization)
    field_updates = {}       # non-date fields → filled by pypdf
    date_field_values = {}   # date fields → painted by fitz (never sent to pypdf)

    for semantic_key, pdf_field in ALL_FIELDS.items():
        value = data.get(semantic_key, "") or ""
        if not value:
            continue

        # Normalize marital status → single letter code (M, N, E, F, S, D, W)
        if "marital" in semantic_key or semantic_key.endswith("_mar"):
            value = _normalize_marital(value)

        # Date fields → normalize and store separately (NOT in field_updates)
        elif "dob" in semantic_key:
            value = _normalize_date(value)
            if value:
                date_field_values[pdf_field] = value
            continue  # skip adding to field_updates

        if value:
            field_updates[pdf_field] = value

    # Auto: today's date for signature/declaration fields (DD-Mon-YYYY)
    # These are also date fields → paint with fitz, not pypdf
    from datetime import date as _today_date
    _today = _today_date.today()
    today_str = f"{_today.day:02d}-{_today.strftime('%b')}-{_today.year}"
    date_field_values["ap.dec 1"] = today_str
    date_field_values["ap.dec 2"] = today_str


    # Fill each page's form fields (text + select fields, NO date fields)
    filled_count = 0
    for page_num in range(len(writer.pages)):
        try:
            writer.update_page_form_field_values(
                writer.pages[page_num],
                field_updates,
                auto_regenerate=True,  # Let pypdf build the appearance stream
            )
            filled_count += 1
        except Exception as exc:
            logger.warning("Page %d fill warning: %s", page_num, exc)

    # Auto: tick the "Visitor visa (600)" checkbox
    _tick_visitor_visa_checkbox(writer)


    # Write to a temporary buffer first, then post-process with fitz
    import io
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)

    # Post-process: physically paint date fields on the PAGE CONTENT layer.
    # Date fields have static '/' characters baked into the template background.
    # By painting white rect + text directly on the page content, we cover the
    # slashes and avoid the double-rendering issue (pypdf annotation + page content).
    _paint_date_fields(buf, output_path, date_field_values)

    total_filled = sum(1 for v in data.values() if v not in (None, "", "0", False))
    logger.info(
        "Form 54 filled: %d values → %s (pages: %d)",
        total_filled, output_path, filled_count,
    )
    return output_path


# ---------------------------------------------------------------------------
# Date field painter: covers '/' slashes with white rect + redrawn text
# ---------------------------------------------------------------------------
_DATE_FIELD_KEYWORDS = ("dob", "dec 1", "dec 2", "prev")

def _paint_date_fields(pdf_buf, output_path: str, date_values: dict) -> None:
    """
    Open the filled PDF with PyMuPDF and physically paint date values
    directly on the page content layer.

    Why not use pypdf to fill date fields?
    The PDF template has static '/' characters baked into the page background
    inside date field areas. Form field text renders as an ANNOTATION layer
    on top of page content, but the annotation background is transparent,
    so the '/' characters bleed through.

    By painting white rect + text directly on the PAGE CONTENT layer,
    we physically cover the '/' characters. Since pypdf never fills
    the date fields, there's only ONE layer of text = no ghosting/doubling.

    Args:
        pdf_buf: BytesIO buffer containing the pypdf-filled PDF
        output_path: Path to save the final PDF
        date_values: Dict of {pdf_field_name: date_string} to paint
    """
    import fitz

    doc = fitz.open(stream=pdf_buf, filetype="pdf")

    for page in doc:
        # Find date widgets and match against our date_values dict
        for widget in page.widgets():
            field_name = widget.field_name or ""
            value = date_values.get(field_name, "")
            if not value:
                continue

            r = widget.rect
            # Shrink 0.3pt inward to preserve table borders
            inner = fitz.Rect(r.x0 + 0.3, r.y0 + 0.3, r.x1 - 0.3, r.y1 - 0.3)

            # Paint white background (covers static '/' slashes)
            shape = page.new_shape()
            shape.draw_rect(inner)
            shape.finish(color=None, fill=(1, 1, 1))
            shape.commit()

            # Draw the date text on top
            fontsize = min(7.5, inner.height * 0.65)
            text_y = inner.y0 + inner.height * 0.72
            page.insert_text(
                fitz.Point(inner.x0 + 1.5, text_y),
                value,
                fontsize=fontsize,
                fontname="helv",
                color=(0, 0, 0),
            )

    doc.save(str(output_path))
    doc.close()


def _tick_visitor_visa_checkbox(writer: pypdf.PdfWriter) -> None:
    """
    Tick the 'Visitor visa (600)' checkbox.

    The checkbox field is named 'visa type' (child of parent 'ap').
    It lives in the AcroForm /Fields /Kids tree, NOT in page /Annots directly.
    We must walk recursively through /Kids to find it.
    """
    from pypdf.generic import NameObject

    def _walk_and_tick(fields_list: list) -> bool:
        for ref in fields_list:
            try:
                field = ref.get_object() if hasattr(ref, "get_object") else ref
                t = str(field.get("/T", "")).lower().strip()
                ft = str(field.get("/FT", ""))

                # Match: field name is 'visa type' AND it's a /Btn
                if t == "visa type" and ft == "/Btn":
                    # The checkbox on-state key is '/visitor (600)' (from /AP /N)
                    on_state = NameObject("/visitor (600)")
                    field.update({
                        NameObject("/V"):  on_state,
                    })
                    # Also set /AS on the first Kid (the actual widget)
                    kids = field.get("/Kids", [])
                    if kids:
                        kid0 = kids[0].get_object() if hasattr(kids[0], "get_object") else kids[0]
                        kid0[NameObject("/AS")] = on_state
                        # Page 2 kid (index 2) also needs ticking
                        if len(kids) > 2:
                            kid2 = kids[2].get_object() if hasattr(kids[2], "get_object") else kids[2]
                            kid2[NameObject("/AS")] = on_state
                    logger.info("Ticked 'Visitor visa (600)' checkbox [T=visa type, state=%s]", on_state)
                    return True

                # Recurse into /Kids
                kids = field.get("/Kids", [])
                if kids and _walk_and_tick(list(kids)):
                    return True

            except Exception as e:
                logger.debug("Field walk error: %s", e)
        return False

    try:
        acroform = writer._root_object.get("/AcroForm", {})
        if hasattr(acroform, "get_object"):
            acroform = acroform.get_object()
        fields = list(acroform.get("/Fields", []))
        if not _walk_and_tick(fields):
            logger.warning("'Visitor visa (600)' checkbox not found in AcroForm field tree")
    except Exception as e:
        logger.warning("Could not tick visitor visa checkbox: %s", e)




def get_field_list() -> list[dict]:
    """Return metadata for all fillable fields (for frontend display)."""
    fields = []
    for semantic_key, pdf_field in ALL_FIELDS.items():
        # Determine section
        if semantic_key.startswith("ap_"):
            section = "Applicant"
            label = semantic_key.replace("ap_", "").replace("_", " ").title()
        elif semantic_key.startswith("as_defacto"):
            section = "De Facto Partner"
            label = semantic_key.replace("as_defacto_", "").replace("_", " ").title()
        elif semantic_key.startswith("as_"):
            section = "Spouse"
            label = semantic_key.replace("as_", "").replace("_", " ").title()
        elif semantic_key.startswith("parent_"):
            parts = semantic_key.split("_")
            idx = int(parts[1])
            field_name = "_".join(parts[2:])
            section = f"Parent {idx + 1}"
            label = field_name.replace("_", " ").title()
        elif semantic_key.startswith("sibling_"):
            parts = semantic_key.split("_")
            idx = int(parts[1])
            field_name = "_".join(parts[2:])
            section = f"Sibling {idx + 1}"
            label = field_name.replace("_", " ").title()
        elif semantic_key.startswith("child_"):
            parts = semantic_key.split("_")
            idx = int(parts[1])
            field_name = "_".join(parts[2:])
            section = f"Child {idx + 1}"
            label = field_name.replace("_", " ").title()
        else:
            section = "Other"
            label = semantic_key.replace("_", " ").title()

        fields.append({
            "key": semantic_key,
            "pdf_field": pdf_field,
            "section": section,
            "label": label,
            "type": "text",
        })

    return fields
