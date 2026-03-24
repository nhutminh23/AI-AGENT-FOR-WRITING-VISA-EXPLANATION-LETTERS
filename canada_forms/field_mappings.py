"""
IMM5645E (Family Information) — PDF form field mappings.

Maps semantic field names to actual PDF AcroForm field keys.
Field types: /Tx = text, /Btn = checkbox/radio, /Ch = dropdown.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Prefix shorthand
# ---------------------------------------------------------------------------
_P = "IMM_5645[0].page1[0]"
_SA = f"{_P}.SectionA[0]"
_SB = f"{_P}.SectionB[0]"
_SC = f"{_P}.SectionC[0]"

# ---------------------------------------------------------------------------
# Top-level: Application type checkboxes
# ---------------------------------------------------------------------------
APPLICATION_TYPE_FIELDS: dict[str, str] = {
    "visitor":  f"{_P}.Subform1[0].Visitor[0]",
    "worker":   f"{_P}.Subform1[0].Worker[0]",
    "student":  f"{_P}.Subform1[0].Student[0]",
    "other":    f"{_P}.Subform1[0].Other[0]",
}

# ---------------------------------------------------------------------------
# Section A: Applicant + Spouse + Mother + Father
# ---------------------------------------------------------------------------
def _person_fields(prefix: str, short: str) -> dict[str, str]:
    """Generate field mapping for a person block (Name, DOB, COB, etc.)."""
    return {
        f"{short}_name":            f"{prefix}.{short.title()}Name[0]",
        f"{short}_dob":             f"{prefix}.{short.title()}DOB[0]",
        f"{short}_cob":             f"{prefix}.{short.title()}COB[0]",
        f"{short}_address":         f"{prefix}.{short.title()}Address[0]",
        f"{short}_occupation":      f"{prefix}.{short.title()}Occupation[0]",
        f"{short}_marital_status":  f"{prefix}.ChildMStatus[0]",
    }


# Applicant uses "App" prefix in the PDF
APPLICANT_FIELDS: dict[str, str] = {
    "app_name":            f"{_SA}.Applicant[0].AppName[0]",
    "app_dob":             f"{_SA}.Applicant[0].AppDOB[0]",
    "app_cob":             f"{_SA}.Applicant[0].AppCOB[0]",
    "app_address":         f"{_SA}.Applicant[0].AppAddress[0]",
    "app_occupation":      f"{_SA}.Applicant[0].AppOccupation[0]",
    "app_marital_status":  f"{_SA}.Applicant[0].ChildMStatus[0]",
}

SPOUSE_FIELDS: dict[str, str] = {
    "spouse_name":            f"{_SA}.Spouse[0].SpouseName[0]",
    "spouse_dob":             f"{_SA}.Spouse[0].SpouseDOB[0]",
    "spouse_cob":             f"{_SA}.Spouse[0].SpouseCOB[0]",
    "spouse_address":         f"{_SA}.Spouse[0].SpouseAddress[0]",
    "spouse_occupation":      f"{_SA}.Spouse[0].SpouseOccupation[0]",
    "spouse_accompanying_yes": f"{_SA}.Spouse[0].SpouseYes[0]",
    "spouse_accompanying_no":  f"{_SA}.Spouse[0].SpouseNo[0]",
    "spouse_marital_status":   f"{_SA}.Spouse[0].ChildMStatus[0]",
}

MOTHER_FIELDS: dict[str, str] = {
    "mother_name":            f"{_SA}.Mother[0].MotherName[0]",
    "mother_dob":             f"{_SA}.Mother[0].MotherDOB[0]",
    "mother_cob":             f"{_SA}.Mother[0].MotherCOB[0]",
    "mother_address":         f"{_SA}.Mother[0].MotherAddress[0]",
    "mother_occupation":      f"{_SA}.Mother[0].MotherOccupation[0]",
    "mother_accompanying_yes": f"{_SA}.Mother[0].MotherYes[0]",
    "mother_accompanying_no":  f"{_SA}.Mother[0].MotherNo[0]",
    "mother_marital_status":   f"{_SA}.Mother[0].ChildMStatus[0]",
}

FATHER_FIELDS: dict[str, str] = {
    "father_name":            f"{_SA}.Father[0].FatherName[0]",
    "father_dob":             f"{_SA}.Father[0].FatherDOB[0]",
    "father_cob":             f"{_SA}.Father[0].FatherCOB[0]",
    "father_address":         f"{_SA}.Father[0].FatherAddress[0]",
    "father_occupation":      f"{_SA}.Father[0].FatherOccupation[0]",
    "father_accompanying_yes": f"{_SA}.Father[0].FatherYes[0]",
    "father_accompanying_no":  f"{_SA}.Father[0].FatherNo[0]",
    "father_marital_status":   f"{_SA}.Father[0].ChildMStatus[0]",
}

SECTION_A_SIGNATURE: dict[str, str] = {
    "section_a_signature": f"{_SA}.#subform[5].SectionAsignature[0]",
    "section_a_date":      f"{_SA}.#subform[5].SectionAdate[0]",
}

# ---------------------------------------------------------------------------
# Section B: Children (up to 4 slots: Child[0] .. Child[3])
# ---------------------------------------------------------------------------
def _child_fields(section: str, index: int) -> dict[str, str]:
    """Generate field mapping for a child slot."""
    prefix = f"{section}.Child[{index}]"
    return {
        f"child_{index}_name":            f"{prefix}.ChildName[0]",
        f"child_{index}_relationship":    f"{prefix}.ChildRelationship[0]",
        f"child_{index}_dob":             f"{prefix}.ChildDOB[0]",
        f"child_{index}_cob":             f"{prefix}.ChildCOB[0]",
        f"child_{index}_address":         f"{prefix}.ChildAddress[0]",
        f"child_{index}_occupation":      f"{prefix}.ChildOccupation[0]",
        f"child_{index}_marital_status":  f"{prefix}.ChildMStatus[0]",
        f"child_{index}_accompanying_yes": f"{prefix}.ChildYes[0]",
        f"child_{index}_accompanying_no":  f"{prefix}.ChildNo[0]",
    }


SECTION_B_CHILDREN: dict[str, str] = {}
for _i in range(4):
    SECTION_B_CHILDREN.update(_child_fields(_SB, _i))

SECTION_B_SIGNATURE: dict[str, str] = {
    "section_b_signature": f"{_SB}.#subform[5].#subform[6].SectionBsignature[0]",
    "section_b_date":      f"{_SB}.#subform[5].#subform[6].SectionBdate[0]",
}

# ---------------------------------------------------------------------------
# Section C: Brothers & Sisters (up to 7 slots: Child[0] .. Child[6])
# ---------------------------------------------------------------------------
SECTION_C_SIBLINGS: dict[str, str] = {}
for _i in range(7):
    # Reuse _child_fields but prefix keys with "sibling_" for clarity
    _raw = _child_fields(_SC, _i)
    for _k, _v in _raw.items():
        _new_key = _k.replace("child_", "sibling_")
        SECTION_C_SIBLINGS[_new_key] = _v

SECTION_C_SIGNATURE: dict[str, str] = {
    "section_c_signature": f"{_SC}.#subform[8].SectionCsignature[0]",
    "section_c_date":      f"{_SC}.#subform[8].SectionCdate[0]",
}

# ---------------------------------------------------------------------------
# Combined: All fillable fields in one dict
# ---------------------------------------------------------------------------
ALL_FIELDS: dict[str, str] = {}
ALL_FIELDS.update(APPLICATION_TYPE_FIELDS)
ALL_FIELDS.update(APPLICANT_FIELDS)
ALL_FIELDS.update(SPOUSE_FIELDS)
ALL_FIELDS.update(MOTHER_FIELDS)
ALL_FIELDS.update(FATHER_FIELDS)
ALL_FIELDS.update(SECTION_A_SIGNATURE)
ALL_FIELDS.update(SECTION_B_CHILDREN)
ALL_FIELDS.update(SECTION_B_SIGNATURE)
ALL_FIELDS.update(SECTION_C_SIBLINGS)
ALL_FIELDS.update(SECTION_C_SIGNATURE)
