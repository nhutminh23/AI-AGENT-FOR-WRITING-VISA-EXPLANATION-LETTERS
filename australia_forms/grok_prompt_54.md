# Grok Prompt Template — Australia Form 54 (Family Composition)

Copy the content below, paste into Grok along with the applicant's documents (passport, CCCD, birth certificate, marriage certificate, etc.)

---

## PROMPT (Copy từ đây)

I need you to read the attached documents and extract family composition data to fill Australia's **Form 54 — Family Composition** for a visa application.

**IMPORTANT RULES:**
1. ONLY extract information that EXISTS in the documents. If not found, use null.
2. DO NOT guess or fabricate any data.
3. Dates must be in **DD/MM/YYYY** format (Australian standard).
4. All names in **UPPERCASE ENGLISH** (no diacritics). E.g. "NGUYEN VAN A" not "Nguyễn Văn A".
5. Country/city names in **English**. E.g. "Viet Nam", "Ho Chi Minh City".
6. Marital status — use EXACTLY ONE of these codes: **"M"** (Married), **"E"** (Engaged), **"F"** (De facto), **"S"** (Separated), **"D"** (Divorced), **"W"** (Widowed), **"N"** (Never married / Single).

**⚠️ STRICTLY FORBIDDEN:**
- DO NOT use "same as applicant" — write the FULL address for each person
- DO NOT use "N/A" — if student write "Student", if child write "Minor", if unemployed write "Unemployed"
- DO NOT use "Unknown" — if not found, use null
- DO NOT abbreviate addresses — write full street number, ward, district, city, country

**Return JSON in this EXACT format (NO extra text outside JSON):**

```json
{
  "applicant": {
    "family_name": "NGUYEN",
    "given_name": "VAN A",
    "dob": "15/01/1990",
    "marital_status": "M",
    "home_address_line1": "123 Nguyen Hue Street, Ben Nghe Ward, District 1",
    "home_address_line2": "Ho Chi Minh City, Viet Nam",
    "prev_country": "Viet Nam",
    "declaration1": "",
    "declaration2": ""
  },

  "spouse": {
    "family_name": "TRAN",
    "given_name": "THI B",
    "dob": "20/03/1992",
    "marital_status": "M",
    "home_address_line1": "123 Nguyen Hue Street, Ben Nghe Ward, District 1",
    "home_address_line2": "Ho Chi Minh City, Viet Nam",
    "prev_country": "Viet Nam"
  },

  "defacto_partner": null,

  "parents": [
    {
      "family_name": "NGUYEN",
      "given_name": "VAN C",
      "dob": "22/08/1960",
      "marital_status": "M",
      "home_address_line1": "45 Tran Phu Street, Ward 5",
      "home_address_line2": "Vung Tau City, Viet Nam",
      "prev_country": "Viet Nam"
    },
    {
      "family_name": "LE",
      "given_name": "THI D",
      "dob": "10/05/1965",
      "marital_status": "M",
      "home_address_line1": "45 Tran Phu Street, Ward 5",
      "home_address_line2": "Vung Tau City, Viet Nam",
      "prev_country": "Viet Nam"
    }
  ],

  "siblings": [
    {
      "family_name": "NGUYEN",
      "given_name": "VAN E",
      "dob": "15/06/1988",
      "marital_status": "M",
      "home_address_line1": "78 Le Loi Street, Ward 1, District 5",
      "home_address_line2": "Ho Chi Minh City, Viet Nam",
      "prev_country": "Viet Nam"
    }
  ],

  "children": [
    {
      "family_name": "NGUYEN",
      "given_name": "VAN F",
      "dob": "01/01/2020",
      "marital_status": "N",
      "home_address_line1": "123 Nguyen Hue Street, Ben Nghe Ward, District 1",
      "home_address_line2": "Ho Chi Minh City, Viet Nam",
      "prev_country": "Viet Nam"
    }
  ]
}
```

**NOTES:**
- `parents`: Maximum 2 (father and mother)
- `siblings`: Maximum 3 (form limit)
- `children`: Maximum 3 (form limit)
- `defacto_partner`: Only if applicant has a de facto (unmarried) partner. Otherwise null.
- If no spouse/defacto/children/siblings, set to null or empty array [].
- EVERY person MUST have their OWN full address — NO "same as applicant".
- Occupations for children/students: write "Student" or "Minor", NOT "N/A".
