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
6. **Company names / Business entity types MUST be translated to English.** NEVER leave Vietnamese terms (even without diacritics). Use this mapping:
   - "Hộ kinh doanh" / "Ho kinh doanh" → **"Sole Proprietorship"** or **"Business Household"**
   - "Công ty TNHH" / "Cong ty TNHH" → **"Company Limited"** or **"Co., Ltd."**
   - "Công ty TNHH MTV" → **"Single-Member Limited Liability Company"**
   - "Công ty Cổ phần" / "CTCP" → **"Joint Stock Company"** or **"Corporation"**
   - "Doanh nghiệp tư nhân" → **"Private Enterprise"**
   - "Hợp tác xã" → **"Cooperative"**
   - "Chi nhánh" → **"Branch"**
   - "Văn phòng đại diện" → **"Representative Office"**
   - Example: "Hộ kinh doanh Nhà Hàng Phong Lan" → **"Sole Proprietorship — Phong Lan Restaurant"**
   - Example: "Công ty TNHH Thương Mại ABC" → **"ABC Trading Co., Ltd."**
   - Example: "CTCP Đầu tư XYZ" → **"XYZ Investment Corporation"**
7. **Job titles / Positions MUST be in English:**
   - "Chủ hộ kinh doanh" → **"Business Owner"** or **"Sole Proprietor"**
   - "Giám đốc" / "Giam doc" → **"Director"**
   - "Phó giám đốc" → **"Deputy Director"**
   - "Kế toán trưởng" → **"Chief Accountant"**
   - "Nhân viên" → **"Employee"** or **"Staff"**
   - "Công nhân" → **"Worker"**
   - "Nội trợ" → **"Homemaker"**
   - "Hưu trí" → **"Retiree"**
   - "Buôn bán" / "Kinh doanh tự do" → **"Self-employed"** or **"Freelance Business"**
8. Currency amounts: include both local currency AND approximate USD/AUD equivalent.
9. If there is a **previous visa refusal letter** or **refusal notification**, extract ALL details into `refusal_history`.
10. If the applicant has a **previous explanation letter** (old one), extract key points into `previous_letter_summary`.
11. For each applicant, extract **booking consistency details** (flight + hotel + trip dates + duration + payment/booking status if shown).
12. For each applicant, extract a **financial chain** clearly: fund owner, source(s) of funds, balance/deposit, income continuity, and whether funds are sufficient for trip length.
13. For each applicant, extract **strong ties** with concrete home-country anchors: relatives/dependents, work/business continuity, assets/property, obligations.
14. Add `applicant.personalization_highlights` (3-8 bullets) with applicant-specific facts that can be used verbatim as individualized evidence points in cover letters.
15. For group applications, keep each person's profile fully individualized (no copy-paste summaries across members).

**⚠️ STRICTLY FORBIDDEN:**
- DO NOT use "N/A" — if data not found, use `null`
- DO NOT abbreviate — write full details
- DO NOT skip any document — read everything
- DO NOT leave ANY Vietnamese text in the output (even without diacritics) — translate EVERYTHING to English

**4-PILLAR JSON COMPLETENESS CHECK (MANDATORY):**
- Pillar 1 (Embassy structure readiness): enough identity/visa-purpose/return-intent facts to draft officer-friendly sections.
- Pillar 2 (Booking-backed tourism): trip dates, flights, hotels, duration, and booking/payment evidence consistency.
- Pillar 3 (Full profile picture): financial chain + relatives/dependents + home-country ties.
- Pillar 4 (Deep personalization): applicant-specific highlights that differentiate this person from other group members.
- If any pillar lacks evidence in documents, still return the field with `null` or empty list and explain the gap in `consistency_checks.missing_evidence`.

**Return JSON in this EXACT format (NO extra text outside JSON):**

```json
{
  "applicant": {
    "full_name": "LY THI HONG",
    "dob": "10 June 1961",
    "passport_no": "E00438172",
    "nationality": "Vietnamese",
    "current_residence": "Viet Nam",
    "current_visa": null,
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
    "health_notes": "Health is not strong due to age",
    "personalization_highlights": [
      "64-year-old retiree applying for a short 11-day tourism trip",
      "Previously visited Australia and complied with visa conditions",
      "Will do day visits to sister and return to hotel each evening"
    ]
  },

  "employment": {
    "type": "retiree",
    "company_name": null,
    "job_title": null,
    "income": null,
    "income_sources": [
      {"source": "Savings", "amount": "VND 200,000,000", "frequency": null}
    ],
    "contract_details": null,
    "business_info": null,
    "retirement_details": "Retired, living on personal savings"
  },

  "financial": {
    "bank_name": "BIDV Bank",
    "bank_balance": "VND 200,000,000 (approximately USD 7,589)",
    "savings_type": "Term deposit",
    "deposit_date": "30 March 2026",
    "fund_owner": "Applicant",
    "fund_source_summary": "Personal life savings accumulated over many years",
    "assets": [],
    "other_financial": [],
    "sponsor": null,
    "trip_funding": "Entirely self-funded from personal life savings",
    "estimated_trip_cost": null,
    "trip_cost_coverage_statement": "Available funds are sufficient for flights, hotels, meals, and local transport for 11 days"
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
    "booking_evidence": {
      "flights_confirmed": true,
      "hotels_confirmed": true,
      "payment_status": "Confirmed/paid if shown in provided documents",
      "booking_consistency_notes": "Dates, duration, and route are consistent across itinerary and bookings"
    },
    "travel_insurance": null,
    "special_notes": "Will make day visits to sister but NOT stay overnight at sister's house"
  },

  "strong_ties": {
    "family_in_home_country": [
      "Three adult children living in Vietnam — strong family roots",
      "Permanent registered residence and home in Long An Province"
    ],
    "relatives_and_dependents": [
      {"name": "CHILD 1", "relationship": "Adult child", "lives_in": "Viet Nam"},
      {"name": "CHILD 2", "relationship": "Adult child", "lives_in": "Viet Nam"},
      {"name": "CHILD 3", "relationship": "Adult child", "lives_in": "Viet Nam"}
    ],
    "property": ["Home in Long An Province"],
    "employment_ties": "Stable savings and ongoing financial commitments in Vietnam",
    "health_ties": "Age 64, health not strong — cannot work or remain abroad for extended period",
    "other_ties": [],
    "return_drivers": [
      "Family roots in Viet Nam",
      "Permanent residence in Viet Nam",
      "Ongoing obligations in Viet Nam"
    ]
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

  "consistency_checks": {
    "booking_dates_consistent": true,
    "funding_and_trip_duration_consistent": true,
    "group_information_consistent": true,
    "missing_evidence": []
  },

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
- For EACH person, fill `applicant.personalization_highlights` with that person's own role/evidence (do not duplicate the exact same bullets for all members).
- For minors, clearly extract dependency context (parental funding/representation/schooling) under `strong_ties` and `additional_context`.

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

**CRITICAL: When MULTIPLE applicants travel together (e.g., husband + wife, family group), ALL travellers must be listed in the `guests` array.** The invitation letter will invite the entire group, not just one person. Each guest object includes the guest's relationship to the host.

**Add this to each applicable applicant's profile:**

```json
{
  "invitation_data": {
    "host": {
      "full_name": "THAN VAN KHANH",
      "dob": "13 August 1961",
      "nationality": "Vietnamese",
      "passport_no": "C5776007",
      "address": "206 Southern Road, Heidelberg West, VIC 3081, Australia",
      "phone": "0448687329",
      "occupation": "Retired / Self-employed",
      "annual_income": "Approximately AUD 50,000",
      "visa_status": "permanent resident of Australia",
      "visa_note": null
    },
    "guests": [
      {
        "full_name": "THAN VAN KHOAN",
        "dob": "10 April 1953",
        "passport_no": "E03124147",
        "sex": "Male",
        "relationship": "elder brother"
      },
      {
        "full_name": "THIEU THI PHAN",
        "dob": "2 April 1959",
        "passport_no": "E03124148",
        "sex": "Female",
        "relationship": "sister-in-law"
      }
    ],
    "trip": {
      "start_date": "1 June 2026",
      "end_date": "15 June 2026",
      "purpose": "the purpose of family visit and tourism"
    },
    "accompanying": []
  }
}
```

**IMPORTANT RULES for invitation_data:**
- `host` = the person IN Australia who writes the invitation letter
- `guests` = array of ALL travellers being invited (each visa applicant in the group). Even if only 1 person, use array format: `[{...}]`
- Each guest has: `full_name`, `dob`, `passport_no`, `sex`, `relationship` (how the host refers to this guest, e.g., "elder brother", "sister-in-law", "mother", "friend")
- `accompanying` = other people travelling WITH the guests who are NOT applying for visa (optional, can be empty `[]`)
- `visa_status` = host's current status in Australia (e.g., "living and working in Australia", "permanent resident of Australia")
- `visa_note` = optional extra sentence about host's visa situation
- If host info is incomplete (e.g., no income data), still include what you have — use `null` for missing fields
- If NO family visit / NO host in Australia → do NOT include `invitation_data` at all (omit the key)
- **For backward compatibility:** if you output `guest` (singular object) instead of `guests` (array), the system will auto-convert it. But prefer `guests` array format.


