"""
Letter generation logic using LangChain + OpenAI.
Reads JSON profile → produces letter text using sample-based prompts.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from letter_gen.prompts import (
    LETTER_GEN_SYSTEM,
    LETTER_NO_REFUSAL_PROMPT,
    LETTER_WITH_REFUSAL_PROMPT,
    REFUSAL_EXPLANATION_PROMPT,
)

logger = logging.getLogger(__name__)

# Fixed model for cost control
WRITER_MODEL = "gpt-5-mini"


def _get_llm(temperature: float = 0.4) -> ChatOpenAI:
    """Create LLM instance locked to gpt-5-mini."""
    return ChatOpenAI(model=WRITER_MODEL, temperature=temperature)


def _call_llm(llm: ChatOpenAI, system: str, user_prompt: str) -> str:
    """Call the LLM with system + user messages and return text."""
    messages = [
        SystemMessage(content=system),
        HumanMessage(content=user_prompt),
    ]
    response = llm.invoke(messages)
    return response.content.strip()


def has_refusal_history(profile: Dict[str, Any]) -> bool:
    """Check if the JSON profile contains refusal history."""
    rh = profile.get("refusal_history")
    if not rh:
        return False
    if isinstance(rh, dict):
        return rh.get("has_refusals", False)
    return False


def generate_letters(
    profile: Dict[str, Any],
    additional_context: str = "",
    group_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate explanation letter(s) from the applicant JSON profile.

    Args:
        profile: Single applicant JSON profile.
        additional_context: Extra instructions for the AI.
        group_info: Optional dict with keys:
          - participants: list of {full_name, passport_no, ...}
          - group_id: string (may be empty)
          - group_label: string (may be empty)

    Returns:
        {
            "explanation_letter": str,           # Always present
            "refusal_letter": str | None,        # Only if has refusal history
            "has_refusal": bool,
            "applicant_name": str,
            "is_group": bool,
            "group_participants": list | None,
        }
    """
    llm = _get_llm()
    json_str = json.dumps(profile, ensure_ascii=False, indent=2)
    has_refusal = has_refusal_history(profile)

    applicant = profile.get("applicant", {})
    applicant_name = applicant.get("full_name", "Applicant")

    # Build group header if applicable
    group_header = ""
    is_group = False
    group_participants = None
    if group_info and group_info.get("participants") and len(group_info["participants"]) >= 2:
        from letter_gen.group_builder import build_group_header_text
        is_group = True
        group_participants = group_info["participants"]
        group_header = build_group_header_text(
            participants=group_participants,
            group_id=group_info.get("group_id", ""),
            group_label=group_info.get("group_label", ""),
        )

    logger.info(
        "Generating letter(s) for %s | has_refusal=%s | is_group=%s | model=%s",
        applicant_name, has_refusal, is_group, WRITER_MODEL,
    )

    # Build additional context with group info
    ctx = additional_context or "None"
    if group_header:
        ctx = (
            f"IMPORTANT — This is a GROUP APPLICATION. "
            f"You MUST include this group header block IMMEDIATELY after the visa type line "
            f"(e.g. after 'Visitor Visa Application (Subclass 600 – Tourist stream)') "
            f"and BEFORE the 'Date:' line:\n\n{group_header}\n\n"
            f"Other additional context: {ctx}"
        )

    # --- Generate main explanation letter ---
    if has_refusal:
        prompt = LETTER_WITH_REFUSAL_PROMPT.format(
            json_profile=json_str,
            additional_context=ctx,
        )
    else:
        prompt = LETTER_NO_REFUSAL_PROMPT.format(
            json_profile=json_str,
            additional_context=ctx,
        )

    explanation_letter = _call_llm(llm, LETTER_GEN_SYSTEM, prompt)
    logger.info("Main letter generated: %d chars", len(explanation_letter))

    # --- Generate separate refusal explanation (if applicable) ---
    refusal_letter = None
    if has_refusal:
        refusal_prompt = REFUSAL_EXPLANATION_PROMPT.format(
            json_profile=json_str,
            additional_context=additional_context or "None",
        )
        refusal_letter = _call_llm(llm, LETTER_GEN_SYSTEM, refusal_prompt)
        logger.info("Refusal letter generated: %d chars", len(refusal_letter))

    return {
        "explanation_letter": explanation_letter,
        "refusal_letter": refusal_letter,
        "has_refusal": has_refusal,
        "applicant_name": applicant_name,
        "is_group": is_group,
        "group_participants": group_participants,
    }
