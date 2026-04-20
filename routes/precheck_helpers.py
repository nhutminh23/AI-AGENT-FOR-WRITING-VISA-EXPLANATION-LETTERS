"""
Shared helpers for precheck: vision detection, document enrichment,
name matching, doc-owner fixing, quick classification, classify_one factory.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Dict

from core.errors import QuotaExhaustedError, check_and_raise_quota

_check_and_raise_quota = check_and_raise_quota

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}

# ── Known bank name keywords ───────────────────────────────────────

_BANK_NAMES: Dict[str, str] = {
    'BIDV': 'BIDV', 'VCB': 'VCB', 'VIETCOMBANK': 'VCB',
    'TCB': 'TCB', 'TECHCOMBANK': 'TCB', 'ACB': 'ACB',
    'MBB': 'MB', 'MBBANK': 'MB', 'MB': 'MB',
    'VPB': 'VPB', 'VPBANK': 'VPB', 'SACOMBANK': 'SACOMBANK',
    'STB': 'SACOMBANK', 'AGRIBANK': 'AGRIBANK', 'TPBANK': 'TPBANK',
    'TPB': 'TPBANK', 'HDBank': 'HDBANK', 'SHB': 'SHB',
    'VIETINBANK': 'VIETINBANK', 'CTG': 'VIETINBANK',
    'EXIMBANK': 'EXIMBANK', 'SCB': 'SCB', 'OCB': 'OCB',
}

# ── Vietnamese keyword fallback ─────────────────────────────────────

_VN_KEYWORDS: Dict[str, str] = {
    # Land & Property
    'SỔ ĐỎ': 'LAND USE RIGHT CERTIFICATE',
    'SỔ HỒNG': 'LAND USE RIGHT CERTIFICATE',
    'QUYỀN SỬ DỤNG ĐẤT': 'LAND USE RIGHT CERTIFICATE',
    'GIẤY CHỨNG NHẬN QSDĐ': 'LAND USE RIGHT CERTIFICATE',
    # Vehicle
    'Ô TÔ': 'VEHICLE REGISTRATION',
    'XE MÁY': 'VEHICLE REGISTRATION',
    'ĐĂNG KÝ XE': 'VEHICLE REGISTRATION',
    'ĐĂNG KIỂM': 'VEHICLE INSPECTION',
    'CAVET': 'VEHICLE REGISTRATION',
    # Bank & Finance
    'TÀI KHOẢN': 'BANK ACCOUNT STATEMENT',
    'SỔ TIẾT KIỆM': 'SAVINGS BOOK',
    'XÁC NHẬN SỐ DƯ': 'BALANCE CONFIRMATION',
    # Insurance
    'BẢO HIỂM XÃ HỘI': 'SOCIAL INSURANCE',
    'BHXH': 'SOCIAL INSURANCE',
    'BẢO HIỂM Y TẾ': 'HEALTH INSURANCE',
    'BHYT': 'HEALTH INSURANCE',
    'BẢO HIỂM': 'INSURANCE',
    # Identity
    'HỘ CHIẾU': 'PASSPORT',
    'CCCD': 'CITIZEN IDENTITY CARD',
    'CMND': 'CITIZEN IDENTITY CARD',
    'GIẤY KHAI SINH': 'BIRTH CERTIFICATE',
    'KHAI SINH': 'BIRTH CERTIFICATE',
    'GIẤY ĐĂNG KÝ KẾT HÔN': 'MARRIAGE CERTIFICATE',
    'KẾT HÔN': 'MARRIAGE CERTIFICATE',
    'HỘ KHẨU': 'HOUSEHOLD REGISTRATION',
    # Employment & Tax
    'HỢP ĐỒNG LAO ĐỘNG': 'LABOR CONTRACT',
    'HỢP ĐỒNG': 'CONTRACT',
    'LƯƠNG': 'SALARY CERTIFICATE',
    'XÁC NHẬN LƯƠNG': 'SALARY CERTIFICATE',
    'THUẾ': 'TAX CERTIFICATE',
    'THUẾ TNCN': 'PERSONAL INCOME TAX',
    'TNCN': 'PERSONAL INCOME TAX',
    'THÔNG BÁO THUẾ': 'TAX NOTICE',
    'MST': 'TAX REGISTRATION',
    # Education
    'THẺ HỌC SINH': 'STUDENT ID CARD',
    'HỌC BẠ': 'ACADEMIC TRANSCRIPT',
    'BẰNG': 'DIPLOMA',
    'BẰNG TỐT NGHIỆP': 'GRADUATION DIPLOMA',
    'CHỨNG CHỈ': 'CERTIFICATE',
    # Travel
    'LỊCH TRÌNH': 'ITINERARY',
    'VÉ MÁY BAY': 'FLIGHT TICKET',
    'BOOKING': 'BOOKING CONFIRMATION',
    'KHÁCH SẠN': 'HOTEL BOOKING',
    # Business
    'GIẤY PHÉP KINH DOANH': 'BUSINESS LICENSE',
    'ĐĂNG KÝ KINH DOANH': 'BUSINESS REGISTRATION',
    'GPKD': 'BUSINESS LICENSE',
    'GIẤY ỦY QUYỀN': 'POWER OF ATTORNEY',
    'ỦY QUYỀN': 'POWER OF ATTORNEY',
    # Application
    'FORM': 'APPLICATION FORM',
    'ĐƠN XIN': 'APPLICATION FORM',
    # Other common
    'ORIGIN': 'ORIGIN STATEMENT',
    'GRANTED': 'GRANT LETTER',
    'GIẤY XÁC NHẬN': 'CONFIRMATION LETTER',
}

# ── Quick classify map (skip LLM for obvious filenames) ─────────────

_QUICK_CLASSIFY_MAP: Dict[str, str] = {
    'hộ chiếu': 'PASSPORT', 'ho chieu': 'PASSPORT', 'passport': 'PASSPORT',
    'cccd': 'CITIZEN IDENTITY CARD', 'cmnd': 'CITIZEN IDENTITY CARD',
    'khai sinh': 'BIRTH CERTIFICATE', 'birth': 'BIRTH CERTIFICATE',
    'kết hôn': 'MARRIAGE CERTIFICATE', 'ket hon': 'MARRIAGE CERTIFICATE',
    'sổ đất': 'LAND USE RIGHT CERTIFICATE', 'so dat': 'LAND USE RIGHT CERTIFICATE',
    'sổ đỏ': 'LAND USE RIGHT CERTIFICATE', 'so do': 'LAND USE RIGHT CERTIFICATE',
    'quyền sử dụng đất': 'LAND USE RIGHT CERTIFICATE',
    'thẻ học sinh': 'STUDENT ID CARD', 'the hoc sinh': 'STUDENT ID CARD',
    'bank': 'BANK STATEMENT', 'ngân hàng': 'BANK STATEMENT',
    'hợp đồng thuê': 'RENTAL AGREEMENT', 'hd thue': 'RENTAL AGREEMENT',
    'hd cho thue': 'RENTAL AGREEMENT', 'thuê nhà': 'RENTAL AGREEMENT',
    'xác nhận công việc': 'WORK CERTIFICATE', 'xncv': 'WORK CERTIFICATE',
    'xác nhận số dư': 'BALANCE CONFIRMATION', 'xnsd': 'BALANCE CONFIRMATION',
    'nghỉ phép': 'LEAVE REQUEST', 'don xin nghi': 'LEAVE REQUEST',
    'sổ tiết kiệm': 'SAVINGS BOOK', 'tiet kiem': 'SAVINGS BOOK',
    'bảo hiểm': 'INSURANCE', 'bhxh': 'SOCIAL INSURANCE',
    'thuế': 'TAX CERTIFICATE', 'thue': 'TAX CERTIFICATE',
    'hộ khẩu': 'HOUSEHOLD REGISTRATION', 'ho khau': 'HOUSEHOLD REGISTRATION',
}

# Vietnamese relational clues
_VN_RELATION_CLUES = [
    'con trai', 'con gái', 'con', 'mẹ', 'vợ', 'bố', 'cha',
    'chồng', 'anh', 'chị', 'em', 'bà', 'ông',
]

# Personal doc types where owner matters
_PERSONAL_DOCS = [
    'PASSPORT', 'OLD PASSPORT', 'STUDENT ID', 'STUDENT CARD',
    'BIRTH CERTIFICATE', 'IDENTITY CARD', 'CCCD', 'CITIZEN',
    'HEALTH INSURANCE', 'PHOTO',
]

# Property/land docs → always use folder name, skip doc_owner
_SKIP_OWNER_DOCS = [
    'LAND USE', 'LAND CERTIFICATE', 'PROPERTY', 'SỔ ĐỎ',
    'RENTAL AGREEMENT', 'LEASE', 'CONTRACT',
]

# Passport family types (treated as single document bundle)
_PASSPORT_FAMILY = {'PASSPORT', 'VISA', 'OLD PASSPORT'}


# ═══════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════

def _vision_detect_pdf_documents(llm, pdf_path: str, filename: str, total_pages: int):
    """Vision check: does this scanned PDF contain multiple documents?
    Detects both different document types AND same-type docs for different people.
    Samples up to 8 pages at 100 DPI for reliable name/type recognition."""
    import fitz  # PyMuPDF
    import base64

    doc = fitz.open(pdf_path)
    actual_pages = len(doc)

    # Smart sampling: ALL pages for short PDFs, evenly-spaced for longer ones
    if actual_pages <= 6:
        sample_indices = list(range(actual_pages))
    else:
        max_samples = min(8, actual_pages)
        step = (actual_pages - 1) / (max_samples - 1)
        sample_indices = sorted(set(int(round(i * step)) for i in range(max_samples)))

    # Render sampled pages as images
    content_parts = [
        {"type": "text", "text": f"""Analyze these {len(sample_indices)} sampled pages from "{filename}" ({actual_pages} pages total).

TASK: Determine if this PDF contains MULTIPLE TRULY SEPARATE documents that were scanned together into one file. 

A PDF needs splitting ONLY when it contains GENUINELY DIFFERENT, STANDALONE documents. Examples of documents that NEED splitting:
- Marriage certificate + birth certificate (completely different docs)
- Two birth certificates for DIFFERENT children (same type but different people)
- Bank statement + identity card (unrelated docs)
- Multiple standalone government certificates mixed together

⚠️ DO NOT SPLIT these — they are ONE document/package:
- PASSPORT booklet with visa stamps/stickers = 1 PASSPORT (visa pages are part of the passport)
- Rental/Lease AGREEMENT + inventory list/appendix/attachment = 1 RENTAL AGREEMENT (appendices belong to the contract)
- Any CONTRACT + its appendix/supplement/addendum = 1 CONTRACT
- Land use RIGHT CERTIFICATE + supplementary pages = 1 LAND CERTIFICATE
- Any document with its cover page + content pages = 1 document
- Bank statement spanning multiple pages = 1 BANK STATEMENT
- Front + back of same ID card = 1 IDENTITY CARD

⚠️ CRITICAL — PASSPORT EXPIRY CHECK:
The current year is 2026. For ANY passport document, you MUST read the "Date of expiry" / "Ngày hết hạn" field on the passport image.
- If the expiry year < 2026 → doc_type_en = "OLD PASSPORT [expiry year]" (e.g. "OLD PASSPORT 2011")
- If the expiry year >= 2026 → doc_type_en = "PASSPORT"
You MUST include the actual expiry year you read from the document.

For EACH truly separate document found, provide:
- doc_type_en: type in ENGLISH, UPPERCASE (see passport rule above)
- person_name: owner name in UPPERCASE, no diacritics. If unclear → "UNKNOWN"
- start_page and end_page: approximate page range

Return JSON ONLY:
{{"documents": [
  {{"doc_type_en": "OLD PASSPORT 2011", "person_name": "NGUYEN VAN A", "start_page": 1, "end_page": 2}},
  {{"doc_type_en": "BIRTH CERTIFICATE", "person_name": "NGUYEN VAN B", "start_page": 3, "end_page": 4}}
]}}

If this is ONE single document or package: {{"documents": [{{"doc_type_en": "RENTAL AGREEMENT", "person_name": "NGUYEN VAN A", "start_page": 1, "end_page": {actual_pages}}}]}}"""}
    ]

    for idx in sample_indices:
        page = doc[idx]
        pix = page.get_pixmap(dpi=100)  # 100 DPI: enough to read names on scanned docs
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode()
        content_parts.append({"type": "text", "text": f"Page {idx + 1}/{actual_pages}:"})
        content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    doc.close()

    from langchain_core.messages import HumanMessage, SystemMessage
    try:
        result = llm.invoke([
            SystemMessage(content="You are an expert document classifier for visa application files. You can read Vietnamese documents. Answer only with JSON."),
            HumanMessage(content=content_parts),
        ])
    except Exception as exc:
        logging.exception("[Safe Log] Unhandled exception in precheck_helpers.py: %s", exc)
        _check_and_raise_quota(exc)
        raise

    # Parse response
    text = (result.content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)

    try:
        parsed = json.loads(text)
    except Exception:
        logging.exception("[Safe Log] Unhandled exception in precheck_helpers.py: invalid JSON from vision classifier")
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                parsed = json.loads(match.group())
            except Exception:
                logging.exception("[Safe Log] Unhandled exception in precheck_helpers.py: fallback JSON parse failed")
                return []
        else:
            return []

    # Extract documents list
    docs = parsed.get("documents", [])
    if not isinstance(docs, list) or len(docs) == 0:
        # Fallback: try old format (mixed/doc_count)
        is_mixed = parsed.get("mixed", False)
        doc_count = int(parsed.get("doc_count", 1))
        doc_types = parsed.get("doc_types", ["UNKNOWN"])
        if is_mixed and doc_count > 1:
            return [{"doc_type_en": dt, "person_name": "UNKNOWN", "start_page": 0, "end_page": 0}
                    for dt in doc_types]
        return [{"doc_type_en": doc_types[0] if doc_types else "UNKNOWN",
                 "person_name": "UNKNOWN", "start_page": 1, "end_page": actual_pages}]

    # Process documents list
    output = []
    for item in docs:
        if not isinstance(item, dict):
            continue
        output.append({
            "doc_type_en": (item.get("doc_type_en") or "UNKNOWN").upper().strip(),
            "person_name": (item.get("person_name") or "UNKNOWN").upper().strip(),
            "start_page": int(item.get("start_page", 0)),
            "end_page": int(item.get("end_page", 0)),
        })

    return output if output else [{"doc_type_en": "UNKNOWN", "person_name": "UNKNOWN",
                                    "start_page": 1, "end_page": actual_pages}]


def enrich_doc_type(doc_type: str, filename: str, sub_path: str) -> str:
    """Post-process: add bank name and time period to doc_type if AI missed them."""
    upper_type = doc_type.upper().strip()
    context_upper = (filename + " " + sub_path).upper()
    fname_only = os.path.splitext(filename)[0].upper()

    is_financial = any(kw in upper_type for kw in ['BANK', 'STATEMENT', 'SAVINGS', 'BALANCE', 'DEPOSIT', 'ACCOUNT'])
    if not is_financial:
        is_financial = any(kw in context_upper for kw in ['SỔ PHỤ', 'SAO KÊ', 'BANK', 'SỔ TIẾT KIỆM'])
        if is_financial and upper_type in ['DOCUMENT', 'UNKNOWN DOCUMENT']:
            upper_type = 'BANK STATEMENT'

    if is_financial:
        has_bank = any(bk in upper_type for bk in _BANK_NAMES.values())
        if not has_bank:
            for keyword, bank_std in _BANK_NAMES.items():
                if keyword.upper() in context_upper:
                    upper_type = f"{upper_type} {bank_std}"
                    break

        has_period = bool(re.search(r'T\d{1,2}|20\d{2}', upper_type))
        if not has_period:
            periods = re.findall(r'T(\d{1,2})', fname_only)
            years = re.findall(r'(20\d{2})', fname_only)
            period_parts = []
            if periods:
                period_parts.extend([f"T{p.zfill(2)}" for p in periods])
            if years:
                period_parts.extend(years)
            period_parts = list(dict.fromkeys(period_parts))
            if period_parts:
                upper_type = f"{upper_type} {' '.join(period_parts)}"

    # Vietnamese keyword fallback
    if upper_type in ['DOCUMENT', 'UNKNOWN DOCUMENT', 'UNKNOWN', 'OTHER', 'PHOTO']:
        fn_upper = filename.upper()
        sub_upper = sub_path.upper() if sub_path else ""
        search_text = fn_upper + " " + sub_upper
        for vn_kw, en_type in _VN_KEYWORDS.items():
            if vn_kw.upper() in search_text:
                upper_type = en_type
                break

    return upper_type.strip()


def is_same_person(name_a: str, name_b: str) -> bool:
    """Check if two Vietnamese names refer to the same person."""
    if not name_a or not name_b:
        return False
    a = name_a.replace("_", " ").strip().upper()
    b = name_b.replace("_", " ").strip().upper()
    if a == b:
        return True
    if a in b or b in a:
        return True
    parts_a = a.split()
    parts_b = b.split()
    if len(parts_a) >= 2 and len(parts_b) >= 2:
        if parts_a[-2:] == parts_b[-2:]:
            return True
        if len(parts_a) >= 3 and len(parts_b) >= 3:
            if parts_a[-3:] == parts_b[-3:]:
                return True
    shorter, longer = (parts_a, parts_b) if len(parts_a) <= len(parts_b) else (parts_b, parts_a)
    if len(shorter) >= 2:
        tail2 = shorter[-2:]
        for i in range(len(longer) - 1):
            if longer[i:i+2] == tail2:
                return True
    if len(shorter) >= 3:
        tail3 = shorter[-3:]
        for i in range(len(longer) - 2):
            if longer[i:i+3] == tail3:
                return True
    return False


def fix_doc_owner(doc_owner: str, person_name: str, filename: str, doc_type: str) -> str:
    """Post-process: fix doc_owner to avoid duplicates and detect missing owners."""
    from classifier.agent import normalize_vietnamese_name
    owner = (doc_owner or "").strip()

    if owner.upper() in ('UNKNOWN PERSON', 'UNKNOWN', 'UNKNOWN_PERSON'):
        owner = ""

    upper_dt = doc_type.upper()
    if any(kw in upper_dt for kw in _SKIP_OWNER_DOCS):
        return ""

    if owner:
        owner_norm = normalize_vietnamese_name(owner)
        if is_same_person(owner_norm, person_name):
            return ""

    fn_lower = filename.lower()
    has_relation_clue = any(clue in fn_lower for clue in _VN_RELATION_CLUES)

    if not owner:
        upper_type = doc_type.upper()
        identity_docs = ['PASSPORT', 'OLD PASSPORT', 'CITIZEN IDENTITY', 'CCCD',
                         'BIRTH CERTIFICATE', 'STUDENT ID', 'STUDENT CARD',
                         'HEALTH INSURANCE', 'SCHOOL']
        is_identity = any(kw in upper_type for kw in identity_docs)

        if is_identity or has_relation_clue:
            stem = os.path.splitext(filename)[0]
            match = re.search(r'[A-Z]{2,6}(?:\s*\.?\s*$)', stem)
            if match:
                initials = match.group().strip('. ')
                if initials not in person_name:
                    return initials

    return owner


def quick_classify_from_filename(fname: str) -> str:
    """Try to classify doc type from filename alone. Returns '' if unclear."""
    fn_lower = os.path.splitext(fname)[0].lower()
    for kw, doc_type in _QUICK_CLASSIFY_MAP.items():
        if kw in fn_lower:
            return doc_type
    return ""


def classify_one(file_info: dict, person_name: str, llm, quota_stop) -> dict:
    """Classify a single file: uses LLM + vision detection.
    This is the main per-file classification function used by precheck_scan."""
    from classifier.agent import classify_doc_type_only, normalize_vietnamese_name

    fname = file_info["filename"]
    fpath = file_info["path"]
    ext = file_info["ext"]
    sub_path = file_info.get("sub_path", fname)

    # Detect if file is inside a Translate/ subfolder
    _is_translate_file = False
    _sub_path_lower = sub_path.replace("\\", "/").lower()
    if _sub_path_lower.startswith("translate/") or "/translate/" in _sub_path_lower:
        _is_translate_file = True

    # Early exit if quota already exhausted
    if quota_stop.is_set():
        return {
            **file_info,
            "person_name": person_name,
            "doc_type_en": "QUOTA ERROR",
            "doc_owner": "",
            "suggested_name": fname,
            "needs_split": False,
            "doc_count": 1,
            "doc_types": ["ERROR"],
            "error": "Skipped: API quota exhausted",
            "quota_error": True,
        }

    try:
        # FAST PATH: if filename clearly tells us the doc type, skip LLM call
        quick_type = quick_classify_from_filename(fname)
        if quick_type:
            page_count = 1
            if ext == '.pdf':
                try:
                    from pypdf import PdfReader as _PdfR
                    page_count = len(_PdfR(fpath).pages)
                except Exception as e:
                    logging.exception("[Safe Log] Unhandled exception in precheck_helpers.py: %s", e)
                    logging.debug("Ignored: %s", e)
            if page_count <= 2:
                doc_type = quick_type
                doc_owner = ""
                needs_split = False
                doc_count = 1
                doc_types = [doc_type]
                doc_type = enrich_doc_type(doc_type, fname, sub_path)
                doc_owner = fix_doc_owner(doc_owner, person_name, fname, doc_type)
                doc_type_clean = doc_type.upper().strip()
                doc_type_clean = re.sub(r'[^A-Z0-9]+', '_', doc_type_clean).strip('_')
                out_ext = '.pdf' if ext in IMAGE_EXTS else ext
                prefix = "TRANSLATED_" if _is_translate_file else ""
                suggested_name = f"{prefix}{person_name}_{doc_type_clean}{out_ext}"
                return {
                    **file_info,
                    "person_name": person_name,
                    "doc_type_en": doc_type,
                    "doc_owner": doc_owner,
                    "suggested_name": suggested_name,
                    "needs_split": needs_split,
                    "doc_count": doc_count,
                    "doc_types": doc_types,
                    "fast_classified": True,
                    "is_translate": _is_translate_file,
                }

        result = classify_doc_type_only(llm, fname, fpath, folder_person=person_name)
        doc_type = result.get("doc_type_en", "DOCUMENT")
        doc_owner = result.get("doc_owner", "")
        ai_person = result.get("person_name", "")
        needs_split = result.get("needs_split", False)
        doc_count = result.get("doc_count", 1)
        doc_types = result.get("doc_types", [doc_type])

        # TRANSLATE FILES: force skip split
        if _is_translate_file:
            needs_split = False
            doc_count = 1

        # VISION MULTI-DOC DETECTION for PDFs
        if ext == '.pdf' and not needs_split:
            try:
                from pypdf import PdfReader as _PdfR
                _reader = _PdfR(fpath)
                total_pages = len(_reader.pages)
                page_texts_len = [len((p.extract_text() or "").strip()) for p in _reader.pages]
                has_scanned_pages = any(tl < 30 for tl in page_texts_len)
                all_scanned = all(tl < 30 for tl in page_texts_len)
            except Exception:
                logging.exception("[Safe Log] Unhandled exception in precheck_helpers.py: PDF scan pre-check failed")
                total_pages = 1
                has_scanned_pages = True
                all_scanned = True

            _VN_CLUES_FOR_VISION = [
                'con trai', 'con gái', 'con', 'mẹ', 'vợ', 'bố', 'cha',
                'chồng', 'anh', 'chị', 'em', 'bà', 'ông',
            ]
            fn_lower_check = fname.lower()
            needs_vision_for_name = any(c in fn_lower_check for c in _VN_CLUES_FOR_VISION)
            should_run_vision = _is_translate_file or (has_scanned_pages and (total_pages >= 2 or needs_vision_for_name or all_scanned))
            if should_run_vision:
                try:
                    vision_results = _vision_detect_pdf_documents(llm, fpath, fname, total_pages)
                    if vision_results:
                        if len(vision_results) > 1 and not _is_translate_file:
                            vr_types = set()
                            vr_persons = set()
                            for vr in vision_results:
                                vt = vr.get("doc_type_en", "").upper()
                                for pf in _PASSPORT_FAMILY:
                                    if vt.startswith(pf):
                                        vr_types.add(pf)
                                        break
                                else:
                                    vr_types.add(vt)
                                vr_persons.add(vr.get("person_name", "UNKNOWN").upper())
                            is_passport_bundle = vr_types.issubset(_PASSPORT_FAMILY) and len(vr_persons) <= 1
                            if not is_passport_bundle:
                                needs_split = True
                                doc_count = len(vision_results)
                            doc_types = []
                            for r in vision_results:
                                dt = r.get("doc_type_en", "UNKNOWN")
                                pn = r.get("person_name", "")
                                if pn and pn != "UNKNOWN":
                                    doc_types.append(f"{dt} ({pn})")
                                else:
                                    doc_types.append(dt)
                            doc_type = vision_results[0].get("doc_type_en", doc_type)
                        # Always use vision person_name
                        vision_person = vision_results[0].get("person_name", "")
                        if vision_person and vision_person not in ("UNKNOWN", "UNKNOWN PERSON"):
                            ai_person = vision_person
                        vision_doc_type = vision_results[0].get("doc_type_en", "")
                        if vision_doc_type:
                            if all_scanned:
                                doc_type = vision_doc_type
                            elif doc_type in ("DOCUMENT", "UNKNOWN DOCUMENT", "UNKNOWN"):
                                doc_type = vision_doc_type
                except QuotaExhaustedError:
                    raise
                except Exception as e:
                    logging.exception("[Safe Log] Unhandled exception in precheck_helpers.py: %s", e)
                    logging.debug("Ignored: %s", e)

        # POST-PROCESSING
        doc_type = enrich_doc_type(doc_type, fname, sub_path)
        doc_owner = fix_doc_owner(doc_owner, person_name, fname, doc_type)

        # FALLBACK: AI returned different person_name
        upper_doc = doc_type.upper()
        is_personal = any(kw in upper_doc for kw in _PERSONAL_DOCS)
        if not doc_owner and ai_person and is_personal:
            ai_person_norm = normalize_vietnamese_name(ai_person)
            if (ai_person_norm and ai_person_norm != "UNKNOWN_PERSON"
                    and not is_same_person(ai_person_norm, person_name)):
                doc_owner = ai_person_norm

        # Build suggested name
        doc_type_clean = doc_type.upper().strip()
        doc_type_clean = re.sub(r'[^A-Z0-9]+', '_', doc_type_clean).strip('_')
        out_ext = '.pdf' if ext in IMAGE_EXTS else ext
        prefix = "TRANSLATED_" if _is_translate_file else ""

        if doc_owner:
            owner_clean = re.sub(r'[^A-Z0-9]+', '_', doc_owner.upper().strip()).strip('_')
            suggested_name = f"{prefix}{owner_clean}_{doc_type_clean}{out_ext}"
        else:
            suggested_name = f"{prefix}{person_name}_{doc_type_clean}{out_ext}"

        return {
            **file_info,
            "person_name": person_name,
            "doc_type_en": doc_type,
            "doc_owner": doc_owner,
            "suggested_name": suggested_name,
            "needs_split": needs_split,
            "doc_count": doc_count,
            "doc_types": doc_types,
            "is_translate": _is_translate_file,
        }
    except Exception as e:
        logging.exception("[Safe Log] Unhandled exception in precheck_helpers.py: %s", e)
        err_str = str(e).lower()
        is_quota = 'insufficient_quota' in err_str or '429' in err_str or 'rate limit' in err_str
        if is_quota:
            quota_stop.set()
        return {
            **file_info,
            "person_name": person_name,
            "doc_type_en": "QUOTA ERROR" if is_quota else "ERROR",
            "doc_owner": "",
            "suggested_name": fname,
            "needs_split": False,
            "doc_count": 1,
            "doc_types": ["ERROR"],
            "error": str(e),
            "quota_error": is_quota,
        }
