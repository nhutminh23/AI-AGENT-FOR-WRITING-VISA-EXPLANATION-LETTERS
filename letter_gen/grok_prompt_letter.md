# Grok Prompt — Explanation Letter Data Extraction

Copy the prompt below, paste into Grok along with ALL applicant documents (passport, bank statements, employment letters, property documentation, travel history, previous visa refusal letters, etc.)

---

## PROMPT (Copy từ đây)

I need you to read ALL attached documents and extract structured data to generate a **Visa Explanation Letter**. This is for visa application support.

**IMPORTANT RULES:**
1. ONLY extract information that EXISTS in the documents. If not found, use `null`.
2. DO NOT guess or fabricate any data.
3. Dates must be in **DD Month YYYY** format (e.g., "15 March 2026").
4. All names in **UPPERCASE ENGLISH** (no diacritics). E.g., "NGUYEN VAN A" not "Nguyễn Văn A".
5. Country/city names in **English**. E.g., "Viet Nam", "Ho Chi Minh City".
6. Currency amounts: include both local currency AND approximate USD/AUD equivalent.
7. If there is a **previous visa refusal letter** or **refusal notification**, extract ALL details into `refusal_history`.
8. If the applicant has a **previous explanation letter** (old one), extract key points into `previous_letter_summary`.

**⚠️ STRICTLY FORBIDDEN:**
- DO NOT use "N/A" — if data not found, use `null`
- DO NOT abbreviate — write full details
- DO NOT skip any document — read everything

**Return JSON in this EXACT format (NO extra text outside JSON):**

```json
{
  "applicant": {
    "full_name": "LY THI HONG",
    "dob": "10 June 1961",
    "passport_no": "E00438172",
    "nationality": "Vietnamese",
    "current_address": "Group 1, New Hamlet 1, My Hanh Nam Commune, Duc Hoa District, Long An Province, Viet Nam",
    "phone": "+84 345 529 453",
    "email": null,
    "marital_status": "Married",
    "spouse_name": null,
    "children": [
      {"name": "NGUYEN VAN A", "dob": "1985", "lives_in": "Viet Nam"},
      {"name": "NGUYEN THI B", "dob": "1988", "lives_in": "Viet Nam"},
      {"name": "NGUYEN VAN C", "dob": "1990", "lives_in": "Viet Nam"}
    ],
    "age": 64,
    "occupation_status": "Retiree",
    "health_notes": "Health is not strong due to age"
  },

  "employment": {
    "type": "retiree",
    "company_name": null,
    "job_title": null,
    "income": null,
    "contract_details": null,
    "business_info": null,
    "retirement_details": "Retired, living on personal savings"
  },

  "financial": {
    "bank_name": "BIDV Bank",
    "bank_balance": "VND 200,000,000 (approximately USD 7,589)",
    "savings_type": "Term deposit",
    "deposit_date": "30 March 2026",
    "assets": [],
    "other_financial": [],
    "sponsor": null,
    "trip_funding": "Entirely self-funded from personal life savings"
  },

  "trip": {
    "destination_country": "Australia",
    "visa_type": "Visitor Visa",
    "visa_subclass": "Subclass 600 – Tourist stream",
    "purpose": "Tourism",
    "start_date": "6 May 2026",
    "end_date": "15 May 2026",
    "duration": "11 days / 10 nights",
    "itinerary": [
      {"date": "6 May 2026", "activity": "Arrive Sydney, check in The Social Hotel Sydney"},
      {"date": "7-9 May 2026", "activity": "Sightseeing in Sydney"},
      {"date": "10 May 2026", "activity": "Day visit by V/Line train to sister at 100 Hoopers Road, Kialla, Victoria. Return to hotel same evening."},
      {"date": "11 May 2026", "activity": "Second day visit to sister. Return to hotel same evening."},
      {"date": "12-14 May 2026", "activity": "Melbourne and Brisbane sightseeing"},
      {"date": "15 May 2026", "activity": "Depart Sydney to Ho Chi Minh City"}
    ],
    "flights": {
      "outbound": "Vietjet VJ85 SGN-SYD on 5 May 2026",
      "return": "Vietjet VJ86 SYD-SGN on 15 May 2026"
    },
    "hotels": [
      {"name": "The Social Hotel Sydney", "dates": "6-10 May 2026"},
      {"name": "Hyatt Centric Melbourne", "dates": "10-12 May 2026"},
      {"name": "LyLo Brisbane", "dates": "12-14 May 2026"}
    ],
    "travel_insurance": null,
    "special_notes": "Will make day visits to sister but NOT stay overnight at sister's house"
  },

  "strong_ties": {
    "family_in_home_country": [
      "Three adult children living in Vietnam — strong family roots",
      "Permanent registered residence and home in Long An Province"
    ],
    "property": ["Home in Long An Province"],
    "employment_ties": "Stable savings and ongoing financial commitments in Vietnam",
    "health_ties": "Age 64, health not strong — cannot work or remain abroad for extended period",
    "other_ties": []
  },

  "travel_history": {
    "countries_visited": [
      {"country": "Australia", "year": "2008", "compliance": "Fully complied with all visa conditions"},
      {"country": "Singapore", "year": null, "compliance": "No violations"},
      {"country": "Thailand", "year": null, "compliance": "No violations"},
      {"country": "Cambodia", "year": null, "compliance": "No violations"},
      {"country": "Malaysia", "year": null, "compliance": "No violations"}
    ],
    "visa_compliance_summary": "Excellent travel record with no violations or overstays"
  },

  "refusal_history": null,

  "previous_letter_summary": null,

  "additional_context": "Applicant will visit sister in Kialla, Victoria but will NOT stay overnight — only day visits by train, returning to hotel each evening"
}
```

**SPECIAL INSTRUCTIONS FOR REFUSAL CASES:**

If you find ANY visa refusal documents (refusal letter, decision record, notification), you MUST fill `refusal_history` like this:

```json
{
  "refusal_history": {
    "has_refusals": true,
    "refusals": [
      {
        "country": "Australia",
        "visa_type": "Visitor (subclass 600)",
        "year": "2024",
        "application_number": null,
        "uci": null,
        "refusal_date": "2024",
        "refusal_reason": "Did not demonstrate sufficient ties to Vietnam or adequate incentives to return after a short visit",
        "officer_notes": "Financial evidence and business documentation were limited",
        "regulation_cited": "Migration Regulations 1994"
      },
      {
        "country": "Australia",
        "visa_type": "Visitor (subclass 600)",
        "year": "2025",
        "application_number": null,
        "uci": null,
        "refusal_date": "18 September 2025",
        "refusal_reason": "Same as above — insufficient ties and financial evidence",
        "officer_notes": null,
        "regulation_cited": "Migration Regulations 1994"
      }
    ],
    "circumstances_changed": [
      "Now hold VND 1,700,000,000 (approximately AUD 95,000) in 6-month term deposit with Agribank",
      "Own residential land title (sổ hồng)",
      "Own Mazda CX-5 vehicle registered in name",
      "Operate registered household business with consistent tax payments",
      "14-month car rental contract generating additional income",
      "Married with two dependent children (born 2009, 2018) studying in Vietnam"
    ]
  }
}
```

**NOTES:**
- Read EVERY attached document thoroughly
- If the applicant currently lives in a different country (e.g., on a work/study visa), include that in `applicant.current_visa` and `applicant.current_residence`
- `previous_letter_summary`: If there's an old explanation letter, summarize its key arguments
- `additional_context`: Any important facts that don't fit in other fields

**SPECIAL INSTRUCTIONS FOR GROUP APPLICATIONS (2+ people):**

If the documents contain information for MORE THAN ONE applicant (e.g., husband + wife, parent + child — each with their own passport), you MUST:

1. **Output a JSON array** `[{person1}, {person2}, ...]` — each element is a COMPLETE profile
2. Each person gets their OWN `applicant`, `employment`, `financial`, `trip`, `strong_ties`, `travel_history` sections
3. Each person MUST include `accompanying_persons` listing ALL the OTHER people in the group
4. Each person in `accompanying_persons` MUST have: `full_name`, `passport_no`, `dob`, `sex` (Male/Female), and `passport_expiry`

**IMPORTANT:**
- Output ONLY the JSON array — no extra text, no markdown headers
- Even if 2 people share the same trip/flights/hotels, EACH profile must have the FULL trip info
- `accompanying_persons` lists the OTHER people (NOT the applicant themselves)
- `sex` and `passport_expiry` in `accompanying_persons` are REQUIRED — read from passport/CCCD
- If a parent is deceased, use `"Deceased"` for their address fields

**Example for 2 applicants (husband + wife):**

```json
[
  {
    "applicant": {
      "full_name": "THAN VAN KHOAN",
      "dob": "10 April 1953",
      "passport_no": "E03124147",
      "nationality": "Vietnamese",
      "current_address": "383/11 Nguyen Van Cu, Tan Lap, Buon Ma Thuot, Dak Lak, Viet Nam",
      "phone": "+84 905 050 699",
      "email": null,
      "marital_status": "Married",
      "spouse_name": "THIEU THI PHAN",
      "children": [],
      "age": 72,
      "occupation_status": "Self-employed",
      "health_notes": null
    },
    "employment": { "type": "self-employed", "business_info": "..." },
    "financial": { "bank_name": "...", "bank_balance": "..." },
    "trip": { "destination_country": "Australia", "start_date": "...", "end_date": "..." },
    "strong_ties": { "family_in_home_country": ["..."], "property": ["..."] },
    "travel_history": { "countries_visited": [], "visa_compliance_summary": "..." },
    "refusal_history": null,
    "previous_letter_summary": null,
    "additional_context": "Travelling with spouse THIEU THI PHAN...",
    "accompanying_persons": [
      {
        "full_name": "THIEU THI PHAN",
        "passport_no": "E03181723",
        "dob": "02 April 1959",
        "sex": "Female",
        "passport_expiry": "07 May 2035"
      }
    ]
  },
  {
    "applicant": {
      "full_name": "THIEU THI PHAN",
      "dob": "02 April 1959",
      "passport_no": "E03181723",
      "nationality": "Vietnamese",
      "current_address": "383/11 Nguyen Van Cu, Tan Lap, Buon Ma Thuot, Dak Lak, Viet Nam",
      "phone": null,
      "email": null,
      "marital_status": "Married",
      "spouse_name": "THAN VAN KHOAN",
      "children": [],
      "age": 66,
      "occupation_status": "Homemaker",
      "health_notes": null
    },
    "employment": { "type": "homemaker" },
    "financial": { "bank_name": "...", "bank_balance": "..." },
    "trip": { "destination_country": "Australia", "start_date": "...", "end_date": "..." },
    "strong_ties": { "family_in_home_country": ["..."], "property": ["..."] },
    "travel_history": { "countries_visited": [], "visa_compliance_summary": "..." },
    "refusal_history": null,
    "previous_letter_summary": null,
    "additional_context": "Travelling with spouse THAN VAN KHOAN...",
    "accompanying_persons": [
      {
        "full_name": "THAN VAN KHOAN",
        "passport_no": "E03124147",
        "dob": "10 April 1953",
        "sex": "Male",
        "passport_expiry": "..."
      }
    ]
  }
]
```

If there is only ONE person, output a single JSON object `{...}` (NOT an array). Do NOT include `accompanying_persons` for single applicants.

**SPECIAL INSTRUCTIONS FOR INVITATION LETTER (Family Visit to Australia):**

If the applicant's trip purpose involves **visiting a relative/friend who LIVES in Australia** (e.g., visiting a sibling, child, parent, or sponsor in Australia), you MUST include an `invitation_data` object in the profile. This data will be used to auto-generate an Invitation Letter.

**How to detect:** Look for clues such as:
- Trip purpose mentions "family visit", "visiting brother/sister/mother/father/relative"
- Itinerary includes visiting someone's home in Australia
- Documents mention a sponsor or host in Australia
- A relative's address in Australia is mentioned

**Add this to each applicable applicant's profile:**

```json
{
  "invitation_data": {
    "host": {
      "full_name": "THI MY LINH TRAN",
      "dob": "13 June 1997",
      "nationality": "Vietnamese",
      "passport_no": "C5776007",
      "address": "Unit 5/15 High St, Swan Hill, VIC 3585",
      "phone": "0448687329",
      "occupation": "Slicer at a meat processing company",
      "annual_income": "Approximately AUD 70,000",
      "visa_status": "living and working in Australia",
      "visa_note": "At present, I am in the process of transitioning from a temporary work visa to permanent residency in Australia."
    },
    "guest": {
      "full_name": "VU BAO MINH TRAN",
      "dob": "4 September 2009",
      "passport_no": "E03450389",
      "sex": "Male",
      "relationship": "younger brother"
    },
    "trip": {
      "start_date": "1 June 2026",
      "end_date": "15 June 2026",
      "purpose": "the purpose of family visit and tourism"
    },
    "accompanying": [
      {
        "full_name": "our mother: THI DAN VU",
        "relationship": "mother",
        "note": "who already holds a valid Australian visa"
      }
    ]
  }
}
```

**IMPORTANT RULES for invitation_data:**
- `host` = the person IN Australia who writes the invitation letter
- `guest` = the applicant being invited (the visa applicant)
- `relationship` = how the host refers to the guest (e.g., "younger brother", "mother", "friend")
- `accompanying` = other people travelling with the guest (optional, can be empty array `[]`)
- `visa_status` = host's current status in Australia (e.g., "living and working in Australia", "permanent resident of Australia")
- `visa_note` = optional extra sentence about host's visa situation
- If host info is incomplete (e.g., no income data), still include what you have — use `null` for missing fields
- If NO family visit / NO host in Australia → do NOT include `invitation_data` at all (omit the key)

