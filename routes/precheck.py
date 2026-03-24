"""
Pre-check routes: file listing, document scanning, rename, merge.
"""
from __future__ import annotations

import json
import logging
import os
import re

from flask import Blueprint, jsonify, request

from core.errors import QuotaExhaustedError, check_and_raise_quota

# Alias for underscore-prefixed name used in this file
_check_and_raise_quota = check_and_raise_quota
from core.helpers import get_vision_model, list_input_files

precheck_bp = Blueprint("precheck", __name__)

# Base directory (project root, one level up from routes/)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# get_vision_model, list_input_files → imported from core.helpers

@precheck_bp.get("/api/files")
def list_files():
    input_dir = request.args.get("input_dir", "input")
    files = list_input_files(input_dir)
    return jsonify({"input_dir": input_dir, "files": files})




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
        # Sample up to 8 pages evenly distributed (first, last, + 6 middle)
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
        _check_and_raise_quota(exc)
        raise
    
    # Parse response
    import re
    text = (result.content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    
    try:
        parsed = json.loads(text)
    except Exception as e:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                parsed = json.loads(match.group())
            except Exception as e:
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


# ── Progress tracking for precheck scan ──
_precheck_progress = {"total": 0, "done": 0, "current_file": "", "running": False}

@precheck_bp.get("/api/precheck/progress")
def precheck_progress():
    """Poll endpoint for scan progress."""
    return jsonify(_precheck_progress)

@precheck_bp.post("/api/precheck/scan")
def precheck_scan():
    """Scan all files in input/ subfolders: classify doc type + detect multi-doc + suggest rename."""
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    model = payload.get("model") or get_vision_model()

    if not os.path.isdir(input_dir):
        return jsonify({"error": "folder_not_found", "input_dir": input_dir}), 404

    from langchain_openai import ChatOpenAI
    from classifier.agent import classify_doc_type_only, normalize_vietnamese_name
    from concurrent.futures import ThreadPoolExecutor, as_completed

    llm = ChatOpenAI(model=model, temperature=0)

    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}

    # Collect files grouped by person subfolder (RECURSIVE with os.walk)
    folders_data = {}
    for item in sorted(os.listdir(input_dir)):
        folder_path = os.path.join(input_dir, item)
        if not os.path.isdir(folder_path):
            continue
        if item.startswith('.') or item.startswith('_'):
            continue
        person_normalized = normalize_vietnamese_name(item)
        files_in_folder = []
        # Walk recursively into all subfolders
        for root, _dirs, filenames in os.walk(folder_path):
            for fname in sorted(filenames):
                fpath = os.path.join(root, fname)
                if not os.path.isfile(fpath):
                    continue
                rel_path = os.path.relpath(fpath, input_dir).replace("\\", "/")
                sub_path = os.path.relpath(fpath, folder_path).replace("\\", "/")
                ext = os.path.splitext(fname)[1].lower()
                files_in_folder.append({
                    "filename": fname,
                    "path": fpath,
                    "rel_path": rel_path,
                    "sub_path": sub_path,  # path relative to person folder
                    "ext": ext,
                })
        if files_in_folder:
            folders_data[item] = {
                "folder_name": item,
                "person_name": person_normalized,
                "files": files_in_folder,
            }

    # Also collect files in root (not in any subfolder)
    root_files = []
    for fname in sorted(os.listdir(input_dir)):
        fpath = os.path.join(input_dir, fname)
        if os.path.isfile(fpath):
            ext = os.path.splitext(fname)[1].lower()
            root_files.append({
                "filename": fname,
                "path": fpath,
                "rel_path": fname,
                "sub_path": fname,
                "ext": ext,
            })
    if root_files:
        folders_data["__ROOT__"] = {
            "folder_name": "(Root)",
            "person_name": "UNKNOWN",
            "files": root_files,
        }

    # Classify all files in parallel
    # Known bank name keywords for post-processing
    _BANK_NAMES = {
        'BIDV': 'BIDV', 'VCB': 'VCB', 'VIETCOMBANK': 'VCB',
        'TCB': 'TCB', 'TECHCOMBANK': 'TCB', 'ACB': 'ACB',
        'MBB': 'MB', 'MBBANK': 'MB', 'MB': 'MB',
        'VPB': 'VPB', 'VPBANK': 'VPB', 'SACOMBANK': 'SACOMBANK',
        'STB': 'SACOMBANK', 'AGRIBANK': 'AGRIBANK', 'TPBANK': 'TPBANK',
        'TPB': 'TPBANK', 'HDBank': 'HDBANK', 'SHB': 'SHB',
        'VIETINBANK': 'VIETINBANK', 'CTG': 'VIETINBANK',
        'EXIMBANK': 'EXIMBANK', 'SCB': 'SCB', 'OCB': 'OCB',
    }

    def _enrich_doc_type(doc_type: str, filename: str, sub_path: str) -> str:
        """Post-process: add bank name and time period to doc_type if AI missed them."""
        upper_type = doc_type.upper().strip()
        # Full context for bank name detection
        context_upper = (filename + " " + sub_path).upper()
        # ONLY filename for period extraction (avoid folder path duplicates)
        fname_only = os.path.splitext(filename)[0].upper()

        # Only enrich financial docs (BANK STATEMENT, SAVINGS BOOK, BALANCE, etc.)
        financial_keywords = ['BANK STATEMENT', 'SAVINGS', 'BALANCE', 'ACCOUNT STATEMENT',
                              'DEPOSIT', 'SỔ PHỤ', 'SAO KÊ']
        is_financial = any(kw in upper_type for kw in ['BANK', 'STATEMENT', 'SAVINGS', 'BALANCE', 'DEPOSIT', 'ACCOUNT'])
        if not is_financial:
            # Also check if filename suggests financial but AI returned generic DOCUMENT
            is_financial = any(kw in context_upper for kw in ['SỔ PHỤ', 'SAO KÊ', 'BANK', 'SỔ TIẾT KIỆM'])
            if is_financial and upper_type in ['DOCUMENT', 'UNKNOWN DOCUMENT']:
                upper_type = 'BANK STATEMENT'

        if is_financial:
            # Check if bank name already in doc_type
            has_bank = any(bk in upper_type for bk in _BANK_NAMES.values())
            if not has_bank:
                # Try to find bank name in full path context
                for keyword, bank_std in _BANK_NAMES.items():
                    if keyword.upper() in context_upper:
                        upper_type = f"{upper_type} {bank_std}"
                        break

            # Check if time period already in doc_type (T01, T06, 2025, 2026, etc.)
            has_period = bool(re.search(r'T\d{1,2}|20\d{2}', upper_type))
            if not has_period:
                # Extract periods from FILENAME ONLY (not folder path!) to avoid duplicates
                periods = re.findall(r'T(\d{1,2})', fname_only)
                years = re.findall(r'(20\d{2})', fname_only)
                period_parts = []
                if periods:
                    period_parts.extend([f"T{p.zfill(2)}" for p in periods])
                if years:
                    period_parts.extend(years)
                # Deduplicate while preserving order
                period_parts = list(dict.fromkeys(period_parts))
                if period_parts:
                    upper_type = f"{upper_type} {' '.join(period_parts)}"

        # ==== VIETNAMESE KEYWORD FALLBACK ====
        # When AI returns generic DOCUMENT/PHOTO, try to match Vietnamese keywords in filename
        if upper_type in ['DOCUMENT', 'UNKNOWN DOCUMENT', 'UNKNOWN', 'OTHER', 'PHOTO']:
            _VN_KEYWORDS = {
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
            # Search in both filename and folder path (Vietnamese chars!)
            fn_upper = filename.upper()
            sub_upper = sub_path.upper() if sub_path else ""
            search_text = fn_upper + " " + sub_upper
            for vn_kw, en_type in _VN_KEYWORDS.items():
                if vn_kw.upper() in search_text:
                    upper_type = en_type
                    break

        return upper_type.strip()

    def _is_same_person(name_a: str, name_b: str) -> bool:
        """Check if two Vietnamese names refer to the same person.
        Handles: LE THI NHAT PHUONG vs NGUYEN THI NHAT PHUONG (same person, different family name).
        Also handles folder prefix like UC_NGUYEN_THI_NHAT_PHUONG_VINH."""
        if not name_a or not name_b:
            return False
        a = name_a.replace("_", " ").strip().upper()
        b = name_b.replace("_", " ").strip().upper()
        # Exact match
        if a == b:
            return True
        # Substring containment
        if a in b or b in a:
            return True
        parts_a = a.split()
        parts_b = b.split()
        # Same given name (last 2+ words match at end)
        if len(parts_a) >= 2 and len(parts_b) >= 2:
            if parts_a[-2:] == parts_b[-2:]:
                return True
            if len(parts_a) >= 3 and len(parts_b) >= 3:
                if parts_a[-3:] == parts_b[-3:]:
                    return True
        # Handle folder names with prefix (UC) or suffix (city like VINH):
        # Check if shorter name's last 2 given-name parts appear as consecutive
        # words anywhere in the longer name. e.g. "NHAT PHUONG" from
        # "LE THI NHAT PHUONG" appears in "UC NGUYEN THI NHAT PHUONG VINH"
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

    def _fix_doc_owner(doc_owner: str, person_name: str, filename: str, doc_type: str) -> str:
        """Post-process: fix doc_owner to avoid duplicates and detect missing owners."""
        from classifier.agent import normalize_vietnamese_name
        owner = (doc_owner or "").strip()

        # Treat UNKNOWN PERSON / UNKNOWN as "no owner found"
        if owner.upper() in ('UNKNOWN PERSON', 'UNKNOWN', 'UNKNOWN_PERSON'):
            owner = ""

        # Property/land docs → always use folder name, skip doc_owner
        _SKIP_OWNER_DOCS = [
            'LAND USE', 'LAND CERTIFICATE', 'PROPERTY', 'SỔ ĐỎ',
            'RENTAL AGREEMENT', 'LEASE', 'CONTRACT',
        ]
        upper_dt = doc_type.upper()
        if any(kw in upper_dt for kw in _SKIP_OWNER_DOCS):
            return ""

        # If doc_owner is same as folder person → set empty (it's the main applicant)
        if owner:
            owner_norm = normalize_vietnamese_name(owner)
            if _is_same_person(owner_norm, person_name):
                return ""

        # Vietnamese relational clues in filename that indicate different person
        _VN_RELATION_CLUES = [
            'con trai', 'con gái', 'con', 'mẹ', 'vợ', 'bố', 'cha',
            'chồng', 'anh', 'chị', 'em', 'bà', 'ông',
        ]
        fn_lower = filename.lower()
        has_relation_clue = any(clue in fn_lower for clue in _VN_RELATION_CLUES)

        # If no doc_owner but filename has initials/name different from person
        if not owner:
            upper_type = doc_type.upper()
            # Only for identity/personal docs where owner matters
            identity_docs = ['PASSPORT', 'OLD PASSPORT', 'CITIZEN IDENTITY', 'CCCD',
                             'BIRTH CERTIFICATE', 'STUDENT ID', 'STUDENT CARD',
                             'HEALTH INSURANCE', 'SCHOOL']
            is_identity = any(kw in upper_type for kw in identity_docs)

            if is_identity or has_relation_clue:
                stem = os.path.splitext(filename)[0]
                # Look for initials (2-6 uppercase letters at end of filename)
                match = re.search(r'[A-Z]{2,6}(?:\s*\.?\s*$)', stem)
                if match:
                    initials = match.group().strip('. ')
                    if initials not in person_name:
                        return initials

        return owner

    import threading
    _quota_stop = threading.Event()

    # Quick filename-based doc type lookup (skips LLM call for obvious files)
    _QUICK_CLASSIFY_MAP = {
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

    def _quick_classify_from_filename(fname: str) -> str:
        """Try to classify doc type from filename alone. Returns '' if unclear."""
        fn_lower = os.path.splitext(fname)[0].lower()
        # Remove common prefixes like numbers, parentheses
        for kw, doc_type in _QUICK_CLASSIFY_MAP.items():
            if kw in fn_lower:
                return doc_type
        return ""

    def _classify_one(file_info, person_name):
        fname = file_info["filename"]
        fpath = file_info["path"]
        ext = file_info["ext"]
        sub_path = file_info.get("sub_path", fname)

        # Early exit if quota already exhausted (don't waste API calls)
        if _quota_stop.is_set():
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
            # This saves both time AND tokens for obvious files
            quick_type = _quick_classify_from_filename(fname)
            if quick_type:
                # Still need to check page count for multi-doc detection
                page_count = 1
                if ext == '.pdf':
                    try:
                        from pypdf import PdfReader as _PdfR
                        page_count = len(_PdfR(fpath).pages)
                    except Exception as e:
                        logging.debug("Ignored: %s", e)
                # Single page or known single-doc type → skip LLM
                if page_count <= 2:
                    doc_type = quick_type
                    doc_owner = ""
                    ai_person = ""
                    needs_split = False
                    doc_count = 1
                    doc_types = [doc_type]
                    # Jump directly to post-processing (skip LLM + vision)
                    doc_type = _enrich_doc_type(doc_type, fname, sub_path)
                    doc_owner = _fix_doc_owner(doc_owner, person_name, fname, doc_type)
                    doc_type_clean = doc_type.upper().strip()
                    doc_type_clean = re.sub(r'[^A-Z0-9]+', '_', doc_type_clean).strip('_')
                    out_ext = '.pdf' if ext in IMAGE_EXTS else ext
                    suggested_name = f"{person_name}_{doc_type_clean}{out_ext}"
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
                    }

            result = classify_doc_type_only(llm, fname, fpath, folder_person=person_name)
            doc_type = result.get("doc_type_en", "DOCUMENT")
            doc_owner = result.get("doc_owner", "")
            ai_person = result.get("person_name", "")  # Actual owner from document content
            needs_split = result.get("needs_split", False)
            doc_count = result.get("doc_count", 1)
            doc_types = result.get("doc_types", [doc_type])

            # VISION MULTI-DOC DETECTION for PDFs (2+ pages, not already flagged)
            # Only skip vision if ALL pages have extractable text (text-based is reliable)
            # If ANY pages are scanned (empty), vision is needed as backup
            if ext == '.pdf' and not needs_split:
                try:
                    from pypdf import PdfReader as _PdfR
                    _reader = _PdfR(fpath)
                    total_pages = len(_reader.pages)
                    # Check if pages lack text (scanned/image pages)
                    page_texts_len = [len((p.extract_text() or "").strip()) for p in _reader.pages]
                    has_scanned_pages = any(tl < 30 for tl in page_texts_len)
                    all_scanned = all(tl < 30 for tl in page_texts_len)
                except Exception as e:
                    total_pages = 1
                    has_scanned_pages = True
                    all_scanned = True
                # Run vision for scanned PDFs to get person name + multi-doc detection
                # Cost optimization: only run for 2+ pages (multi-doc) OR when filename
                # has relational clues (con, vợ, mẹ...) suggesting different person
                _VN_CLUES_FOR_VISION = [
                    'con trai', 'con gái', 'con', 'mẹ', 'vợ', 'bố', 'cha',
                    'chồng', 'anh', 'chị', 'em', 'bà', 'ông',
                ]
                fn_lower_check = fname.lower()
                needs_vision_for_name = any(c in fn_lower_check for c in _VN_CLUES_FOR_VISION)
                should_run_vision = has_scanned_pages and (total_pages >= 2 or needs_vision_for_name or all_scanned)
                if should_run_vision:
                    try:
                        vision_results = _vision_detect_pdf_documents(llm, fpath, fname, total_pages)
                        if vision_results:
                            if len(vision_results) > 1:
                                # Check if all results are passport-related (PASSPORT + VISA)
                                # for the same person → treat as ONE passport, don't split
                                _PASSPORT_FAMILY = {'PASSPORT', 'VISA', 'OLD PASSPORT'}
                                vr_types = set()
                                vr_persons = set()
                                for vr in vision_results:
                                    vt = vr.get("doc_type_en", "").upper()
                                    # Normalize: "OLD PASSPORT 2011" → "OLD PASSPORT"
                                    for pf in _PASSPORT_FAMILY:
                                        if vt.startswith(pf):
                                            vr_types.add(pf)
                                            break
                                    else:
                                        vr_types.add(vt)
                                    vr_persons.add(vr.get("person_name", "UNKNOWN").upper())
                                # All passport-family docs for same person → single doc
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
                            # ALWAYS use vision person_name for ai_person (even single-doc)
                            # This is how we find the child's name from a scanned passport
                            vision_person = vision_results[0].get("person_name", "")
                            if vision_person and vision_person not in ("UNKNOWN", "UNKNOWN PERSON"):
                                ai_person = vision_person
                            # Use vision doc_type if better than text-based
                            # For scanned PDFs, text-based only guesses from filename → vision is MORE reliable
                            vision_doc_type = vision_results[0].get("doc_type_en", "")
                            if vision_doc_type:
                                # Always prefer vision for fully-scanned PDFs (text-based just guesses)
                                if all_scanned:
                                    doc_type = vision_doc_type
                                # For partial-scan PDFs, only override if text-based gave generic result
                                elif doc_type in ("DOCUMENT", "UNKNOWN DOCUMENT", "UNKNOWN"):
                                    doc_type = vision_doc_type
                    except QuotaExhaustedError:
                        raise
                    except Exception as e:
                        logging.debug("Ignored: %s", e)  # Vision detection failed, keep original result

            # POST-PROCESSING: enrich doc_type with bank name + period from filename
            doc_type = _enrich_doc_type(doc_type, fname, sub_path)

            # POST-PROCESSING: fix doc_owner (prevent duplicate, detect missing)
            doc_owner = _fix_doc_owner(doc_owner, person_name, fname, doc_type)

            # FALLBACK: if AI returned a different person_name than folder person,
            # use it as doc_owner — BUT ONLY for personal/identity docs
            # (passport, student ID, birth cert). Other docs → folder name only.
            _PERSONAL_DOCS = ['PASSPORT', 'OLD PASSPORT', 'STUDENT ID', 'STUDENT CARD',
                              'BIRTH CERTIFICATE', 'IDENTITY CARD', 'CCCD', 'CITIZEN',
                              'HEALTH INSURANCE', 'PHOTO']
            upper_doc = doc_type.upper()
            is_personal = any(kw in upper_doc for kw in _PERSONAL_DOCS)
            if not doc_owner and ai_person and is_personal:
                ai_person_norm = normalize_vietnamese_name(ai_person)
                if (ai_person_norm and ai_person_norm != "UNKNOWN_PERSON"
                        and not _is_same_person(ai_person_norm, person_name)):
                    doc_owner = ai_person_norm

            # Build suggested name
            doc_type_clean = doc_type.upper().strip()
            doc_type_clean = re.sub(r'[^A-Z0-9]+', '_', doc_type_clean).strip('_')
            out_ext = '.pdf' if ext in IMAGE_EXTS else ext

            # If doc_owner exists (different person), use ONLY owner name
            # e.g. "Hộ chiếu con trai" → NGUYEN_DUC_TRI_PASSPORT.pdf
            if doc_owner:
                owner_clean = re.sub(r'[^A-Z0-9]+', '_', doc_owner.upper().strip()).strip('_')
                suggested_name = f"{owner_clean}_{doc_type_clean}{out_ext}"
            else:
                suggested_name = f"{person_name}_{doc_type_clean}{out_ext}"

            return {
                **file_info,
                "person_name": person_name,
                "doc_type_en": doc_type,
                "doc_owner": doc_owner,
                "suggested_name": suggested_name,
                "needs_split": needs_split,
                "doc_count": doc_count,
                "doc_types": doc_types,
            }
        except Exception as e:
            err_str = str(e).lower()
            is_quota = 'insufficient_quota' in err_str or '429' in err_str or 'rate limit' in err_str
            if is_quota:
                _quota_stop.set()  # Signal all other threads to stop
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

    all_results = []
    folders_output = []

    # Setup progress tracking
    total_files = sum(len(fd["files"]) for fd in folders_data.values())
    _precheck_progress.update({"total": total_files, "done": 0, "current_file": "", "running": True})

    # Build flat list of (file_info, person_name, folder_key) for sequential submit
    all_tasks = []
    for folder_key, folder_data in folders_data.items():
        for file_info in folder_data["files"]:
            all_tasks.append((file_info, folder_data["person_name"], folder_key))

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_map = {}
        for file_info, person_name, folder_key in all_tasks:
            if _quota_stop.is_set():
                # Quota exhausted — skip remaining, mark as quota error
                all_results.append({
                    **file_info,
                    "person_name": person_name,
                    "doc_type_en": "QUOTA ERROR",
                    "doc_owner": "",
                    "suggested_name": file_info["filename"],
                    "needs_split": False,
                    "doc_count": 1,
                    "doc_types": ["ERROR"],
                    "error": "Skipped: API quota exhausted",
                    "quota_error": True,
                })
                continue
            future = executor.submit(_classify_one, file_info, person_name)
            future_map[future] = (folder_key, file_info, person_name)

        for future in as_completed(future_map):
            result = future.result()
            folder_key, file_info, person_name = future_map[future]
            # Update progress for frontend polling
            _precheck_progress["done"] = _precheck_progress.get("done", 0) + 1
            _precheck_progress["current_file"] = file_info["filename"]
            all_results.append(result)
            # If quota just got exhausted, cancel remaining pending futures
            if _quota_stop.is_set():
                for pending in future_map:
                    pending.cancel()

    # Group results back by folder
    folder_results = {}
    for r in all_results:
        # Find which folder this file belongs to
        for folder_key, folder_data in folders_data.items():
            if any(f["path"] == r["path"] for f in folder_data["files"]):
                if folder_key not in folder_results:
                    folder_results[folder_key] = {
                        "folder_name": folder_data["folder_name"],
                        "person_name": folder_data["person_name"],
                        "files": [],
                    }
                folder_results[folder_key]["files"].append(r)
                break

    # Handle duplicate suggested names within each folder
    for folder_key, folder_data in folder_results.items():
        name_counts = {}
        for f in sorted(folder_data["files"], key=lambda x: x["filename"]):
            sname = f["suggested_name"]
            if sname in name_counts:
                name_counts[sname] += 1
                base, ext = os.path.splitext(sname)
                f["suggested_name"] = f"{base}_({name_counts[sname]}){ext}"
            else:
                name_counts[sname] = 0

    # Sort files within each folder
    for folder_data in folder_results.values():
        folder_data["files"].sort(key=lambda x: x["filename"])

    folders_output = sorted(folder_results.values(), key=lambda x: x["folder_name"])

    total_files = sum(len(f["files"]) for f in folders_output)
    multi_count = sum(1 for r in all_results if r.get("needs_split"))
    quota_errors = sum(1 for r in all_results if r.get("quota_error"))

    # Reset progress
    _precheck_progress.update({"total": total_files, "done": total_files, "current_file": "", "running": False})

    return jsonify({
        "status": "done",
        "input_dir": input_dir,
        "total_files": total_files,
        "multi_doc_count": multi_count,
        "clean_count": total_files - multi_count,
        "folders": folders_output,
        "quota_exhausted": quota_errors > 0,
        "quota_error_count": quota_errors,
    })


@precheck_bp.post("/api/processor/apply-rename")
def processor_apply_rename():
    """Rename files in-place within input/ subfolders. Converts images to PDF."""
    payload = request.get_json(force=True) or {}
    renames = payload.get("renames", [])

    if not renames:
        return jsonify({"error": "no_renames_provided"}), 400

    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    renamed = []
    errors = []

    for item in renames:
        old_path = item.get("path", "")
        new_name = item.get("new_name", "")

        if not old_path or not new_name:
            errors.append({"path": old_path, "error": "missing path or new_name"})
            continue

        if not os.path.isfile(old_path):
            errors.append({"path": old_path, "error": "file_not_found"})
            continue

        parent_dir = os.path.dirname(old_path)
        old_ext = os.path.splitext(old_path)[1].lower()
        new_ext = os.path.splitext(new_name)[1].lower()
        needs_convert = (old_ext in IMAGE_EXTS and new_ext == '.pdf')

        new_path = os.path.join(parent_dir, new_name)

        # Handle duplicate: add suffix
        if os.path.exists(new_path) and not os.path.samefile(old_path, new_path):
            base, ext = os.path.splitext(new_name)
            idx = 1
            while os.path.exists(new_path):
                new_path = os.path.join(parent_dir, f"{base}_({idx}){ext}")
                idx += 1

        try:
            if needs_convert:
                # Convert image → PDF using Pillow
                from PIL import Image
                img = Image.open(old_path)
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                img.save(new_path, 'PDF', resolution=150)
                img.close()
                os.remove(old_path)  # Remove original image
            else:
                os.rename(old_path, new_path)
            renamed.append({
                "old": os.path.basename(old_path),
                "new": os.path.basename(new_path),
                "path": new_path,
                "converted": needs_convert,
            })
        except Exception as e:
            errors.append({"path": old_path, "error": str(e)})

    return jsonify({
        "status": "done",
        "renamed_count": len(renamed),
        "error_count": len(errors),
        "renamed": renamed,
        "errors": errors,
    })


@precheck_bp.post("/api/processor/merge-files")
def processor_merge_files():
    """Merge multiple files (images + PDFs) into a single PDF in user-specified order."""
    payload = request.get_json(force=True) or {}
    file_paths = payload.get("files", [])  # ordered list of file paths
    output_name = payload.get("output_name", "merged.pdf")

    if len(file_paths) < 2:
        return jsonify({"error": "need_at_least_2_files"}), 400

    from pypdf import PdfWriter, PdfReader
    from PIL import Image
    import tempfile

    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
    writer = PdfWriter()
    tmp_files = []

    try:
        for fpath in file_paths:
            if not os.path.isfile(fpath):
                return jsonify({"error": f"file_not_found: {fpath}"}), 404
            ext = os.path.splitext(fpath)[1].lower()
            if ext in IMAGE_EXTS:
                # Convert image to temp PDF page
                img = Image.open(fpath)
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                tmp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
                img.save(tmp_pdf.name, 'PDF', resolution=150)
                img.close()
                tmp_files.append(tmp_pdf.name)
                reader = PdfReader(tmp_pdf.name)
                for page in reader.pages:
                    writer.add_page(page)
            elif ext == '.pdf':
                reader = PdfReader(fpath)
                for page in reader.pages:
                    writer.add_page(page)
            else:
                return jsonify({"error": f"unsupported_format: {ext}"}), 400

        # Output path = same folder as first file
        parent_dir = os.path.dirname(file_paths[0])
        if not output_name.lower().endswith('.pdf'):
            output_name += '.pdf'
        output_path = os.path.join(parent_dir, output_name)

        # Handle duplicate
        if os.path.exists(output_path):
            base, ext = os.path.splitext(output_name)
            idx = 1
            while os.path.exists(os.path.join(parent_dir, f"{base}_({idx}){ext}")):
                idx += 1
            output_path = os.path.join(parent_dir, f"{base}_({idx}){ext}")

        with open(output_path, 'wb') as out:
            writer.write(out)

        # Delete original source files after successful merge
        deleted_files = []
        output_abs = os.path.abspath(output_path)
        for fpath in file_paths:
            src_abs = os.path.abspath(fpath)
            if src_abs == output_abs:
                continue  # don't delete the output file itself
            try:
                os.remove(fpath)
                deleted_files.append(os.path.basename(fpath))
            except Exception as del_err:
                print(f"[merge] Warning: could not delete {fpath}: {del_err}")

        return jsonify({
            "status": "done",
            "output_path": output_path,
            "output_name": os.path.basename(output_path),
            "total_pages": len(writer.pages),
            "merged_count": len(file_paths),
            "deleted_files": deleted_files,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        for tf in tmp_files:
            try:
                os.remove(tf)
            except Exception as e:
                logging.debug("Ignored error: %s", e)


