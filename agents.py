from __future__ import annotations

import base64
import json
import os
from io import BytesIO
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from file_utils import read_docx, read_pdf, read_text_file
from prompts import (
    EMPLOYMENT_EXTRACT_PROMPT,
    FILE_EXTRACT_TEXT_PROMPT,
    FILE_OCR_IMAGE_PROMPT,
    FINANCIAL_EXTRACT_PROMPT,
    IDENTITY_EXTRACT_PROMPT,
    ITINERARY_PROMPT,
    PURPOSE_EXTRACT_PROMPT,
    RISK_EXPLANATION_PROMPT,
    SYSTEM_BASE,
    LETTER_WRITER_PROMPT,
    TRAVEL_HISTORY_EXTRACT_PROMPT,
)
from state import GraphState


PREFIX_TO_DOMAIN = {
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
    except Exception:
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
            except Exception:
                continue
    return "\n".join(t for t in texts if t)


def _extract_image_with_openai(llm: Any, path: str) -> str:
    from PIL import Image

    try:
        img = Image.open(path)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return _llm_extract_from_image_bytes(llm, buffer.getvalue())
    except Exception:
        return ""


def extract_text_with_openai(llm: Any, path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in [".txt", ".md"]:
        return read_text_file(path)
    if ext in [".docx", ".doc"]:
        try:
            return read_docx(path)
        except Exception:
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
    grouped: Dict[str, List[str]] = {}
    for item in state.get("files", []):
        if item["domain"] in PREFIX_TO_DOMAIN.values():
            grouped.setdefault(item["domain"], []).append(item["text"])
    state["grouped"] = grouped
    return state


def _safe_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return {"raw_output": text}


def domain_agent(domain: str):
    def _run(state: GraphState) -> GraphState:
        llm = state["llm"]
        texts = state.get("grouped", {}).get(domain, [])
        if not texts:
            state.setdefault("extracted", {})[domain] = _empty_domain_output(domain)
            return state

        content = "\n\n".join(t for t in texts if t)
        prompt = _domain_prompt(domain, content)
        result = llm.invoke(
            [SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)]
        )
        parsed = _safe_json_loads(result.content)
        state.setdefault("extracted", {})[domain] = parsed
        return state

    return _run


def risk_explanation_finder(state: GraphState) -> GraphState:
    llm = state["llm"]
    extracted = state.get("extracted", {})
    inputs = {
        "Identity": extracted.get("personal", {}),
        "TravelHistory": extracted.get("travel_history", {}),
        "Employment": extracted.get("employment", {}),
        "Financial": extracted.get("financial", {}),
        "PurposeOfTravel": extracted.get("purpose", {}),
    }
    prompt = RISK_EXPLANATION_PROMPT.format(
        inputs=json.dumps(inputs, ensure_ascii=False)
    )
    result = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
    parsed = _safe_json_loads(result.content)
    state["risk_points"] = parsed.get("risk_points", [])
    return state


def _empty_domain_output(domain: str) -> Dict[str, Any]:
    if domain == "personal":
        return {
            "full_name": "",
            "date_of_birth": "",
            "place_of_birth": "",
            "nationality": "",
            "passport_number": "",
            "passport_issue_date": "",
            "passport_expiry_date": "",
            "current_address": "",
            "marital_status": "",
            "spouse_name": "",
            "family_members_in_vn": [],
            "contact_phone": "",
            "contact_email": "",
            "note": "",
        }
    if domain == "travel_history":
        return {
            "previous_countries_visited": [],
            "previous_visa_types": [],
            "last_travel_year": "",
            "travel_frequency": "",
            "overstay_history": "",
            "old_passport_available": "",
            "note": "",
        }
    if domain == "employment":
        return {
            "employment_type": "",
            "company_name": "",
            "company_address": "",
            "job_title": "",
            "employment_start_date": "",
            "employment_status": "",
            "monthly_income": "",
            "approved_leave_start": "",
            "approved_leave_end": "",
            "return_to_work_confirmation": "",
            "business_name": "",
            "business_registration_year": "",
            "business_field": "",
            "role_in_business": "",
            "monthly_or_yearly_income": "",
            "tax_compliance_status": "",
            "business_operation_status": "",
            "main_income_sources": [],
            "average_monthly_income": "",
            "income_stability_level": "",
            "personal_explanation_present": "",
            "note": "",
        }
    if domain == "financial":
        return {
            "bank_statement_months": "",
            "average_monthly_balance": "",
            "current_account_balance": "",
            "savings_balance": "",
            "asset_list": [],
            "total_estimated_assets_value": "",
            "financial_sponsor": "",
            "sponsor_relationship": "",
            "note": "",
        }
    if domain == "purpose":
        return {
            "travel_purpose": "",
            "destination_country": "",
            "cities_to_visit": [],
            "travel_start_date": "",
            "travel_end_date": "",
            "total_trip_duration": "",
            "daily_itinerary_available": "",
            "flight_booking_status": "",
            "hotel_booking_status": "",
            "travel_insurance_status": "",
            "accompanying_persons": [],
            "relationship_with_companion": "",
            "note": "",
        }
    return {}


def _domain_prompt(domain: str, content: str) -> str:
    if domain == "personal":
        return IDENTITY_EXTRACT_PROMPT.format(text=content)
    if domain == "travel_history":
        return TRAVEL_HISTORY_EXTRACT_PROMPT.format(text=content)
    if domain == "employment":
        return EMPLOYMENT_EXTRACT_PROMPT.format(text=content)
    if domain == "financial":
        return FINANCIAL_EXTRACT_PROMPT.format(text=content)
    if domain == "purpose":
        return PURPOSE_EXTRACT_PROMPT.format(text=content)
    return IDENTITY_EXTRACT_PROMPT.format(text=content)


def _build_summary_profile(extracted: Dict[str, Any]) -> str:
    personal = extracted.get("personal", {})
    travel = extracted.get("travel_history", {})
    employment = extracted.get("employment", {})
    financial = extracted.get("financial", {})
    purpose = extracted.get("purpose", {})

    lines: List[str] = []
    def _stringify_list(values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        result: List[str] = []
        for item in values:
            if item is None:
                continue
            if isinstance(item, str):
                result.append(item)
            else:
                result.append(json.dumps(item, ensure_ascii=False))
        return result

    if personal:
        lines.append("Thông tin định danh:")
        for key in [
            "full_name",
            "date_of_birth",
            "nationality",
            "passport_number",
            "passport_issue_date",
            "passport_expiry_date",
            "current_address",
            "marital_status",
            "spouse_name",
            "contact_phone",
            "contact_email",
        ]:
            value = personal.get(key, "")
            if value:
                lines.append(f"- {key}: {value}")
        family = _stringify_list(personal.get("family_members_in_vn", []))
        if family:
            lines.append(f"- family_members_in_vn: {', '.join(family)}")
        note = personal.get("note", "")
        if note:
            lines.append(f"- note: {note}")

    if employment:
        lines.append("Công việc & thu nhập:")
        for key in [
            "employment_type",
            "company_name",
            "company_address",
            "job_title",
            "employment_start_date",
            "employment_status",
            "monthly_income",
            "approved_leave_start",
            "approved_leave_end",
            "return_to_work_confirmation",
            "business_name",
            "business_registration_year",
            "business_field",
            "role_in_business",
            "monthly_or_yearly_income",
            "tax_compliance_status",
            "business_operation_status",
            "average_monthly_income",
            "income_stability_level",
            "personal_explanation_present",
        ]:
            value = employment.get(key, "")
            if value:
                lines.append(f"- {key}: {value}")
        sources = _stringify_list(employment.get("main_income_sources", []))
        if sources:
            lines.append(f"- main_income_sources: {', '.join(sources)}")
        note = employment.get("note", "")
        if note:
            lines.append(f"- note: {note}")

    if financial:
        lines.append("Tài chính & tài sản:")
        for key in [
            "bank_statement_months",
            "average_monthly_balance",
            "current_account_balance",
            "savings_balance",
            "total_estimated_assets_value",
            "financial_sponsor",
            "sponsor_relationship",
        ]:
            value = financial.get(key, "")
            if value:
                lines.append(f"- {key}: {value}")
        assets = _stringify_list(financial.get("asset_list", []))
        if assets:
            lines.append(f"- asset_list: {', '.join(assets)}")
        note = financial.get("note", "")
        if note:
            lines.append(f"- note: {note}")

    if travel:
        lines.append("Lịch sử du lịch & visa:")
        for key in [
            "last_travel_year",
            "travel_frequency",
            "overstay_history",
            "old_passport_available",
        ]:
            value = travel.get(key, "")
            if value:
                lines.append(f"- {key}: {value}")
        countries = _stringify_list(travel.get("previous_countries_visited", []))
        if countries:
            lines.append(f"- previous_countries_visited: {', '.join(countries)}")
        visas = _stringify_list(travel.get("previous_visa_types", []))
        if visas:
            lines.append(f"- previous_visa_types: {', '.join(visas)}")
        note = travel.get("note", "")
        if note:
            lines.append(f"- note: {note}")

    if purpose:
        lines.append("Mục đích chuyến đi:")
        for key in [
            "travel_purpose",
            "destination_country",
            "travel_start_date",
            "travel_end_date",
            "total_trip_duration",
            "daily_itinerary_available",
            "flight_booking_status",
            "hotel_booking_status",
            "travel_insurance_status",
            "relationship_with_companion",
        ]:
            value = purpose.get(key, "")
            if value:
                lines.append(f"- {key}: {value}")
        cities = _stringify_list(purpose.get("cities_to_visit", []))
        if cities:
            lines.append(f"- cities_to_visit: {', '.join(cities)}")
        companions = _stringify_list(purpose.get("accompanying_persons", []))
        if companions:
            lines.append(f"- accompanying_persons: {', '.join(companions)}")
        note = purpose.get("note", "")
        if note:
            lines.append(f"- note: {note}")

    return "\n".join(lines).strip()


def _build_visa_relevance(extracted: Dict[str, Any]) -> List[str]:
    personal = extracted.get("personal", {})
    travel = extracted.get("travel_history", {})
    employment = extracted.get("employment", {})
    financial = extracted.get("financial", {})
    purpose = extracted.get("purpose", {})

    items: List[str] = []
    if personal:
        parts = []
        if personal.get("full_name"):
            parts.append(f"full_name={personal.get('full_name')}")
        if personal.get("passport_number"):
            parts.append(f"passport_number={personal.get('passport_number')}")
        if personal.get("nationality"):
            parts.append(f"nationality={personal.get('nationality')}")
        if parts:
            items.append("Identity: " + ", ".join(parts))

    if employment:
        parts = []
        if employment.get("employment_type"):
            parts.append(f"employment_type={employment.get('employment_type')}")
        if employment.get("company_name"):
            parts.append(f"company_name={employment.get('company_name')}")
        if employment.get("business_name"):
            parts.append(f"business_name={employment.get('business_name')}")
        if employment.get("job_title"):
            parts.append(f"job_title={employment.get('job_title')}")
        if parts:
            items.append("Employment: " + ", ".join(parts))

    def _stringify_list(values: Any) -> List[str]:
        if not isinstance(values, list):
            return []
        result: List[str] = []
        for item in values:
            if item is None:
                continue
            if isinstance(item, str):
                result.append(item)
            else:
                result.append(json.dumps(item, ensure_ascii=False))
        return result

    if financial:
        parts = []
        if financial.get("current_account_balance"):
            parts.append(f"current_account_balance={financial.get('current_account_balance')}")
        if financial.get("savings_balance"):
            parts.append(f"savings_balance={financial.get('savings_balance')}")
        assets = _stringify_list(financial.get("asset_list", []))
        if assets:
            parts.append(f"asset_list={', '.join(assets)}")
        if parts:
            items.append("Financial: " + ", ".join(parts))

    if travel:
        parts = []
        countries = _stringify_list(travel.get("previous_countries_visited", []))
        if countries:
            parts.append(f"previous_countries_visited={', '.join(countries)}")
        if travel.get("overstay_history"):
            parts.append(f"overstay_history={travel.get('overstay_history')}")
        if parts:
            items.append("TravelHistory: " + ", ".join(parts))

    if purpose:
        parts = []
        if purpose.get("travel_purpose"):
            parts.append(f"travel_purpose={purpose.get('travel_purpose')}")
        if purpose.get("destination_country"):
            parts.append(f"destination_country={purpose.get('destination_country')}")
        if purpose.get("travel_start_date"):
            parts.append(f"travel_start_date={purpose.get('travel_start_date')}")
        if purpose.get("travel_end_date"):
            parts.append(f"travel_end_date={purpose.get('travel_end_date')}")
        if parts:
            items.append("PurposeOfTravel: " + ", ".join(parts))

    return items


def letter_writer(state: GraphState) -> GraphState:
    llm = state["llm"]
    extracted = state.get("extracted", {})
    summary_profile = _build_summary_profile(extracted)
    state["summary_profile"] = summary_profile
    visa_relevance: List[str] = _build_visa_relevance(extracted)

    def _format_risk_report(risk_points: Any) -> str:
        if not isinstance(risk_points, list) or len(risk_points) == 0:
            return "Chưa có dữ liệu rủi ro (risk_points trống)."

        lines: List[str] = []
        lines.append("BÁO CÁO RỦI RO (ĐIỂM CẦN GIẢI TRÌNH)")
        lines.append("(Tự động tạo từ bước 'Điểm cần giải trình')")
        lines.append("")

        for i, item in enumerate(risk_points, 1):
            if not isinstance(item, dict):
                continue
            risk_type = (item.get("risk_type") or "").strip()
            severity = (item.get("severity") or "").strip()
            description = (item.get("description") or "").strip()
            direction = (item.get("suggested_explanation_direction") or "").strip()

            title_parts = [p for p in [risk_type, severity] if p]
            title = " | ".join(title_parts) if title_parts else f"Risk #{i}"
            lines.append(f"{i}. {title}")
            if description:
                lines.append(f"   - Mô tả: {description}")
            if direction:
                lines.append(f"   - Hướng giải trình gợi ý: {direction}")
            lines.append("")

        return "\n".join(lines).strip()

    state["risk_report"] = _format_risk_report(state.get("risk_points", []))

    prompt = LETTER_WRITER_PROMPT.format(
        summary_profile=summary_profile,
        visa_relevance=visa_relevance,
    )
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
    prompt = ITINERARY_PROMPT.format(
        flight_text=flight_text,
        hotel_text=hotel_text,
        summary_profile=summary_profile,
    )
    result = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
    return result.content or ""
