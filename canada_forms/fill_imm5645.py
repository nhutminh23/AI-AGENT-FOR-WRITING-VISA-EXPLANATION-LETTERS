"""
Fill IMM5645E (Family Information) PDF form using pypdf.

Reads the encrypted template, maps extracted data to form fields,
and writes a filled PDF to the output path.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pypdf

from canada_forms.field_mappings import ALL_FIELDS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_checkbox(value: str | bool | None) -> str | None:
    """Convert a boolean-ish value to checkbox fill value."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    v = str(value).strip().lower()
    if v in ("yes", "true", "1", "có", "co"):
        return "1"
    if v in ("no", "false", "0", "không", "khong"):
        return "0"
    return None


def _clean_value(value: str | None) -> str:
    """Sanitize a text value before filling into the PDF."""
    if value is None:
        return ""
    return str(value).strip()


# ---------------------------------------------------------------------------
# Main fill function
# ---------------------------------------------------------------------------

def fill_imm5645(
    data: dict,
    template_path: str | Path,
    output_path: str | Path,
) -> Path:
    """
    Fill IMM5645E PDF form with extracted data.

    Uses direct annotation manipulation because XFA/AcroForm dual-layer PDFs
    don't work with pypdf's update_page_form_field_values.

    Parameters
    ----------
    data : dict
        Extracted family information. Keys should match semantic field names
        defined in ``field_mappings.py`` (e.g. ``app_name``, ``spouse_dob``).
        Missing keys are silently skipped (field left blank).
    template_path : str | Path
        Path to the blank IMM5645E PDF template.
    output_path : str | Path
        Where to write the filled PDF.

    Returns
    -------
    Path
        The output_path of the filled PDF.
    """
    from pypdf.generic import NameObject, TextStringObject

    template_path = Path(template_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(str(template_path))
    if reader.is_encrypted:
        reader.decrypt("")

    writer = pypdf.PdfWriter()
    writer.append_pages_from_reader(reader)

    # Build field→value dict from data using mappings
    # Key: the last part of the PDF field key (e.g. "AppName[0]")
    # because annotations use short /T tags
    fields_to_fill: dict[str, str] = {}
    filled_count = 0
    skipped_count = 0

    for semantic_key, pdf_field_key in ALL_FIELDS.items():
        value = data.get(semantic_key)
        if value is None or value == "":
            skipped_count += 1
            continue

        # Determine if this is a checkbox field (Yes/No buttons)
        if semantic_key.endswith(("_yes", "_no")):
            resolved = _resolve_checkbox(value)
            if resolved is not None:
                fields_to_fill[pdf_field_key] = resolved
                filled_count += 1
        else:
            cleaned = _clean_value(value)
            if cleaned:
                fields_to_fill[pdf_field_key] = cleaned
                filled_count += 1

    # Apply fields via direct annotation manipulation
    for page in writer.pages:
        if "/Annots" not in page:
            continue
        annots = page["/Annots"]
        for annot_ref in annots:
            try:
                annot = annot_ref.get_object()
                t_tag = str(annot.get("/T", ""))
                if not t_tag:
                    continue

                # Match against our field keys by suffix
                for pdf_key, value in fields_to_fill.items():
                    # PDF keys like "IMM_5645[0].page1[0]...AppName[0]"
                    # Annotation /T is just "AppName[0]"
                    last_part = pdf_key.split(".")[-1]
                    if t_tag == last_part:
                        annot.update({
                            NameObject("/V"): TextStringObject(value),
                        })
                        break
            except Exception as exc:
                logger.debug("Skipping annotation: %s", exc)

    # Write output
    with open(output_path, "wb") as f:
        writer.write(f)

    logger.info(
        "IMM5645E filled: %d fields set, %d skipped → %s",
        filled_count,
        skipped_count,
        output_path,
    )
    return output_path


def get_field_list() -> list[dict]:
    """
    Return a list of all fillable field metadata for frontend display.

    Each item: {key, section, label, type}
    """
    fields = []
    for semantic_key, pdf_key in ALL_FIELDS.items():
        # Determine section
        if semantic_key.startswith("app_"):
            section, label = "A - Applicant", semantic_key.replace("app_", "").replace("_", " ").title()
        elif semantic_key.startswith("spouse_"):
            section, label = "A - Spouse", semantic_key.replace("spouse_", "").replace("_", " ").title()
        elif semantic_key.startswith("mother_"):
            section, label = "A - Mother", semantic_key.replace("mother_", "").replace("_", " ").title()
        elif semantic_key.startswith("father_"):
            section, label = "A - Father", semantic_key.replace("father_", "").replace("_", " ").title()
        elif semantic_key.startswith("child_"):
            idx = semantic_key.split("_")[1]
            field_name = "_".join(semantic_key.split("_")[2:])
            section = f"B - Child {int(idx)+1}"
            label = field_name.replace("_", " ").title()
        elif semantic_key.startswith("sibling_"):
            idx = semantic_key.split("_")[1]
            field_name = "_".join(semantic_key.split("_")[2:])
            section = f"C - Sibling {int(idx)+1}"
            label = field_name.replace("_", " ").title()
        elif semantic_key.startswith("section_"):
            section = semantic_key.split("_")[1].upper()
            label = semantic_key.replace("_", " ").title()
            section = f"Signature {section}"
        elif semantic_key in ("visitor", "worker", "student", "other"):
            section = "Application Type"
            label = semantic_key.title()
        else:
            section = "Other"
            label = semantic_key.replace("_", " ").title()

        # Field type
        if semantic_key.endswith(("_yes", "_no")) or semantic_key in ("visitor", "worker", "student", "other"):
            ftype = "checkbox"
        elif semantic_key.endswith("_marital_status"):
            ftype = "dropdown"
        else:
            ftype = "text"

        fields.append({
            "key": semantic_key,
            "section": section,
            "label": label,
            "type": ftype,
        })

    return fields
