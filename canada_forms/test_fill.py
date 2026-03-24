"""Test: fill IMM5645E with sample data and verify annotation values."""
import sys
sys.path.insert(0, ".")

from canada_forms.fill_imm5645 import fill_imm5645
from pathlib import Path
import pypdf

# Sample data
sample_data = {
    "visitor": "1",
    "app_name": "NGUYEN VAN A",
    "app_dob": "1990-05-15",
    "app_cob": "Viet Nam",
    "app_address": "123 Nguyen Hue, Ho Chi Minh City, Viet Nam",
    "app_occupation": "Software Engineer",
    "spouse_name": "TRAN THI B",
    "spouse_dob": "1992-03-20",
    "spouse_cob": "Viet Nam",
    "spouse_accompanying_yes": True,
    "mother_name": "LE THI C",
    "mother_dob": "1965-01-10",
    "father_name": "NGUYEN VAN D",
    "father_dob": "1963-08-25",
    "child_0_name": "NGUYEN VAN E",
    "child_0_relationship": "Son",
    "child_0_dob": "2018-12-01",
    "child_0_accompanying_yes": True,
}

template = "canada_forms/templates/imm5645e.pdf"
output = "canada_forms/output/test_filled.pdf"

result = fill_imm5645(sample_data, template, output)
print(f"SUCCESS! → {result} ({Path(result).stat().st_size / 1024:.0f} KB)")

# Verify by reading annotations
reader = pypdf.PdfReader(str(result))
if reader.is_encrypted:
    reader.decrypt("")

checks = {
    "AppName[0]": "NGUYEN VAN A",
    "AppDOB[0]": "1990-05-15",
    "SpouseName[0]": "TRAN THI B",
    "MotherName[0]": "LE THI C",
    "FatherName[0]": "NGUYEN VAN D",
    "ChildName[0]": "NGUYEN VAN E",
}

found = {}
for page in reader.pages:
    if "/Annots" not in page:
        continue
    for annot_ref in page["/Annots"]:
        annot = annot_ref.get_object()
        t = str(annot.get("/T", ""))
        v = str(annot.get("/V", ""))
        if t in checks:
            found[t] = v

print("\nVerification:")
all_pass = True
for tag, expected in checks.items():
    actual = found.get(tag, "NOT FOUND")
    ok = expected in actual
    all_pass = all_pass and ok
    print(f"  {'✅' if ok else '❌'} {tag}: '{actual}'")

print(f"\n{'🎉 ALL CHECKS PASSED!' if all_pass else '⚠️ Some checks failed'}")
