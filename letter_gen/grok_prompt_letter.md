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

If the documents contain information for MORE THAN ONE person (e.g., family group, couple, parent + child), you MUST add an `accompanying_persons` array to the JSON. Each person should have at minimum: `full_name`, `passport_no`, `dob`, `sex`, and `passport_expiry` (date of expiry of passport).

Example:
```json
{
  "applicant": { ... },
  "accompanying_persons": [
    {
      "full_name": "NGO NGAN HA",
      "passport_no": "C3980690",
      "dob": "15 March 1985",
      "sex": "Female",
      "passport_expiry": "15 March 2035"
    },
    {
      "full_name": "TRAN TRUNG GIA HUNG",
      "passport_no": "P04067466",
      "dob": "10 June 2018",
      "sex": "Male",
      "passport_expiry": "10 June 2028"
    }
  ],
  "trip": { ... },
  ...
}
```

If there is only ONE person, do NOT include `accompanying_persons`.

