# Grok Prompt Template — Australia Form 54 (Family Composition)

Copy the content below, paste into Grok along with ALL applicants' documents (passport, CCCD, birth certificate, marriage certificate, etc.)

> **Lưu ý:** Prompt này tự nhận biết số lượng người nộp đơn từ tài liệu đính kèm.
> Nếu có 2 người → sinh ra 2 JSON riêng biệt. Nếu có 5 người → sinh ra 5 JSON riêng biệt.
> Mỗi JSON copy-paste riêng vào app để sinh 1 Form 54.

---

## PROMPT (Copy từ đây)

I need you to read ALL attached documents and extract family composition data to fill Australia's **Form 54 — Family Composition** for a visa application.

---

### 🔑 CRITICAL: MULTI-APPLICANT DETECTION

**Step 1 — Count how many APPLICANTS exist:**
- Look at ALL passports/CCCD in the documents
- Each person who has BOTH a passport AND a CCCD (or visa application form) = 1 applicant
- Family members mentioned in birth/marriage certificates but who do NOT have their own passport = NOT applicants (they go into parents/siblings/children sections)

**Step 2 — Generate ONE separate JSON for EACH applicant:**
- If you find 2 applicants (e.g. husband + wife both applying) → output 2 separate JSON blocks
- If you find 3 applicants → output 3 separate JSON blocks
- Each JSON block is a COMPLETE, INDEPENDENT Form 54

**Step 3 — Role swapping for each form:**
- In Form of Person A: Person A = `applicant`, Person B = `spouse`
- In Form of Person B: Person B = `applicant`, Person A = `spouse`
- Parents/siblings/children are filled from EACH person's OWN perspective

---

### 📋 DATA RULES:

1. ONLY extract information that EXISTS in the documents. If not found, use `null`.
2. DO NOT guess or fabricate any data.
3. Dates must be in **DD/MM/YYYY** format (Australian standard).
4. All names in **UPPERCASE ENGLISH** (no diacritics). E.g. `"NGUYEN VAN A"` not `"Nguyễn Văn A"`.
5. Country/city names in **English**. E.g. `"Viet Nam"`, `"Ho Chi Minh City"`.
6. Marital status — use EXACTLY ONE of these codes:
   - **"M"** = Married
   - **"E"** = Engaged
   - **"F"** = De facto
   - **"S"** = Separated
   - **"D"** = Divorced
   - **"W"** = Widowed
   - **"N"** = Never married / Single
7. **Deceased family members:** If a parent or sibling has PASSED AWAY, you MUST still include them. Set both address fields to `"Deceased"`. Keep their name, DOB, and marital status as normal. Example:
   ```json
   {
     "family_name": "NGUYEN",
     "given_name": "VAN C",
     "dob": "22/08/1940",
     "marital_status": "W",
     "home_address_line1": "Deceased"
   }
   ```

### ⚠️ STRICTLY FORBIDDEN:
- DO NOT use `"same as applicant"` — write the FULL address for each person
- DO NOT use `"N/A"` — if student write `"Student"`, if child write `"Minor"`, if unemployed write `"Unemployed"`
- DO NOT use `"Unknown"` — if not found, use `null`
- DO NOT abbreviate addresses — write full street number, ward, district, city, country
- DO NOT wrap multiple forms in a JSON array `[...]` — output each form as a SEPARATE JSON object
- DO NOT skip deceased parents/siblings — they MUST still appear with address = `"Deceased"`

---

### 📤 OUTPUT FORMAT:

Output each applicant's Form 54 as a **separate JSON object** (NOT inside an array).
Separate each JSON block with a clear header line like below.
Each JSON must be a standalone object `{...}` that can be copy-pasted independently.

---

**===== FORM 54: NGUYEN VAN A (1/2) =====**

```json
{
  "applicant": {
    "family_name": "NGUYEN",
    "given_name": "VAN A",
    "dob": "15/01/1990",
    "marital_status": "M",
    "home_address_line1": "123 Nguyen Hue Street, Ben Nghe Ward, District 1",
    "home_address_line2": "Ho Chi Minh City, Viet Nam"
  },

  "spouse": {
    "family_name": "TRAN",
    "given_name": "THI B",
    "dob": "20/03/1992",
    "marital_status": "M",
    "home_address_line1": "123 Nguyen Hue Street, Ben Nghe Ward, District 1",
    "home_address_line2": "Ho Chi Minh City, Viet Nam"
  },

  "defacto_partner": null,

  "parents": [
    {
      "family_name": "NGUYEN",
      "given_name": "VAN C",
      "dob": "22/08/1960",
      "marital_status": "M",
      "home_address_line1": "45 Tran Phu Street, Ward 5",
      "home_address_line2": "Vung Tau City, Viet Nam"
    },
    {
      "family_name": "LE",
      "given_name": "THI D",
      "dob": "10/05/1965",
      "marital_status": "M",
      "home_address_line1": "45 Tran Phu Street, Ward 5",
      "home_address_line2": "Vung Tau City, Viet Nam"
    }
  ],

  "siblings": [
    {
      "family_name": "NGUYEN",
      "given_name": "VAN E",
      "dob": "15/06/1988",
      "marital_status": "M",
      "home_address_line1": "78 Le Loi Street, Ward 1, District 5",
      "home_address_line2": "Ho Chi Minh City, Viet Nam"
    }
  ],

  "children": [
    {
      "family_name": "NGUYEN",
      "given_name": "VAN F",
      "dob": "01/01/2020",
      "marital_status": "N",
      "home_address_line1": "123 Nguyen Hue Street, Ben Nghe Ward, District 1",
      "home_address_line2": "Ho Chi Minh City, Viet Nam"
    }
  ]
}
```

**===== FORM 54: TRAN THI B (2/2) =====**

```json
{
  "applicant": {
    "family_name": "TRAN",
    "given_name": "THI B",
    "dob": "20/03/1992",
    "marital_status": "M",
    "home_address_line1": "123 Nguyen Hue Street, Ben Nghe Ward, District 1",
    "home_address_line2": "Ho Chi Minh City, Viet Nam"
  },

  "spouse": {
    "family_name": "NGUYEN",
    "given_name": "VAN A",
    "dob": "15/01/1990",
    "marital_status": "M",
    "home_address_line1": "123 Nguyen Hue Street, Ben Nghe Ward, District 1",
    "home_address_line2": "Ho Chi Minh City, Viet Nam"
  },

  "defacto_partner": null,

  "parents": [
    {
      "family_name": "TRAN",
      "given_name": "VAN G",
      "dob": "05/03/1958",
      "marital_status": "M",
      "home_address_line1": "12 Hai Ba Trung Street, Ward 3, District 3",
      "home_address_line2": "Ho Chi Minh City, Viet Nam"
    },
    {
      "family_name": "PHAM",
      "given_name": "THI H",
      "dob": "18/07/1962",
      "marital_status": "M",
      "home_address_line1": "12 Hai Ba Trung Street, Ward 3, District 3",
      "home_address_line2": "Ho Chi Minh City, Viet Nam"
    }
  ],

  "siblings": [],

  "children": [
    {
      "family_name": "NGUYEN",
      "given_name": "VAN F",
      "dob": "01/01/2020",
      "marital_status": "N",
      "home_address_line1": "123 Nguyen Hue Street, Ben Nghe Ward, District 1",
      "home_address_line2": "Ho Chi Minh City, Viet Nam"
    }
  ]
}
```

---

### 📝 NOTES:

- `parents`: Maximum 2 per person (father and mother of THAT applicant)
- `siblings`: Maximum 3 per person (form limit)
- `children`: Maximum 3 per person (form limit)
- `defacto_partner`: Only if applicant has a de facto (unmarried) partner. Otherwise `null`.
- If no spouse/defacto/children/siblings, set to `null` or empty array `[]`.
- EVERY person MUST have their OWN full address — NO "same as applicant".
- Children/students occupation: write `"Student"` or `"Minor"`, NOT `"N/A"`.

### 🔄 ROLE SWAPPING CHEAT SHEET:

| Scenario | Person A's Form | Person B's Form |
|----------|----------------|----------------|
| Married couple | A = applicant, B = spouse | B = applicant, A = spouse |
| Parent + child | Parent = applicant, Child in `children[]` | Child = applicant, Parent in `parents[]` |
| Siblings | Sibling A = applicant, B in `siblings[]` | Sibling B = applicant, A in `siblings[]` |
| Unrelated | Each has independent form, no cross-reference | Each has independent form |

### ✅ SELF-CHECK before outputting:
1. Count all passports/CCCDs → Did you generate that many separate JSON blocks?
2. Each JSON block has a different person as `applicant`?
3. Each JSON is a standalone `{...}` object (NOT wrapped in an array `[...]`)?
4. Spouse/parent/sibling roles are correctly swapped in each block?
5. Every address is FULL (not "same as applicant")?
