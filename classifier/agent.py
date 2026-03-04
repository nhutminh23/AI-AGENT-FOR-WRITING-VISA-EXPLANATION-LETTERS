from __future__ import annotations

import json
import os
import re
import shutil
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
        except Exception:
            pages.append("")
    return pages


def _read_docx_text(path: str) -> str:
    """Read text from .docx using python-docx (local, no API)."""
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return ""


# ==================== SINGLE-CALL CLASSIFY PROMPT ====================

def _build_classify_prompt(filename: str, text: str) -> str:
    """Single prompt that identifies doc type + person name in ONE call."""
    content = (text or "").strip()
    # Limit text to save tokens
    if len(content) > 4000:
        content = content[:3000] + "\n...[TRUNCATED]...\n" + content[-800:]

    return f"""Bạn là AI phân loại giấy tờ visa. Xác định loại giấy tờ và tên chủ sở hữu.

Trả về JSON duy nhất:
{{
  "person_name": "NGUYEN VAN A",
  "doc_type_en": "PASSPORT"
}}

Quy tắc:
- person_name: tên người sở hữu giấy tờ, viết IN HOA, không dấu. Nếu không rõ dùng "UNKNOWN PERSON".
- doc_type_en: loại giấy tờ tiếng Anh, IN HOA, ngắn gọn. Ví dụ:
  PASSPORT, CITIZEN IDENTITY CARD, BIRTH CERTIFICATE, MARRIAGE CERTIFICATE,
  BANK STATEMENT, SAVINGS BOOK, TAX RETURN, SALARY CERTIFICATE,
  LABOR CONTRACT, BUSINESS LICENSE, SOCIAL INSURANCE RECORD,
  HOTEL BOOKING, FLIGHT BOOKING, TRAVEL ITINERARY, TRAVEL INSURANCE,
  VISA GRANT NOTICE, IMMIGRATION RECORD, PROPERTY CERTIFICATE,
  DRIVER LICENSE, ACADEMIC TRANSCRIPT, APPLICATION FORM, PHOTO, COVER LETTER,
  POWER OF ATTORNEY, RECEIPT VOUCHER, AGREEMENT, PRICE QUOTATION,
  REGISTRATION FORM, LAND CERTIFICATE, DECISION
- Chỉ trả JSON, không giải thích.

RẤT QUAN TRỌNG VỀ person_name:
- TÊN FILE rất quan trọng! Nếu tên file có dạng "NGUYEN_LE_KIM_NGAN_Contract.pdf" thì person_name = "NGUYEN LE KIM NGAN".
- Nếu tên file có dạng "Hộ chiếu của mẹ chồng.pdf" hoặc tên Việt, vẫn cố gắng tìm tên trong NỘI DUNG.
- Nếu nội dung chứa tên người (trong phần chủ sở hữu, bên ủy quyền, bên được ủy quyền, v.v.), PHẢI dùng tên đó.
- CHỈ dùng "UNKNOWN PERSON" khi THẬT SỰ không thể tìm ra tên từ cả tên file lẫn nội dung.

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
- Không overlap trang. Thứ tự tăng dần.
- Chỉ trả JSON, không giải thích.

RẤT QUAN TRỌNG VỀ person_name:
- TÊN FILE rất quan trọng! Nếu tên file có dạng "NGUYEN_LE_KIM_NGAN_Contract.pdf" thì person_name = "NGUYEN LE KIM NGAN".
- Ưu tiên tìm tên TRONG NỘI DUNG trang. Nếu không rõ, dùng tên từ tên file.
- CHỈ dùng "UNKNOWN PERSON" khi THẬT SỰ không thể xác định từ cả tên file lẫn nội dung.

Tên file: {filename}
{pages_text}"""


def _classify_single(llm: Any, filename: str, text: str) -> Optional[Dict[str, str]]:
    """Classify a single-doc file with 1 API call."""
    prompt = _build_classify_prompt(filename, text)
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
        # Fallback: if AI returned UNKNOWN PERSON, try extracting from filename
        if person == "UNKNOWN PERSON":
            fname_name = _extract_name_from_filename(filename)
            if fname_name:
                person = fname_name
        return {
            "person_name": person,
            "doc_type_en": doc_type,
        }
    except Exception:
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
    except Exception:
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
        except Exception:
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
            except Exception:
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
        except Exception:
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
                except Exception:
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
