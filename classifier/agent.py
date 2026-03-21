from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import unicodedata
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pypdf import PdfReader, PdfWriter

from core.prompts import SYSTEM_BASE


def _sanitize_name(value: str, fallback: str) -> str:
    text = (value or "").strip()
    text = re.sub(r'[\\/:*?"<>|]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback


# ==================== NORMALIZE VIETNAMESE NAME ====================

def normalize_vietnamese_name(name: str) -> str:
    """Convert Vietnamese name to ASCII uppercase with underscores.

    'NGÔ NGÂN HÀ' → 'NGO_NGAN_HA'
    'TRẦN TRUNG ANH - CHỒNG' → 'TRAN_TRUNG_ANH'
    """
    text = (name or "").strip()
    # Remove relationship suffixes like "- CHỒNG", "- VỢ", "- CON"
    text = re.sub(r'\s*[-–]\s*(CHỒNG|VỢ|CON|MẸ|BỐ|CHA|ANH|CHỊ|EM|BÀ|ÔNG).*$', '', text, flags=re.IGNORECASE)
    # Remove Vietnamese diacritics
    nfkd = unicodedata.normalize('NFKD', text)
    ascii_text = ''.join(c for c in nfkd if not unicodedata.combining(c))
    # Replace Đ/đ
    ascii_text = ascii_text.replace('Đ', 'D').replace('đ', 'd')
    # Uppercase, replace spaces with _
    ascii_text = ascii_text.upper().strip()
    ascii_text = re.sub(r'[^A-Z0-9]+', '_', ascii_text)
    ascii_text = ascii_text.strip('_')
    return ascii_text or "UNKNOWN"


# ==================== CLASSIFY DOC TYPE ONLY ====================

def classify_doc_type_only(llm: Any, filename: str, file_path: str, folder_person: str = "") -> Dict[str, Any]:
    """Classify a file to get doc_type_en only (person_name comes from folder).

    Also detects if the file contains multiple document types (needs_split).
    Args:
        folder_person: The person name derived from the parent folder (e.g. "TRAN TRUNG ANH")
    Returns: {"doc_type_en": "PASSPORT", "needs_split": False, "doc_count": 1, "doc_owner": ""}
    """
    ext = os.path.splitext(filename)[1].lower()

    # Image files: use VISION model to actually see the image content
    if ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']:
        result = _classify_image_vision(llm, filename, file_path, folder_person)
        return {
            "doc_type_en": result.get("doc_type_en", "DOCUMENT") if result else "DOCUMENT",
            "doc_owner": result.get("doc_owner", "") if result else "",
            "needs_split": False,
            "doc_count": 1,
        }

    if ext in ['.docx', '.doc']:
        text = _read_docx_text(file_path)
        if not text.strip():
            return {"doc_type_en": "APPLICATION FORM", "doc_owner": "", "needs_split": False, "doc_count": 1}
        result = _classify_single(llm, filename, text, folder_person)
        return {
            "doc_type_en": result.get("doc_type_en", "DOCUMENT") if result else "DOCUMENT",
            "doc_owner": result.get("doc_owner", "") if result else "",
            "needs_split": False,
            "doc_count": 1,
        }

    if ext != '.pdf':
        return {"doc_type_en": "DOCUMENT", "doc_owner": "", "needs_split": False, "doc_count": 1}

    # PDF: extract text → classify + detect multi-doc
    try:
        page_texts = _extract_pdf_pages_text(file_path)
    except Exception as e:
        return {"doc_type_en": "DOCUMENT", "needs_split": False, "doc_count": 1}

    total_pages = len(page_texts)
    non_empty = sum(1 for t in page_texts if len(t.strip()) > 30)

    # Scanned PDF (mostly no text)
    if non_empty < max(1, total_pages * 0.3):
        partial_text = "\n".join(t for t in page_texts if t.strip())
        if partial_text.strip():
            context = f"[Scanned PDF, có một phần text:]\n{partial_text[:3000]}"
        else:
            context = f"[Scanned PDF: {filename}, {total_pages} trang, không có text.]"
        result = _classify_single(llm, filename, context, folder_person)
        return {
            "doc_type_en": result.get("doc_type_en", "DOCUMENT") if result else "DOCUMENT",
            "doc_owner": result.get("doc_owner", "") if result else "",
            "needs_split": False,
            "doc_count": 1,
        }

    # Digital PDF with text → detect multi-doc
    docs = _classify_multi_page_pdf(llm, filename, page_texts)
    if not docs:
        return {"doc_type_en": "DOCUMENT", "needs_split": False, "doc_count": 1}

    if len(docs) == 1:
        return {
            "doc_type_en": docs[0].get("doc_type_en", "DOCUMENT"),
            "needs_split": False,
            "doc_count": 1,
        }

    # Multiple documents detected
    doc_types = [d.get("doc_type_en", "UNKNOWN") for d in docs]
    return {
        "doc_type_en": doc_types[0],  # primary doc type
        "needs_split": True,
        "doc_count": len(docs),
        "doc_types": doc_types,
        "documents": docs,
    }


# Known Vietnamese document type keywords (used to separate person name from doc type in filename)
_FILENAME_DOC_KEYWORDS = [
    "Power_of_Attorney", "Contract", "Passport", "Visa", "Birth_Certificate",
    "Marriage_Certificate", "Identity_Card", "CCCD", "CMND", "License",
    "Account_Statement", "Bank_Statement", "Social_Insurance", "Receipt",
    "Land_Certificate", "Property", "Decision", "Registration_Form",
    "Price_Quotation", "Agreement", "Certificate", "Other", "Driver",
    "Application_Form", "Photo", "Booking", "Itinerary", "Insurance",
    "Notification", "Voucher", "Tax", "Salary", "Transcript",
]


def _extract_name_from_filename(filename: str) -> str:
    """Try to extract person name from structured filename.
    e.g. 'NGUYEN_LE_KIM_NGAN_Contract.pdf' -> 'NGUYEN LE KIM NGAN'
    e.g. 'THACH_NGUYEN_PHONG_Birth_Certificate.pdf' -> 'THACH NGUYEN PHONG'
    Returns empty string if no name found."""
    stem = os.path.splitext(filename)[0]  # remove extension
    # Remove trailing numbers like (1), (2)
    stem = re.sub(r'\s*\(\d+\)\s*$', '', stem).strip()
    # Remove trailing dots and spaces
    stem = stem.rstrip(". ")

    # Non-name prefixes that should be rejected
    _NON_NAME_PREFIXES = ["IMMI", "FORM", "GRANT", "SCAN", "DOC", "FILE", "PAGE", "COPY"]

    def _is_valid_name(name: str) -> bool:
        """Check if extracted name looks like a real person name."""
        words = name.split()
        if len(words) < 2:
            return False
        # Reject if starts with known non-name words
        if words[0] in _NON_NAME_PREFIXES:
            return False
        # All words should be alphabetic (Vietnamese names after removing diacritics)
        return all(re.match(r'^[A-Z]+$', w) for w in words)

    # Try to find where the doc-type part starts
    for kw in _FILENAME_DOC_KEYWORDS:
        idx = stem.lower().find(kw.lower())
        if idx > 0:
            name_part = stem[:idx].rstrip("_- ")
            name = name_part.replace("_", " ").replace("-", " ").strip().upper()
            if _is_valid_name(name):
                return name

    # Also try patterns like IMMI-Grant-Notification_NGUYEN-LE-KIM-NGAN
    # where person name follows a doc keyword
    for kw in _FILENAME_DOC_KEYWORDS:
        pattern = re.compile(re.escape(kw) + r'[_\-\s]+(.+)', re.IGNORECASE)
        m = pattern.search(stem)
        if m:
            name_part = m.group(1).strip()
            name = name_part.replace("_", " ").replace("-", " ").strip().upper()
            if _is_valid_name(name):
                return name
    return ""


def _pick_unique_destination(dest_dir: str, stem: str, ext: str) -> str:
    candidate = os.path.join(dest_dir, f"{stem}{ext}")
    idx = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dest_dir, f"{stem} ({idx}){ext}")
        idx += 1
    return candidate


def _extract_pdf_pages_text(path: str) -> List[str]:
    reader = PdfReader(path)
    pages: List[str] = []
    for page in reader.pages:
        try:
            pages.append((page.extract_text() or "").strip())
        except Exception as e:
            pages.append("")
    return pages


def _read_docx_text(path: str) -> str:
    """Read text from .docx using python-docx (local, no API)."""
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        return ""


# ==================== SINGLE-CALL CLASSIFY PROMPT ====================

def _build_classify_prompt(filename: str, text: str, folder_person: str = "") -> str:
    """Single prompt that identifies doc type + person name in ONE call."""
    content = (text or "").strip()
    # Limit text to save tokens
    if len(content) > 4000:
        content = content[:3000] + "\n...[TRUNCATED]...\n" + content[-800:]

    folder_ctx = ""
    if folder_person:
        folder_ctx = f"\nChủ hồ sơ (tên folder cha): {folder_person}"

    return f"""Bạn là AI phân loại giấy tờ visa. Xác định loại giấy tờ CỤ THỂ và tên chủ sở hữu.

Trả về JSON duy nhất:
{{
  "person_name": "NGUYEN VAN A",
  "doc_type_en": "BANK STATEMENT BIDV T01 2026",
  "doc_owner": ""
}}

Quy tắc doc_type_en - PHẢI CỤ THỂ, KHÔNG CHUNG CHUNG:
- doc_type_en PHẢI bao gồm thông tin phụ để PHÂN BIỆT với file khác cùng loại.
- Viết IN HOA, tiếng Anh.

⚠️ QUY TẮC QUAN TRỌNG - THÊM THÔNG TIN PHỤ:
  1. Sao kê / sổ phụ ngân hàng → thêm TÊN NGÂN HÀNG + KỲ THÁNG/NĂM
     VD: "BANK STATEMENT BIDV T01 2026", "BANK STATEMENT VCB T06 T12 2025"
         "SAVINGS BOOK TECHCOMBANK", "BALANCE CONFIRM ACB 2026"
  2. Hợp đồng → thêm loại hợp đồng
     VD: "LABOR CONTRACT", "LAND SALE CONTRACT", "RENTAL AGREEMENT"
  3. Giấy tờ có thời kỳ → thêm năm/kỳ
     VD: "TAX RETURN 2025", "SOCIAL INSURANCE 2020 2025", "SALARY CERT T12 2025"
  4. Bảo hiểm → thêm tên công ty
     VD: "TRAVEL INSURANCE BAOVIET", "HEALTH INSURANCE PRUDENTIAL"
  5. Giấy tờ cơ bản (PASSPORT, CCCD, BIRTH CERT...) → giữ ngắn gọn, KHÔNG cần thêm
  6. Nếu file là ảnh chân dung → "PHOTO"
  7. HỘ CHIẾU CŨ / HẾT HẠN → "OLD PASSPORT [năm hết hạn]"
     - Nếu thấy NỘI DUNG có "Date of expiry" đã qua, hoặc tên file gợi ý cũ (Passport 1, Passport 2, HC cũ...)
       → doc_type_en = "OLD PASSPORT 2020" (thay 2020 bằng năm hết hạn thực tế)
     - Chỉ hộ chiếu MỚI NHẤT (còn hạn) mới là "PASSPORT"
  8. THẺ HỌC SINH / STUDENT ID → "STUDENT ID CARD"
     - Nếu là thẻ học sinh con → doc_owner = tên đứa con, KHÔNG phải tên cha/mẹ

Quy tắc doc_owner - AI CHỦ SỞ HỮU THỰC SỰ:
- doc_owner: tên THẬT (IN HOA, không dấu) của người sở hữu giấy tờ này
  NẾU người đó KHÁC với chủ hồ sơ (folder).
- Nếu giấy tờ thuộc chính chủ hồ sơ → doc_owner = "" (rỗng)
- VD: Folder "TRAN TRUNG ANH", file "Hộ chiếu mới NTTO.pdf" → đây là passport
  của ai đó tên NTTO (vợ/con/người thân) → doc_owner = tên đầy đủ nếu có trong nội dung,
  nếu không thì dùng viết tắt từ filename: "NTTO"
- VD: Folder "TRAN TRUNG ANH", file "Hộ chiếu chồng.pdf" → đây là passport
  của chính chồng (tức TRAN TRUNG ANH) → doc_owner = ""

⚠️ ĐẶC BIỆT VỀ GiẤY TỜ CỦA CON / VỢ / NGƯỜI THÂN:
- Tên file chứa "con trai", "con gái", "con", "mẹ", "vợ", "bố", "cha" → giấy tờ của người KHÁC
  → doc_owner PHẢI là tên THẬT (tìm trong nội dung), KHÔNG PHẢI tên chủ hồ sơ
- VD: "Hộ chiếu con trai.pdf" → tìm tên con trong nội dung → doc_owner = "NGUYEN DUC TAM"
- VD: "Thẻ học sinh con.pdf" → tìm tên học sinh → doc_owner = tên đứa con
- LUÔN LUÔN cố gắng tìm tên thật trong nội dung thay vì để trống

Quy tắc person_name:
- person_name: tên người sở hữu giấy tờ, viết IN HOA, không dấu.
- TÊN FILE rất quan trọng! Nếu tên file có dạng "NGUYEN_LE_KIM_NGAN_Contract.pdf" thì person_name = "NGUYEN LE KIM NGAN".
- Nếu tên file có dạng "Hộ chiếu của mẹ chồng.pdf" hoặc tên Việt, vẫn cố gắng tìm tên trong NỘI DUNG.
- Nếu nội dung chứa tên người (trong phần chủ sở hữu, bên ủy quyền, bên được ủy quyền, v.v.), PHẢI dùng tên đó.
- CHỈ dùng "UNKNOWN PERSON" khi THẬT SỰ không thể tìm ra tên từ cả tên file lẫn nội dung.

- Chỉ trả JSON, không giải thích.
{folder_ctx}
Tên file: {filename}
Nội dung:
{content}"""


def _build_classify_prompt_multi(filename: str, page_texts: List[str]) -> str:
    """Single prompt for multi-page PDF: detect ALL docs + classify in ONE call."""
    snippets: List[str] = []
    for idx, txt in enumerate(page_texts, 1):
        short = txt
        if len(short) > 600:
            short = short[:500] + "\n...[CUT]...\n" + short[-80:]
        if not short.strip():
            short = "(trang trống hoặc scan)"
        snippets.append(f"[TRANG {idx}]\n{short}")

    pages_text = "\n\n".join(snippets)
    # Limit total size
    if len(pages_text) > 15000:
        pages_text = pages_text[:12000] + "\n...[TRUNCATED]..."

    return f"""Bạn là AI phân loại giấy tờ visa trong 1 file PDF nhiều trang.

Nhiệm vụ: Xác định file có bao nhiêu giấy tờ KHÁC NHAU, mỗi giấy tờ thuộc ai.

Trả về JSON duy nhất:
{{
  "documents": [
    {{
      "person_name": "NGUYEN VAN A",
      "doc_type_en": "PASSPORT",
      "start_page": 1,
      "end_page": 2
    }}
  ]
}}

Quy tắc:
- Nếu TẤT CẢ trang cùng 1 loại + cùng 1 người → trả 1 mục duy nhất.
- person_name: IN HOA, không dấu. Không rõ thì "UNKNOWN PERSON".
- doc_type_en: tiếng Anh, IN HOA, ngắn gọn (PASSPORT, BANK STATEMENT, LABOR CONTRACT, POWER OF ATTORNEY, ...).
- Hộ chiếu CŨ / hết hạn → "OLD PASSPORT [năm hết hạn]" (VD: "OLD PASSPORT 2020")
  Chỉ hộ chiếu MỚI NHẤT (còn hạn) mới là "PASSPORT"
- Không overlap trang. Thứ tự tăng dần.
- Chỉ trả JSON, không giải thích.

RẤT QUAN TRỌNG VỀ person_name:
- TÊN FILE rất quan trọng! Nếu tên file có dạng "NGUYEN_LE_KIM_NGAN_Contract.pdf" thì person_name = "NGUYEN LE KIM NGAN".
- Ưu tiên tìm tên TRONG NỘI DUNG trang. Nếu không rõ, dùng tên từ tên file.
- Mỗi giấy tờ có thể thuộc NGƯỜI KHÁC NHAU → person_name phải là tên THẬT của người sở hữu giấy tờ đó.
- VD: File "Kết hôn và khai sinh con.pdf" có thể chứa 1 giấy kết hôn (của bố mẹ) + 2 giấy khai sinh (của 2 đứa con khác nhau).
- CHỈ dùng "UNKNOWN PERSON" khi THẬT SỰ không thể xác định từ cả tên file lẫn nội dung.

Tên file: {filename}
{pages_text}"""


def _classify_image_vision(llm: Any, filename: str, file_path: str, folder_person: str = "") -> Optional[Dict[str, str]]:
    """Classify an image file using vision model — AI actually SEES the image."""
    try:
        with open(file_path, 'rb') as f:
            img_bytes = f.read()
        # Determine MIME type
        ext = os.path.splitext(filename)[1].lower()
        mime_map = {'.jpg': 'jpeg', '.jpeg': 'jpeg', '.png': 'png', '.bmp': 'bmp', '.tiff': 'tiff', '.tif': 'tiff', '.webp': 'webp'}
        mime_type = mime_map.get(ext, 'jpeg')
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        data_url = f"data:image/{mime_type};base64,{b64}"

        # Build prompt
        prompt_text = _build_classify_prompt(filename, "[Hình ảnh được đính kèm bên dưới — hãy NHÌN vào hình để phân loại]", folder_person)

        # Send as multimodal message (text + image)
        message_content = [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
        result = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=message_content)])
        raw = result.content or ""
        # Extract JSON from response
        match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            parsed = json.loads(raw)
        person = _sanitize_name(str(parsed.get("person_name", "")), "UNKNOWN PERSON")
        doc_type = _sanitize_name(str(parsed.get("doc_type_en", "")), "DOCUMENT")
        doc_owner = (parsed.get("doc_owner") or "").strip()
        # Fallback: if AI returned UNKNOWN PERSON, try extracting from filename
        if person == "UNKNOWN PERSON":
            fname_name = _extract_name_from_filename(filename)
            if fname_name:
                person = fname_name
        return {
            "person_name": person,
            "doc_type_en": doc_type,
            "doc_owner": doc_owner,
        }
    except Exception as vision_err:
        # If quota exhausted, re-raise so _classify_one can trigger early stop
        err_msg = str(vision_err).lower()
        if 'insufficient_quota' in err_msg or '429' in err_msg or 'rate limit' in err_msg:
            raise
        # Fallback to text-only classify if image reading fails (non-quota errors only)
        return _classify_single(llm, filename, f"[Image file: {filename}]", folder_person)


def _classify_single(llm: Any, filename: str, text: str, folder_person: str = "") -> Optional[Dict[str, str]]:
    """Classify a single-doc file with 1 API call."""
    prompt = _build_classify_prompt(filename, text, folder_person)
    try:
        result = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
        raw = result.content or ""
        # Extract JSON from response
        match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            parsed = json.loads(raw)
        person = _sanitize_name(str(parsed.get("person_name", "")), "UNKNOWN PERSON")
        doc_type = _sanitize_name(str(parsed.get("doc_type_en", "")), "DOCUMENT")
        doc_owner = (parsed.get("doc_owner") or "").strip()
        # Fallback: if AI returned UNKNOWN PERSON, try extracting from filename
        if person == "UNKNOWN PERSON":
            fname_name = _extract_name_from_filename(filename)
            if fname_name:
                person = fname_name
        return {
            "person_name": person,
            "doc_type_en": doc_type,
            "doc_owner": doc_owner,
        }
    except Exception as e:
        # If quota exhausted, re-raise so _classify_one can trigger early stop
        err_msg = str(e).lower()
        if 'insufficient_quota' in err_msg or '429' in err_msg or 'rate limit' in err_msg:
            raise
        return None


def _classify_multi_page_pdf(llm: Any, filename: str, page_texts: List[str]) -> List[Dict[str, Any]]:
    """Classify a multi-page PDF: detect + classify ALL documents in 1 API call."""
    prompt = _build_classify_prompt_multi(filename, page_texts)
    try:
        result = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
        raw = result.content or ""
        # Extract JSON from response
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            parsed = json.loads(raw)
    except Exception as e:
        err_msg = str(e).lower()
        if 'insufficient_quota' in err_msg or '429' in err_msg or 'rate limit' in err_msg:
            raise
        return []

    docs = parsed.get("documents")
    if not isinstance(docs, list):
        return []

    max_page = len(page_texts)
    output: List[Dict[str, Any]] = []
    fname_name = _extract_name_from_filename(filename)
    for item in docs:
        if not isinstance(item, dict):
            continue
        try:
            s = int(item.get("start_page"))
            e = int(item.get("end_page"))
        except Exception as e:
            logging.debug("Skipped: %s", e)
            continue
        s = max(1, min(max_page, s))
        e = max(1, min(max_page, e))
        if s > e:
            s, e = e, s
        person = _sanitize_name(str(item.get("person_name", "")), "UNKNOWN PERSON")
        # Fallback: if AI returned UNKNOWN PERSON, try filename
        if person == "UNKNOWN PERSON" and fname_name:
            person = fname_name
        output.append({
            "person_name": person,
            "doc_type_en": _sanitize_name(str(item.get("doc_type_en", "")), "DOCUMENT"),
            "start_page": s,
            "end_page": e,
        })
    output.sort(key=lambda x: (x["start_page"], x["end_page"]))
    return output


# ==================== DOMAIN PREFIX MAPPING ====================

_DOMAIN_KEYWORDS = {
    "PERSONAL": [
        "PASSPORT", "IDENTITY CARD", "CITIZEN", "CCCD", "CMND",
        "BIRTH CERTIFICATE", "MARRIAGE", "HOUSEHOLD", "FAMILY",
        "PHOTO", "APPLICATION FORM", "FORM KHAI", "DRIVER",
    ],
    "FINANCIAL": [
        "BANK", "STATEMENT", "BALANCE", "SAVINGS", "DEPOSIT",
        "TAX", "INCOME", "SALARY", "PAYSLIP", "PROPERTY",
        "LAND", "STOCK", "INVESTMENT", "PRICE QUOTATION",
        "RECEIPT", "VOUCHER", "ACCOUNT",
    ],
    "EMPLOYMENT": [
        "LABOR CONTRACT", "EMPLOYMENT", "BUSINESS LICENSE",
        "COMPANY", "LEAVE", "SOCIAL INSURANCE", "WORK PERMIT",
        "BUSINESS REGISTRATION", "JOB", "POSITION",
    ],
    "PURPOSE": [
        "HOTEL", "BOOKING", "FLIGHT", "ITINERARY", "TRAVEL PLAN",
        "INVITATION", "ENROLLMENT", "ADMISSION", "SPONSORSHIP",
        "TOUR", "INSURANCE",
    ],
    "TRAVEL_HISTORY": [
        "VISA", "GRANT", "IMMI", "TRAVEL HISTORY", "ENTRY", "EXIT",
        "STAMP", "IMMIGRATION",
    ],
    "LEGAL": [
        "CONTRACT", "AGREEMENT", "POWER OF ATTORNEY", "DECISION",
        "REGISTRATION FORM", "NOTARY", "AUTHORIZATION",
    ],
    "OVERVIEW": [
        "OVERVIEW", "SUMMARY", "COVER LETTER", "EXPLANATION",
    ],
}


def _resolve_domain_prefix(doc_type_en: str) -> str:
    upper = doc_type_en.upper()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in upper:
                return domain
    # Default: if truly unrecognized, use OTHER
    if upper in ["UNKNOWN", "DOCUMENT", "OTHER", "UNKNOWN DOCUMENT"]:
        return "OTHER"
    return "OTHER"


def _copy_to_output(
    src_path: str, output_dir: str, person_name: str, doc_type_en: str
) -> str:
    person_dir = os.path.join(output_dir, _sanitize_name(person_name, "UNKNOWN PERSON"))
    os.makedirs(person_dir, exist_ok=True)
    ext = os.path.splitext(src_path)[1] or ""
    domain = _resolve_domain_prefix(doc_type_en)
    doc = _sanitize_name(doc_type_en, "DOCUMENT")
    pname = _sanitize_name(person_name, "UNKNOWN").replace(" ", "_")
    # Format: DOMAIN_PersonName_DocType.ext
    stem = f"{domain}_{pname}_{doc}"
    target = _pick_unique_destination(person_dir, stem, ext)
    shutil.copy2(src_path, target)
    return target


def _split_and_copy_pdf(
    src_path: str,
    output_dir: str,
    docs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    reader = PdfReader(src_path)
    total = len(reader.pages)
    results: List[Dict[str, Any]] = []
    for item in docs:
        s = int(item["start_page"])
        e = int(item["end_page"])
        if s < 1 or e > total or s > e:
            continue
        writer = PdfWriter()
        for i in range(s - 1, e):
            writer.add_page(reader.pages[i])
        person_dir = os.path.join(output_dir, _sanitize_name(item["person_name"], "UNKNOWN PERSON"))
        os.makedirs(person_dir, exist_ok=True)
        domain = _resolve_domain_prefix(item["doc_type_en"])
        doc = _sanitize_name(item["doc_type_en"], "DOCUMENT")
        pname = _sanitize_name(item["person_name"], "UNKNOWN").replace(" ", "_")
        # Format: DOMAIN_PersonName_DocType.pdf
        stem = f"{domain}_{pname}_{doc}"
        out_path = _pick_unique_destination(person_dir, stem, ".pdf")
        with open(out_path, "wb") as f:
            writer.write(f)
        results.append({
            "filename": os.path.basename(src_path),
            "pages": f"{s}-{e}",
            "person_name": item["person_name"],
            "doc_type_en": item["doc_type_en"],
            "to": os.path.relpath(out_path, output_dir).replace("\\", "/"),
        })
    return results


# ==================== MAIN PIPELINE ====================

def classify_files_in_folder(
    input_dir: str,
    output_dir: str,
    model: str = "gpt-4o-mini",
    max_workers: int = 8,
) -> Dict[str, Any]:
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f"Folder not found: {input_dir}")
    os.makedirs(output_dir, exist_ok=True)

    llm = ChatOpenAI(model=model, temperature=0)
    files: List[str] = []
    for root, _, names in os.walk(input_dir):
        for name in sorted(names):
            files.append(os.path.join(root, name))

    copied: List[Dict[str, Any]] = []
    skipped: List[str] = []
    split_logs: List[Dict[str, Any]] = []
    person_counts: Dict[str, int] = {}

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _process_single_file(src_path: str) -> Optional[Dict[str, Any]]:
        """Process a single file with minimum API calls."""
        filename = os.path.basename(src_path)
        ext = os.path.splitext(filename)[1].lower()

        # -------- Non-PDF: extract text locally, then 1 API call --------
        if ext in [".docx", ".doc"]:
            text = _read_docx_text(src_path)
            if not text.strip():
                # Try to get name from filename first, then fallback
                fname_name = _extract_name_from_filename(filename)
                return {"type": "copied", "filename": filename,
                        "person_name": fname_name or "UNKNOWN PERSON",
                        "doc_type_en": "APPLICATION FORM"}
            identified = _classify_single(llm, filename, text)
            if not identified:
                return {"type": "skipped", "filename": filename}
            return {"type": "copied", "filename": filename, **identified}

        if ext in [".txt", ".md"]:
            try:
                with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except Exception as e:
                text = ""
            if not text.strip():
                return {"type": "skipped", "filename": filename}
            identified = _classify_single(llm, filename, text)
            if not identified:
                return {"type": "skipped", "filename": filename}
            return {"type": "copied", "filename": filename, **identified}

        if ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
            # Images: classify from filename only (1 call, no vision needed here)
            identified = _classify_single(llm, filename, f"[Image file: {filename}]")
            if not identified:
                return {"type": "skipped", "filename": filename}
            return {"type": "copied", "filename": filename, **identified}

        if ext != ".pdf":
            return {"type": "skipped", "filename": filename}

        # -------- PDF: extract text locally with pypdf → 1 API call --------
        try:
            page_texts = _extract_pdf_pages_text(src_path)
        except Exception as e:
            return {"type": "skipped", "filename": filename}

        total_pages = len(page_texts)
        non_empty = sum(1 for t in page_texts if len(t.strip()) > 30)

        # Scanned PDF (mostly no text) → still try to use any available text
        if non_empty < max(1, total_pages * 0.3):
            # Collect whatever partial text exists
            partial_text = "\n".join(t for t in page_texts if t.strip())
            if partial_text.strip():
                context = f"[Scanned PDF, nhưng có một phần text:]\n{partial_text[:3000]}"
            else:
                context = f"[Scanned PDF: {filename}, {total_pages} trang, không có text. Hãy phân loại từ tên file.]"
            identified = _classify_single(llm, filename, context)
            if not identified:
                return {"type": "skipped", "filename": filename}
            return {"type": "copied", "filename": filename, **identified}

        # Digital PDF with text → 1 API call to detect + classify
        docs = _classify_multi_page_pdf(llm, filename, page_texts)

        if not docs:
            return {"type": "skipped", "filename": filename}

        # Single document in PDF → just rename
        if len(docs) == 1:
            return {
                "type": "copied",
                "filename": filename,
                "person_name": docs[0]["person_name"],
                "doc_type_en": docs[0]["doc_type_en"],
            }

        # Multiple documents → split PDF
        split_results = _split_and_copy_pdf(src_path, output_dir, docs)
        if split_results:
            return {"type": "split", "filename": filename, "split_results": split_results}

        return {"type": "skipped", "filename": filename}

    # Process files in parallel (8 workers)
    future_to_src = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for src_path in files:
            future = executor.submit(_process_single_file, src_path)
            future_to_src[future] = src_path

        for future in as_completed(future_to_src):
            src_path = future_to_src[future]
            try:
                result = future.result()
            except Exception as e:
                skipped.append(os.path.basename(src_path))
                continue
            if result is None:
                continue
            if result["type"] == "skipped":
                skipped.append(result["filename"])
            elif result["type"] == "split":
                sr = result["split_results"]
                split_logs.append({
                    "source_file": result["filename"],
                    "detected_documents": len(sr),
                    "outputs": sr,
                })
                for item in sr:
                    person_counts[item["person_name"]] = person_counts.get(item["person_name"], 0) + 1
                    copied.append({
                        "source": result["filename"],
                        "person_name": item["person_name"],
                        "doc_type_en": item["doc_type_en"],
                        "to": item["to"],
                    })
            elif result["type"] == "copied":
                pname = result.get("person_name", "UNKNOWN PERSON")
                dtype = result.get("doc_type_en", "DOCUMENT")
                person_counts[pname] = person_counts.get(pname, 0) + 1
                try:
                    out_path = _copy_to_output(src_path, output_dir, pname, dtype)
                    copied.append({
                        "source": result["filename"],
                        "person_name": pname,
                        "doc_type_en": dtype,
                        "to": os.path.relpath(out_path, output_dir).replace("\\", "/"),
                    })
                except Exception as e:
                    skipped.append(result["filename"])

    return {
        "input_dir": input_dir,
        "output_dir": output_dir,
        "split_logs": split_logs,
        "copied_count": len(copied),
        "skipped_count": len(skipped),
        "person_counts": person_counts,
        "copied": copied,
        "skipped": skipped,
    }
