"""
AI agent for extracting family information from documents.

Uses GPT-5-mini for text extraction and GPT-4o-mini for vision (scanned/image docs).
Returns structured data matching IMM5645E field requirements.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from langchain_openai import ChatOpenAI

from canada_forms.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from canada_forms.reader import read_all_files

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data transformation: AI output → form field keys
# ---------------------------------------------------------------------------

def _transform_to_form_fields(ai_output: dict) -> dict[str, Any]:
    """
    Transform structured AI output to flat dict with semantic field keys
    matching field_mappings.py conventions.
    """
    fields: dict[str, Any] = {}

    # Application type
    app_type = ai_output.get("application_type", "visitor")
    for t in ("visitor", "worker", "student", "other"):
        fields[t] = "1" if t == app_type else "0"

    # Section A: Applicant
    applicant = ai_output.get("applicant", {})
    fields["app_name"] = applicant.get("name")
    fields["app_dob"] = applicant.get("dob")
    fields["app_cob"] = applicant.get("country_of_birth")
    fields["app_address"] = applicant.get("address")
    fields["app_occupation"] = applicant.get("occupation")
    fields["app_marital_status"] = applicant.get("marital_status")

    # Section A: Spouse
    spouse = ai_output.get("spouse", {})
    if spouse and spouse.get("name"):
        fields["spouse_name"] = spouse.get("name")
        fields["spouse_dob"] = spouse.get("dob")
        fields["spouse_cob"] = spouse.get("country_of_birth")
        fields["spouse_address"] = spouse.get("address")
        fields["spouse_occupation"] = spouse.get("occupation")
        fields["spouse_marital_status"] = spouse.get("marital_status")
        accompanying = spouse.get("accompanying")
        if accompanying is True:
            fields["spouse_accompanying_yes"] = True
            fields["spouse_accompanying_no"] = False
        elif accompanying is False:
            fields["spouse_accompanying_yes"] = False
            fields["spouse_accompanying_no"] = True

    # Section A: Mother
    mother = ai_output.get("mother", {})
    if mother and mother.get("name"):
        fields["mother_name"] = mother.get("name")
        fields["mother_dob"] = mother.get("dob")
        fields["mother_cob"] = mother.get("country_of_birth")
        fields["mother_address"] = mother.get("address")
        fields["mother_occupation"] = mother.get("occupation")
        fields["mother_marital_status"] = mother.get("marital_status")
        accompanying = mother.get("accompanying")
        if accompanying is True:
            fields["mother_accompanying_yes"] = True
            fields["mother_accompanying_no"] = False
        elif accompanying is False:
            fields["mother_accompanying_yes"] = False
            fields["mother_accompanying_no"] = True

    # Section A: Father
    father = ai_output.get("father", {})
    if father and father.get("name"):
        fields["father_name"] = father.get("name")
        fields["father_dob"] = father.get("dob")
        fields["father_cob"] = father.get("country_of_birth")
        fields["father_address"] = father.get("address")
        fields["father_occupation"] = father.get("occupation")
        fields["father_marital_status"] = father.get("marital_status")
        accompanying = father.get("accompanying")
        if accompanying is True:
            fields["father_accompanying_yes"] = True
            fields["father_accompanying_no"] = False
        elif accompanying is False:
            fields["father_accompanying_yes"] = False
            fields["father_accompanying_no"] = True

    # Section B: Children (max 4)
    children = ai_output.get("children", [])
    for i, child in enumerate(children[:4]):
        fields[f"child_{i}_name"] = child.get("name")
        fields[f"child_{i}_relationship"] = child.get("relationship")
        fields[f"child_{i}_dob"] = child.get("dob")
        fields[f"child_{i}_cob"] = child.get("country_of_birth")
        fields[f"child_{i}_address"] = child.get("address")
        fields[f"child_{i}_occupation"] = child.get("occupation")
        fields[f"child_{i}_marital_status"] = child.get("marital_status")
        accompanying = child.get("accompanying")
        if accompanying is True:
            fields[f"child_{i}_accompanying_yes"] = True
            fields[f"child_{i}_accompanying_no"] = False
        elif accompanying is False:
            fields[f"child_{i}_accompanying_yes"] = False
            fields[f"child_{i}_accompanying_no"] = True

    # Section C: Siblings (max 7)
    siblings = ai_output.get("siblings", [])
    for i, sibling in enumerate(siblings[:7]):
        fields[f"sibling_{i}_name"] = sibling.get("name")
        fields[f"sibling_{i}_relationship"] = sibling.get("relationship")
        fields[f"sibling_{i}_dob"] = sibling.get("dob")
        fields[f"sibling_{i}_cob"] = sibling.get("country_of_birth")
        fields[f"sibling_{i}_address"] = sibling.get("address")
        fields[f"sibling_{i}_occupation"] = sibling.get("occupation")
        fields[f"sibling_{i}_marital_status"] = sibling.get("marital_status")
        accompanying = sibling.get("accompanying")
        if accompanying is True:
            fields[f"sibling_{i}_accompanying_yes"] = True
            fields[f"sibling_{i}_accompanying_no"] = False
        elif accompanying is False:
            fields[f"sibling_{i}_accompanying_yes"] = False
            fields[f"sibling_{i}_accompanying_no"] = True

    # Filter out None values
    return {k: v for k, v in fields.items() if v is not None}


# ---------------------------------------------------------------------------
# AI extraction
# ---------------------------------------------------------------------------

def _build_messages(file_contents: list[dict]) -> list[dict]:
    """
    Build LLM messages from file contents.
    Text files → user text message.
    Image/scanned files → vision messages with base64 images.
    """
    # Separate text and image content
    text_parts = []
    image_parts = []

    for fc in file_contents:
        if fc["type"] == "text" and fc.get("content"):
            text_parts.append(f"=== FILE: {fc['filename']} ===\n{fc['content']}")
        elif fc.get("images"):
            for img in fc["images"]:
                image_parts.append({
                    "filename": fc["filename"],
                    "base64": img["base64"],
                    "mime_type": img["mime_type"],
                })

    documents_text = "\n\n".join(text_parts) if text_parts else "(No text documents)"

    # Build user prompt
    user_prompt = USER_PROMPT_TEMPLATE.format(documents_content=documents_text)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    if image_parts:
        # Use vision-capable model: combine text + images in one message
        content_blocks = [{"type": "text", "text": user_prompt}]
        for img in image_parts:
            content_blocks.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['mime_type']};base64,{img['base64']}",
                    "detail": "high",
                },
            })
        messages.append({"role": "user", "content": content_blocks})
    else:
        messages.append({"role": "user", "content": user_prompt})

    return messages, bool(image_parts)


def _parse_json_response(raw: str) -> dict:
    """Parse JSON from LLM response, handling code blocks."""
    text = raw.strip()
    # Remove markdown code block wrapper
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)


def extract_family_info(file_paths: list[str]) -> dict:
    """
    Extract family information from uploaded documents.

    Parameters
    ----------
    file_paths : list[str]
        Paths to uploaded document files.

    Returns
    -------
    dict
        {
            "raw": <structured AI output>,
            "form_fields": <flat dict for form filling>,
            "confidence": <confidence scores per field>,
        }
    """
    # 1. Read all files
    file_contents = read_all_files(file_paths)
    if not file_contents:
        raise ValueError("No readable files found")

    # 2. Build messages
    messages, has_images = _build_messages(file_contents)

    # 3. Choose model based on content type
    text_model = os.getenv("TEXT_MODEL", "gpt-5-mini")
    vision_model = os.getenv("VISION_MODEL", "gpt-4o-mini")
    model_name = vision_model if has_images else text_model

    llm = ChatOpenAI(
        model=model_name,
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    logger.info(
        "Extracting family info using model=%s, files=%d (images=%s)",
        model_name, len(file_contents), has_images,
    )

    # 4. Call LLM
    response = llm.invoke(messages)
    raw_text = response.content.strip()

    # 5. Parse response
    ai_output = _parse_json_response(raw_text)

    # 6. Transform to form fields
    form_fields = _transform_to_form_fields(ai_output)

    return {
        "raw": ai_output,
        "form_fields": form_fields,
        "confidence": ai_output.get("confidence", {}),
    }
