"""
Fill IMM5645E (Family Information) PDF form by updating XFA XML data.

Strategy: Modify the XFA datasets XML to fill values, then write it back
into the cloned PDF. This preserves the original PDF format (XFA + locked)
so the result can be uploaded to the Canada immigration portal.

The XFA engine handles auto-sizing, text wrapping, and visual rendering.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from datetime import date
from io import BytesIO
from pathlib import Path

import pypdf
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DecodedStreamObject,
    NameObject,
    TextStringObject,
)

from canada_forms.field_mappings import ALL_FIELDS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# XFA data mapping
# ---------------------------------------------------------------------------

def _build_xfa_data(data: dict) -> dict:
    """
    Convert flat frontend form_fields into the XFA XML hierarchy.

    Returns a nested dict mirroring the XFA datasets structure:
    {
        "SectionA": {
            "Applicant": {"AppName": "...", "AppDOB": "...", ...},
            "Spouse": {...},
            "Mother": {...},
            "Father": {...},
        },
        "SectionB": { "children": [ {child0}, {child1}, ... ] },
        "SectionC": { "children": [ {sib0}, {sib1}, ... ] },
    }
    """
    # Auto-fill signature dates with current date
    today = date.today().isoformat()
    for dk in ("section_a_date", "section_b_date", "section_c_date"):
        if not data.get(dk):
            data[dk] = today

    # Auto-convert marital status for Applicant/Spouse
    _MARITAL_NORMALIZE = {
        "married": "Married-physically present",
        "common-law": "Common-law",
        "separated": "Legally separated",
        "annulled": "Annulled marriage",
    }
    for mk in ("app_marital_status", "spouse_marital_status"):
        raw = data.get(mk, "")
        if raw and raw.lower() in _MARITAL_NORMALIZE:
            data[mk] = _MARITAL_NORMALIZE[raw.lower()]

    xfa = {
        "Subform1": {
            "Visitor": data.get("visitor", "0"),
            "Worker": data.get("worker", "0"),
            "Student": data.get("student", "0"),
            "Other": data.get("other", "0"),
        },
        "SectionA": {
            "Applicant": {
                "AppName": data.get("app_name", ""),
                "AppDOB": data.get("app_dob", ""),
                "AppCOB": data.get("app_cob", ""),
                "AppAddress": data.get("app_address", ""),
                "AppOccupation": data.get("app_occupation", ""),
                "ChildMStatus": data.get("app_marital_status", ""),
            },
            "Spouse": {
                "SpouseName": data.get("spouse_name", ""),
                "SpouseDOB": data.get("spouse_dob", ""),
                "SpouseCOB": data.get("spouse_cob", ""),
                "SpouseAddress": data.get("spouse_address", ""),
                "SpouseOccupation": data.get("spouse_occupation", ""),
                "SpouseYes": "1" if data.get("spouse_accompanying_yes") else "0",
                "SpouseNo": "1" if data.get("spouse_accompanying_no") else "0",
                "ChildMStatus": data.get("spouse_marital_status", ""),
            },
            "Mother": {
                "MotherName": data.get("mother_name", ""),
                "MotherDOB": data.get("mother_dob", ""),
                "MotherCOB": data.get("mother_cob", ""),
                "MotherAddress": data.get("mother_address", ""),
                "MotherOccupation": data.get("mother_occupation", ""),
                "MotherYes": "1" if data.get("mother_accompanying_yes") else "0",
                "MotherNo": "1" if data.get("mother_accompanying_no") else "0",
                "ChildMStatus": data.get("mother_marital_status", ""),
            },
            "Father": {
                "FatherName": data.get("father_name", ""),
                "FatherDOB": data.get("father_dob", ""),
                "FatherCOB": data.get("father_cob", ""),
                "FatherAddress": data.get("father_address", ""),
                "FatherOccupation": data.get("father_occupation", ""),
                "FatherYes": "1" if data.get("father_accompanying_yes") else "0",
                "FatherNo": "1" if data.get("father_accompanying_no") else "0",
                "ChildMStatus": data.get("father_marital_status", ""),
            },
            "SectionAsignature": data.get("section_a_signature", ""),
            "SectionAdate": data.get("section_a_date", ""),
        },
        "SectionB": {
            "children": [],
            "SectionBsignature": data.get("section_b_signature", ""),
            "SectionBdate": data.get("section_b_date", ""),
        },
        "SectionC": {
            "children": [],
            "SectionCsignature": data.get("section_c_signature", ""),
            "SectionCdate": data.get("section_c_date", ""),
        },
    }

    # Build children (Section B: up to 4)
    for i in range(4):
        child = {
            "ChildName": data.get(f"child_{i}_name", ""),
            "ChildMStatus": data.get(f"child_{i}_marital_status", ""),
            "ChildRelationship": data.get(f"child_{i}_relationship", ""),
            "ChildDOB": data.get(f"child_{i}_dob", ""),
            "ChildCOB": data.get(f"child_{i}_cob", ""),
            "ChildAddress": data.get(f"child_{i}_address", ""),
            "ChildOccupation": data.get(f"child_{i}_occupation", ""),
            "ChildYes": "1" if data.get(f"child_{i}_accompanying_yes") else "0",
            "ChildNo": "1" if data.get(f"child_{i}_accompanying_no") else "0",
        }
        xfa["SectionB"]["children"].append(child)

    # Build siblings (Section C: up to 7)
    for i in range(7):
        sib = {
            "ChildName": data.get(f"sibling_{i}_name", ""),
            "ChildMStatus": data.get(f"sibling_{i}_marital_status", ""),
            "ChildRelationship": data.get(f"sibling_{i}_relationship", ""),
            "ChildDOB": data.get(f"sibling_{i}_dob", ""),
            "ChildCOB": data.get(f"sibling_{i}_cob", ""),
            "ChildAddress": data.get(f"sibling_{i}_address", ""),
            "ChildOccupation": data.get(f"sibling_{i}_occupation", ""),
            "ChildYes": "1" if data.get(f"sibling_{i}_accompanying_yes") else "0",
            "ChildNo": "1" if data.get(f"sibling_{i}_accompanying_no") else "0",
        }
        xfa["SectionC"]["children"].append(sib)

    return xfa


def _fill_xfa_element(parent_el, field_name: str, value: str):
    """Set text content of an XFA XML element, creating it if needed."""
    el = parent_el.find(field_name)
    if el is None:
        el = ET.SubElement(parent_el, field_name)
    el.text = value if value else None


def _fill_child_element(child_el, child_data: dict):
    """Fill a <Child> XFA element with data."""
    # Order matters to match original XML structure
    field_order = [
        "ChildName", "ChildMStatus", "ChildRelationship",
        "ChildDOB", "ChildCOB", "ChildAddress",
        "ChildOccupation", "ChildYes", "ChildNo",
    ]
    for field in field_order:
        _fill_xfa_element(child_el, field, child_data.get(field, ""))


def _update_xfa_datasets(xml_bytes: bytes, xfa_data: dict) -> bytes:
    """
    Parse XFA datasets XML, fill in values from xfa_data, return updated XML.
    """
    # Parse XML (handle namespace)
    ns = {"xfa": "http://www.xfa.org/schema/xfa-data/1.0/"}
    ET.register_namespace("xfa", "http://www.xfa.org/schema/xfa-data/1.0/")

    root = ET.fromstring(xml_bytes)
    data_el = root.find("xfa:data", ns)
    if data_el is None:
        raise RuntimeError("XFA datasets has no <xfa:data> element")

    imm = data_el.find("IMM_5645")
    if imm is None:
        raise RuntimeError("XFA data has no <IMM_5645> element")

    page1 = imm.find("page1")
    if page1 is None:
        raise RuntimeError("XFA data has no <page1> element")

    # --- Subform1 (application type checkboxes) ---
    subform1 = page1.find("Subform1")
    if subform1 is not None:
        for field, value in xfa_data["Subform1"].items():
            _fill_xfa_element(subform1, field, value)

    # --- Section A ---
    section_a = page1.find("SectionA")
    if section_a is not None:
        sa_data = xfa_data["SectionA"]

        # Applicant
        applicant_el = section_a.find("Applicant")
        if applicant_el is not None:
            for field, value in sa_data["Applicant"].items():
                _fill_xfa_element(applicant_el, field, value)

        # Spouse
        spouse_el = section_a.find("Spouse")
        if spouse_el is not None:
            for field, value in sa_data["Spouse"].items():
                _fill_xfa_element(spouse_el, field, value)

        # Mother
        mother_el = section_a.find("Mother")
        if mother_el is not None:
            for field, value in sa_data["Mother"].items():
                _fill_xfa_element(mother_el, field, value)

        # Father
        father_el = section_a.find("Father")
        if father_el is not None:
            for field, value in sa_data["Father"].items():
                _fill_xfa_element(father_el, field, value)

        # Signature & Date
        _fill_xfa_element(section_a, "SectionAsignature", sa_data.get("SectionAsignature", ""))
        _fill_xfa_element(section_a, "SectionAdate", sa_data.get("SectionAdate", ""))

    # --- Section B (Children) ---
    section_b = page1.find("SectionB")
    if section_b is not None:
        sb_data = xfa_data["SectionB"]
        child_elements = section_b.findall("Child")
        for i, child_el in enumerate(child_elements):
            if i < len(sb_data["children"]):
                _fill_child_element(child_el, sb_data["children"][i])

        _fill_xfa_element(section_b, "SectionBsignature", sb_data.get("SectionBsignature", ""))
        _fill_xfa_element(section_b, "SectionBdate", sb_data.get("SectionBdate", ""))

    # --- Section C (Siblings) ---
    section_c = page1.find("SectionC")
    if section_c is not None:
        sc_data = xfa_data["SectionC"]
        child_elements = section_c.findall("Child")
        for i, child_el in enumerate(child_elements):
            if i < len(sc_data["children"]):
                _fill_child_element(child_el, sc_data["children"][i])

        _fill_xfa_element(section_c, "SectionCsignature", sc_data.get("SectionCsignature", ""))
        _fill_xfa_element(section_c, "SectionCdate", sc_data.get("SectionCdate", ""))

    # Serialize back to bytes
    return ET.tostring(root, encoding="unicode", xml_declaration=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Main fill function
# ---------------------------------------------------------------------------

def fill_imm5645(
    data: dict,
    template_path: str | Path,
    output_path: str | Path,
) -> Path:
    """
    Fill IMM5645E PDF form by updating XFA datasets XML.

    Preserves the original PDF format (XFA + locked structure) so the
    result can be uploaded to the Canada immigration portal.
    """
    template_path = Path(template_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    reader = pypdf.PdfReader(str(template_path))
    if reader.is_encrypted:
        reader.decrypt("")

    # Clone entire document (preserves everything)
    writer = pypdf.PdfWriter(clone_from=reader)

    # -----------------------------------------------------------------------
    # Extract XFA datasets XML
    # -----------------------------------------------------------------------
    acroform_ref = writer._root_object.get("/AcroForm")
    if not acroform_ref:
        raise RuntimeError("PDF has no AcroForm")

    acroform = acroform_ref.get_object() if hasattr(acroform_ref, "get_object") else acroform_ref

    xfa_ref = acroform.get("/XFA")
    if not xfa_ref:
        raise RuntimeError("PDF has no XFA data — cannot use XFA fill method")

    # XFA is an array: [name, stream, name, stream, ...]
    xfa_array = xfa_ref.get_object() if hasattr(xfa_ref, "get_object") else xfa_ref

    # Find the "datasets" stream
    datasets_idx = None
    for i, item in enumerate(xfa_array):
        if isinstance(item, str) and item == "datasets":
            datasets_idx = i + 1
            break
        # Handle IndirectObject wrapping a string
        try:
            resolved = item.get_object() if hasattr(item, "get_object") else item
            if str(resolved) == "datasets":
                datasets_idx = i + 1
                break
        except Exception:
            pass

    if datasets_idx is None:
        raise RuntimeError("Could not find 'datasets' in XFA array")

    datasets_stream_ref = xfa_array[datasets_idx]
    datasets_stream = datasets_stream_ref.get_object() if hasattr(datasets_stream_ref, "get_object") else datasets_stream_ref

    # Get current XML
    original_xml = datasets_stream.get_data()

    # -----------------------------------------------------------------------
    # Build XFA data and update XML
    # -----------------------------------------------------------------------
    xfa_data = _build_xfa_data(data)
    updated_xml = _update_xfa_datasets(original_xml, xfa_data)

    # -----------------------------------------------------------------------
    # Write updated XML back into the datasets stream
    # -----------------------------------------------------------------------
    # Write updated XML back into the datasets stream (in-place)
    # -----------------------------------------------------------------------
    datasets_stream.set_data(updated_xml)

    # Count filled fields for logging
    filled_count = sum(1 for v in data.values() if v not in (None, "", "0", False))

    # -----------------------------------------------------------------------
    # STRIP DIGITAL SIGNATURES / CERTIFICATIONS
    # -----------------------------------------------------------------------
    # PyPDF breaks the DocMDP signature because it rewrites the XREF table.
    # An invalid signature causes Adobe Acrobat to enter high-security mode
    # and disable JavaScript, which might prevent validation.
    root = writer._root_object
    if "/Perms" in root:
        del root["/Perms"]
        
    if "/SigFlags" in acroform:
        del acroform["/SigFlags"]

    with open(output_path, "wb") as f:
        writer.write(f)

    logger.info(
        "IMM5645E XFA filled: %d fields → %s",
        filled_count, output_path,
    )
    return output_path


def get_field_list() -> list[dict]:
    """Return a list of all fillable field metadata for frontend display."""
    fields = []
    for semantic_key, pdf_key in ALL_FIELDS.items():
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
        elif semantic_key in ("visitor", "worker", "student", "other"):
            section = "Application Type"
            label = semantic_key.title()
        else:
            section = "Other"
            label = semantic_key.replace("_", " ").title()

        if semantic_key.endswith(("_yes", "_no")) or semantic_key in ("visitor", "worker", "student", "other"):
            ftype = "checkbox"
        elif semantic_key.endswith("_marital_status"):
            ftype = "dropdown"
        else:
            ftype = "text"

        fields.append({"key": semantic_key, "section": section, "label": label, "type": ftype})

    return fields
