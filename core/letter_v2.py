from __future__ import annotations

import json
import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from core.prompts import (
    SYSTEM_BASE,
    LETTER_STYLE_PROFILE_PROMPT,
    LETTER_WRITER_V2_PROMPT,
    LETTER_QUALITY_CHECK_PROMPT,
)


def get_default_style_profile() -> Dict[str, Any]:
    return {
        "tone": "Formal, transparent, fact-based",
        "structure": {
            "opening": "Identity + purpose + visa type",
            "sections": [
                "Purpose of visit",
                "Travel arrangements",
                "Financial capacity",
                "Strong ties",
                "Travel history",
            ],
            "closing": "Declaration + appreciation + signature",
        },
        "persuasion_principles": [
            "Use verifiable facts",
            "Explain temporary stay logic clearly",
            "Demonstrate financial sufficiency",
        ],
        "detail_level_rules": [
            "Use concrete dates and locations when available",
            "Avoid generic statements",
        ],
        "forbidden_patterns": [
            "vague promises without facts",
            "irrelevant emotional language",
        ],
        "preferred_sentence_style": "Clear, medium-length, professional",
        "preferred_length": "700-1200 words depending on profile depth",
        "quality_bar": "Specific, consistent, and officer-readable",
    }


def _strip_code_fences(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw[:-3]
    return raw.strip()


def _safe_json_loads(text: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    raw = _strip_code_fences(text)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception as exc:
        logging.debug("Failed to parse JSON output: %s", exc)
    return fallback


def extract_style_profile(llm: Any, sample_letter: str) -> Dict[str, Any]:
    prompt = LETTER_STYLE_PROFILE_PROMPT.format(sample_letter=(sample_letter or "").strip())
    response = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
    fallback = get_default_style_profile()
    return _safe_json_loads(response.content or "", fallback)


def assess_letter_quality(llm: Any, summary_profile: str, generated_letter: str) -> Dict[str, Any]:
    prompt = LETTER_QUALITY_CHECK_PROMPT.format(
        summary_profile=(summary_profile or "").strip(),
        generated_letter=(generated_letter or "").strip(),
    )
    response = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
    fallback = {
        "overall_score": 0,
        "is_pass": False,
        "strengths": [],
        "issues": ["Could not parse quality output from model."],
        "missing_or_weak_evidence": [],
        "generic_phrases_found": [],
        "consistency_risks": [],
        "suggested_improvements": ["Re-run quality check."],
    }
    report = _safe_json_loads(response.content or "", fallback)

    try:
        score = int(report.get("overall_score", 0))
    except Exception:
        score = 0
        report["overall_score"] = 0

    if "is_pass" not in report:
        report["is_pass"] = score >= 75

    return report


def generate_letter_v2(
    llm: Any,
    summary_profile: str,
    sample_style_profile: Dict[str, Any],
    legacy_letter_reference: str = "",
    writer_context: str = "",
) -> Dict[str, Any]:
    style_json = json.dumps(sample_style_profile or {}, ensure_ascii=False, indent=2)
    prompt = LETTER_WRITER_V2_PROMPT.format(
        sample_style_profile=style_json,
        summary_profile=(summary_profile or "").strip(),
        legacy_letter_reference=(legacy_letter_reference or "").strip(),
        writer_context=(writer_context or "").strip(),
    )
    response = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
    letter = _strip_code_fences(response.content or "")
    quality_report = assess_letter_quality(llm, summary_profile, letter)
    return {
        "letter": letter,
        "quality_report": quality_report,
    }
