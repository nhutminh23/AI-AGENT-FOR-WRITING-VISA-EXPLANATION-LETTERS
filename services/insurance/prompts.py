import json

# Fields that are auto-generated or fixed — Grok should NOT touch these
AUTO_FIELDS = {
    "policy_no", "customer_code", "membership_no",
    "plan", "nationality", "region",
    "period_from", "period_to", "length_of_trip",
    "total_premium",
    # Chubb-specific auto fields
    "issued_date", "total_days", "category",
}

# Fields Grok needs to generate for a new person
GROK_FIELDS = {"insured_name", "dob", "passport_no", "address", "gender"}


def build_grok_prompt(summary: dict, template_key: str) -> str:
    """Build a prompt the user can paste into Grok.
    Only includes fields that actually need AI generation (name, DOB, passport, address).
    Auto-generated fields (policy_no, dates, premium, etc.) are excluded.

    The prompt instructs Grok to USE the person data from the applicant's
    documents (which the user already has), NOT to invent new people.
    """
    # Filter: only send fields Grok should fill
    grok_data = {}
    for key, val in summary.items():
        if key in AUTO_FIELDS:
            continue  # skip auto-generated
        grok_data[key] = val

    json_str = json.dumps(grok_data, indent=2, ensure_ascii=False)
    prompt = f"""I have a travel insurance certificate. I need to fill it with a SPECIFIC person's data from their visa application documents.

Here is the current template data (this is sample data from the template, NOT the real person):

```json
{json_str}
```

📋 YOUR TASK:
Using the applicant's ACTUAL documents (passport, ID card, application form) that I provide below, extract and fill the following fields with their REAL information:
- **insured_name**: The applicant's REAL full name in UPPERCASE without diacritics
- **dob**: The applicant's REAL date of birth in DD/MM/YYYY format
- **passport_no**: The applicant's REAL passport number
- **address**: The applicant's REAL address in English without diacritics

⚠️ STRICT RULES — MUST FOLLOW ALL:
1. **USE THE REAL PERSON'S DATA** from the documents I provide — do NOT invent or generate fake data
2. **ALL TEXT MUST BE IN FULL ENGLISH** — absolutely NO Vietnamese words, NO Vietnamese characters (no ă, â, ê, ô, ơ, ư, đ, diacritics, etc.)
3. **insured_name**: Vietnamese name in UPPERCASE without diacritics. Example: "NGUYEN VAN A", NOT "Nguyễn Văn A"
4. **address**: MUST be FULLY TRANSLATED to English. Translate ALL Vietnamese geographical terms:
   - "Xã" → "Commune" (NOT "Xa")
   - "Huyện" → "District" (NOT "Huyen")  
   - "Tỉnh" → "Province" (NOT "Tinh")
   - "Phường" → "Ward" (NOT "Phuong")
   - "Quận" → "District" (NOT "Quan")
   - "Xóm/Thôn" → "Hamlet" (NOT "Xom/Thon")
   - "Thành phố" → "City" (NOT "Thanh pho")
   - Example: "Hamlet 7C, Con Thoi Commune, Kim Son District, Ninh Binh Province, Viet Nam"
   - WRONG: "Xom 7C, Xa Con Thoi, Kim Son District, Ninh Binh Province, Viet Nam"
5. **dob**: DD/MM/YYYY format (e.g. 21/08/2002)
6. **passport_no**: Copy EXACTLY from the person's passport (1 uppercase letter + 7-8 digits)
7. Return ONLY pure JSON with the EXACT same keys, no explanation

⛔ FORBIDDEN: Any Vietnamese word (Xã, Phường, Quận, Huyện, Tỉnh, Xóm, Thôn, etc.) and any character with diacritics (ả, ã, á, à, ạ, ắ, etc.)
✅ ALLOWED: Only ASCII characters (A-Z, a-z, 0-9, spaces, punctuation) and English geographical terms

Now here are the applicant's documents:

[PASTE APPLICANT DOCUMENTS HERE]

Return JSON:"""
    return prompt
