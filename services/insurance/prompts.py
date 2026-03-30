import json

# Fields that are auto-generated or fixed — Grok should NOT touch these
AUTO_FIELDS = {
    "policy_no", "customer_code", "membership_no",
    "plan", "nationality", "region",
    "period_from", "period_to", "length_of_trip",
    "total_premium",
}

# Fields Grok needs to generate for a new person
GROK_FIELDS = {"insured_name", "dob", "passport_no", "address"}


def build_grok_prompt(summary: dict, template_key: str) -> str:
    """Build a prompt the user can paste into Grok.
    Only includes fields that actually need AI generation (name, DOB, passport, address).
    Auto-generated fields (policy_no, dates, premium, etc.) are excluded.
    """
    # Filter: only send fields Grok should fill
    grok_data = {}
    for key, val in summary.items():
        if key in AUTO_FIELDS:
            continue  # skip auto-generated
        grok_data[key] = val

    json_str = json.dumps(grok_data, indent=2, ensure_ascii=False)
    prompt = f"""I have a travel insurance certificate. Generate NEW personal details for a different person.

Here are the fields I need you to fill:

```json
{json_str}
```

⚠️ STRICT RULES — MUST FOLLOW ALL:
1. **ALL TEXT MUST BE IN ENGLISH** — absolutely NO Vietnamese characters (no ă, â, ê, ô, ơ, ư, đ, diacritics, etc.)
2. **insured_name**: Vietnamese name in UPPERCASE without diacritics. Example: "NGUYEN VAN A", NOT "Nguyễn Văn A"
3. **address**: MUST be in English. Use format: "192 Tran Quang Khai, Tan Dinh Ward, Ho Chi Minh". NO Vietnamese diacritics
4. **dob**: DD/MM/YYYY format (e.g. 21/08/2002)
5. **passport_no**: 1 uppercase letter + 7-8 digits (e.g. P01828868)
6. Return ONLY pure JSON with the EXACT same keys, no explanation

⛔ FORBIDDEN: Any character with diacritics (ả, ã, á, à, ạ, ắ, etc.)
✅ ALLOWED: Only ASCII characters (A-Z, a-z, 0-9, spaces, punctuation)

Return JSON:"""
    return prompt
