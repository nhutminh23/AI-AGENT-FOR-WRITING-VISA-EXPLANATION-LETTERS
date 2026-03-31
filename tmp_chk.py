"""Quick test: checkbox tick + date painting together"""
import shutil, os, io
shutil.copy("australia_forms/templates/54_backup2.pdf", "australia_forms/templates/54.pdf")

from australia_forms.fill_54 import fill_form54

data = {
    "ap_family_name": "LY", "ap_given_name": "THI HONG",
    "ap_dob": "10-Jun-1961", "ap_marital": "Married",
    "ap_home_addr1": "Group 1, New Hamlet 1, My Hanh Nam Commune",
    "ap_home_addr2": "Duc Hoa District, Long An Province, Viet Nam",
    "as_family_name": "NGUYEN", "as_given_name": "HUU THANH",
    "as_dob": "01-Jan-1959", "as_marital": "Married",
    "parent_0_family_name": "LY", "parent_0_given_name": "VAN LEN",
    "parent_0_dob": "01-Jan-1938", "parent_0_marital": "M",
    "parent_1_family_name": "LE", "parent_1_given_name": "THI TIEM",
    "parent_1_dob": "01-Jan-1942", "parent_1_marital": "M",
    "sibling_0_family_name": "LE", "sibling_0_given_name": "THU THUY",
    "sibling_0_dob": "13-Sep-1965",
    "child_0_family_name": "NGUYEN", "child_0_given_name": "CHI THIEN",
    "child_0_dob": "09-Oct-1989", "child_0_marital": "N",
    "child_1_family_name": "NGUYEN", "child_1_given_name": "PHUONG LIEN",
    "child_1_dob": "01-Jan-1983", "child_1_marital": "N",
}

result = fill_form54(
    data,
    "australia_forms/templates/54.pdf",
    "australia_forms/output/test_final_v2.pdf",
)

# Render to verify
import fitz
doc = fitz.open(str(result))
pix = doc[0].get_pixmap(dpi=150)
pix.save("australia_forms/output/test_final_v2.png")
artifacts = r"C:\Users\TIEN NGUYEN\.gemini\antigravity\brain\96a6b5ce-55c3-401d-85d1-6b1b6c5e3078"
shutil.copy("australia_forms/output/test_final_v2.png", os.path.join(artifacts, "test_final_v2.png"))
print("Done!")
doc.close()
