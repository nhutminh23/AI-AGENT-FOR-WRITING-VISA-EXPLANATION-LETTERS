from __future__ import annotations

import base64
import json
import logging
import os
from io import BytesIO
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from core.file_utils import read_docx, read_pdf, read_text_file
from core.prompts import (
    EMPLOYMENT_EXTRACT_PROMPT,
    FILE_EXTRACT_TEXT_PROMPT,
    FILE_OCR_IMAGE_PROMPT,
    FINANCIAL_EXTRACT_PROMPT,
    IDENTITY_EXTRACT_PROMPT,
    ITINERARY_PROMPT,
    LETTER_WRITER_PROMPT,
    PURPOSE_EXTRACT_PROMPT,
    SUMMARY_GROUP_PROMPT,
    SYSTEM_BASE,
    TRAVEL_HISTORY_EXTRACT_PROMPT,
)
from core.state import GraphState


PREFIX_TO_DOMAIN = {
    # English prefixes (primary)
    "OVERVIEW": "overview",
    "PERSONAL": "personal",
    "TRAVEL_HISTORY": "travel_history",
    "EMPLOYMENT": "employment",
    "FINANCIAL": "financial",
    "PURPOSE": "purpose",
    # Vietnamese prefixes (backward compatible)
    "TONG QUAN": "overview",
    "HO SO CA NHAN": "personal",
    "LICH SU DU LICH": "travel_history",
    "CONG VIEC": "employment",
    "TAI CHINH": "financial",
    "MUC DICH CHUYEN DI": "purpose",
}


def detect_domain(filename: str) -> str:
    name = filename.upper()
    for prefix, domain in PREFIX_TO_DOMAIN.items():
        if name.startswith(prefix):
            return domain
    return "unknown"


def _image_to_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _llm_extract_from_text(llm: Any, text: str) -> str:
    prompt = FILE_EXTRACT_TEXT_PROMPT.format(text=text)
    result = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
    return result.content or ""


def _llm_extract_from_image_bytes(llm: Any, image_bytes: bytes) -> str:
    b64 = _image_to_base64(image_bytes)
    message = HumanMessage(
        content=[
            {"type": "text", "text": FILE_OCR_IMAGE_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
    )
    result = llm.invoke([SystemMessage(content=SYSTEM_BASE), message])
    return result.content or ""


def _extract_pdf_with_openai(llm: Any, path: str) -> str:
    text = read_pdf(path)
    if text.strip():
        return _llm_extract_from_text(llm, text)

    try:
        import pdfplumber
        from PIL import Image
    except Exception as e:
        logging.debug("Cannot import pdfplumber/PIL: %s", e)
        return text

    texts: List[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            try:
                page_image = page.to_image().original
                if isinstance(page_image, Image.Image):
                    buffer = BytesIO()
                    page_image.save(buffer, format="PNG")
                    texts.append(_llm_extract_from_image_bytes(llm, buffer.getvalue()))
            except Exception as e:
                logging.debug("OCR page failed: %s", e)
                continue
    return "\n".join(t for t in texts if t)


def _extract_image_with_openai(llm: Any, path: str) -> str:
    from PIL import Image

    try:
        img = Image.open(path)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return _llm_extract_from_image_bytes(llm, buffer.getvalue())
    except Exception as e:
        logging.debug("Image extraction failed for %s: %s", path, e)
        return ""


def extract_text_with_openai(llm: Any, path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in [".txt", ".md"]:
        return read_text_file(path)
    if ext in [".docx", ".doc"]:
        try:
            return read_docx(path)
        except Exception as e:
            logging.debug("Docx read failed for %s: %s", path, e)
            return ""
    if ext == ".pdf":
        return _extract_pdf_with_openai(llm, path)
    if ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
        return _extract_image_with_openai(llm, path)
    return ""


def ingest_files(state: GraphState) -> GraphState:
    input_dir = state["input_dir"]
    llm = state["llm"]
    files: List[Dict[str, str]] = []

    for root, _, filenames in os.walk(input_dir):
        for fname in filenames:
            path = os.path.join(root, fname)
            text = extract_text_with_openai(llm, path)
            files.append(
                {
                    "path": path,
                    "name": fname,
                    "text": text,
                    "domain": detect_domain(fname),
                }
            )

    state["files"] = files
    return state


def classify_files(state: GraphState) -> GraphState:
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for item in state.get("files", []):
        domain = item.get("domain")
        if domain in PREFIX_TO_DOMAIN.values():
            grouped.setdefault(domain, []).append(
                {
                    "name": item.get("name", ""),
                    "path": item.get("path", ""),
                    "text": item.get("text", ""),
                }
            )
    state["grouped"] = grouped
    return state


SUMMARY_DOMAIN_ORDER = [
    ("overview", "OVERVIEW"),
    ("personal", "PERSONAL"),
    ("employment", "EMPLOYMENT"),
    ("financial", "FINANCIAL"),
    ("purpose", "PURPOSE"),
    ("travel_history", "TRAVEL_HISTORY"),
]


def _trim_text_for_summary(text: str, max_chars: int = 12000) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    head = text[:8000]
    tail = text[-3500:]
    return f"{head}\n\n...[TRUNCATED]...\n\n{tail}"


def build_summary_profile(state: GraphState) -> GraphState:
    llm = state["llm"]
    grouped = classify_files(state).get("grouped", {})
    sections: List[str] = []

    for domain, title in SUMMARY_DOMAIN_ORDER:
        files = grouped.get(domain, [])
        if not files:
            sections.append(f"`{title}` có 0 file.")
            continue

        file_list = ", ".join(f.get("name", "") for f in files if f.get("name"))
        compact_files = [
            {
                "file_name": f.get("name", ""),
                "content": _trim_text_for_summary(f.get("text", "")),
            }
            for f in files
        ]
        prompt = SUMMARY_GROUP_PROMPT.format(
            group_title=title,
            file_count=len(files),
            file_list=file_list,
            files_json=json.dumps(compact_files, ensure_ascii=False),
        )
        result = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
        sections.append((result.content or "").strip())

    state["summary_profile"] = "\n\n".join(s for s in sections if s).strip()
    return state


def _safe_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception as e:
        logging.debug("JSON parse failed: %s", e)
        return {"raw_output": text}


# ── Dead code removed during refactor (2026-04-09) ──────────────────
# Removed: domain_agent, _run, _empty_domain_output, _domain_prompt,
#          _stringify_list, _stringify_people_records,
#          _build_summary_profile, _build_visa_relevance
# Reason: Zero callers confirmed via GitNexus impact analysis.
#         Logic superseded by letter_gen V3 and itinerary pipelines.
# Backup: branch backup/before-refactor


def letter_writer(state: GraphState) -> GraphState:
    llm = state["llm"]
    summary_profile = (state.get("summary_profile") or "").strip()
    state["summary_profile"] = summary_profile
    prompt = LETTER_WRITER_PROMPT.format(summary_profile=summary_profile)
    writer_context = (state.get("writer_context") or "").strip()
    if writer_context:
        prompt += (
            "\n\nTHÔNG TIN BỔ SUNG TỪ NGƯỜI DÙNG (ƯU TIÊN SỬ DỤNG NẾU KHÔNG MÂU THUẪN INPUT):\n"
            f"{writer_context}\n"
        )
    result = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
    state["letter_full"] = result.content
    return state


def itinerary_writer(llm: Any, flight_text: str, hotel_text: str, summary_profile: str) -> str:
    """Generate itinerary by asking LLM for JSON data, then filling the HTML template."""
    import re

    prompt = ITINERARY_PROMPT.format(
        flight_text=flight_text,
        hotel_text=hotel_text,
        summary_profile=summary_profile,
    )
    result = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
    raw = (result.content or "").strip()

    # ── Parse JSON from LLM response ──
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON object from the response
        match = re.search(r"\{[\s\S]+\}", raw)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                logging.warning("[ITINERARY] Could not parse JSON from LLM, returning raw HTML")
                return raw
        else:
            logging.warning("[ITINERARY] No JSON found in LLM response, returning raw")
            return raw

    # ── Read template ──
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "itinerary_template.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        logging.error(f"[ITINERARY] Template not found: {template_path}")
        return raw  # fallback

    # ── Build HTML fragments ──

    # Applicants
    applicants = data.get("applicants", [])
    if applicants:
        applicants_html = "<br>".join(
            f'{a.get("name", "")}' + (f' ({a["passport"]})' if a.get("passport") else "")
            for a in applicants
        )
    else:
        applicants_html = "N/A"

    # Itinerary rows
    rows_html = ""
    for day in data.get("days", []):
        date_str = day.get("date", "")
        day_name = day.get("day_name", "")
        city = day.get("city", "")
        hotel_name = day.get("hotel_name", "")
        hotel_address = day.get("hotel_address", "")
        transportation = day.get("transportation", [])
        program = day.get("program", "")

        # Hotel cell
        hotel_cell = f'<span class="hotel-name">{hotel_name}</span>'
        if hotel_address:
            hotel_cell += f'\n                        <span class="hotel-addr">{hotel_address}</span>'

        # Transport cell
        trans_cell = "\n                        ".join(
            f'<span class="trans-info">{t}</span>' for t in transportation
        ) if transportation else '<span class="trans-info">—</span>'

        rows_html += f"""                <tr>
                    <td class="col-date">{date_str}<br><small>{day_name}</small></td>
                    <td class="col-city">{city}</td>
                    <td class="col-hotel">
                        {hotel_cell}
                    </td>
                    <td class="col-trans">
                        {trans_cell}
                    </td>
                    <td class="col-program">{program}</td>
                </tr>
"""

    # Commitments
    commitments = data.get("commitments", [])
    commitments_html = "\n                ".join(f"<li>{c}</li>" for c in commitments) if commitments else ""

    # Signatures
    signers = data.get("signers", [])
    signatures_html = "\n            ".join(
        f'<div class="sig-box">\n                <div class="sig-line">{name}</div>\n            </div>'
        for name in signers
    ) if signers else ""

    # ── Fill template ──
    html = html.replace("{{SUBTITLE}}", data.get("subtitle", "Visa Application"))
    html = html.replace("{{APPLICANTS_HTML}}", applicants_html)
    html = html.replace("{{PURPOSE}}", data.get("purpose", "Tourism"))
    html = html.replace("{{DESTINATION}}", data.get("destination", ""))
    html = html.replace("{{TRAVEL_DATES}}", data.get("travel_dates", ""))
    html = html.replace("{{ITINERARY_ROWS}}", rows_html)
    html = html.replace("{{COMMITMENTS_HTML}}", commitments_html)
    html = html.replace("{{SIGNATURES_HTML}}", signatures_html)

    return html
