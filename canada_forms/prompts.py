"""
AI prompts for extracting family information from documents.

Used by agent.py to instruct the LLM on what data to extract
and how to structure the output for IMM5645E form filling.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# System prompt — sets the AI's role and anti-hallucination rules
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a precise document data extractor for Canadian visa applications.

## YOUR ROLE
Extract family information from uploaded documents to fill the IMM5645E (Family Information) form.

## CRITICAL RULES — ANTI-HALLUCINATION
1. ONLY extract information that is EXPLICITLY stated in the documents.
2. If a piece of information is NOT found, set it to null. NEVER guess or infer.
3. Do NOT make up dates, names, addresses, or any other data.
4. For each extracted field, provide a confidence score (high/medium/low).
5. Include the source (which document/file the data came from).

## DATE FORMAT
All dates must be in YYYY-MM-DD format. If only year is available, use YYYY-01-01.
If day is missing, use the 1st of the month.

## MARITAL STATUS VALUES
Use one of: "Single", "Married", "Common-Law", "Divorced", "Separated", "Widowed", "Annulled", "Unknown"

## COUNTRY/CITY OF BIRTH
Use English names for countries and cities. Example: "Viet Nam", "Ho Chi Minh City"
"""

# ---------------------------------------------------------------------------
# User prompt template — includes document content and output schema
# ---------------------------------------------------------------------------
USER_PROMPT_TEMPLATE = """## DOCUMENTS CONTENT
{documents_content}

## TASK
Extract ALL family information for the IMM5645E (Family Information / Renseignements sur la famille) form.

## REQUIRED OUTPUT — JSON ONLY
Return a single JSON object with the following structure. Use null for any field you cannot find.
Do NOT include any text outside the JSON block.

```json
{{
  "application_type": "visitor" | "worker" | "student" | "other",

  "applicant": {{
    "name": "<full name as in passport>",
    "dob": "<YYYY-MM-DD>",
    "country_of_birth": "<country>",
    "address": "<full current address>",
    "occupation": "<current occupation>",
    "marital_status": "<status>"
  }},

  "spouse": {{
    "name": "<full name or null>",
    "dob": "<YYYY-MM-DD or null>",
    "country_of_birth": "<country or null>",
    "address": "<address or null>",
    "occupation": "<occupation or null>",
    "marital_status": "<status or null>",
    "accompanying": true | false | null
  }},

  "mother": {{
    "name": "<full name or null>",
    "dob": "<YYYY-MM-DD or null>",
    "country_of_birth": "<country or null>",
    "address": "<address or null>",
    "occupation": "<occupation or null>",
    "marital_status": "<status or null>",
    "accompanying": true | false | null
  }},

  "father": {{
    "name": "<full name or null>",
    "dob": "<YYYY-MM-DD or null>",
    "country_of_birth": "<country or null>",
    "address": "<address or null>",
    "occupation": "<occupation or null>",
    "marital_status": "<status or null>",
    "accompanying": true | false | null
  }},

  "children": [
    {{
      "name": "<full name>",
      "relationship": "<Son / Daughter>",
      "dob": "<YYYY-MM-DD>",
      "country_of_birth": "<country>",
      "address": "<address>",
      "occupation": "<occupation or Student or N/A>",
      "marital_status": "<status>",
      "accompanying": true | false
    }}
  ],

  "siblings": [
    {{
      "name": "<full name>",
      "relationship": "<Brother / Sister>",
      "dob": "<YYYY-MM-DD>",
      "country_of_birth": "<country>",
      "address": "<address>",
      "occupation": "<occupation>",
      "marital_status": "<status>",
      "accompanying": true | false
    }}
  ],

  "confidence": {{
    "<field_path>": {{
      "level": "high" | "medium" | "low",
      "source": "<filename or document description>"
    }}
  }}
}}
```

IMPORTANT NOTES:
- "children" array: max 4 entries (form limit for Section B)
- "siblings" array: max 7 entries (form limit for Section C)
- If more exist, include only the first N and note the overflow
- Include ALL people found in the documents, even if some fields are null
- "accompanying" means they are traveling WITH the applicant to Canada
"""
