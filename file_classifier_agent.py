from __future__ import annotations

import json
import os
import re
import shutil
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pypdf import PdfReader, PdfWriter

from agents import extract_text_with_openai
from prompts import SYSTEM_BASE


def _sanitize_name(value: str, fallback: str) -> str:
    text = (value or "").strip()
    text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback


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


def _build_split_pdf_prompt(filename: str, page_texts: List[str]) -> str:
    snippets: List[str] = []
    for idx, txt in enumerate(page_texts, 1):
        short = txt
        if len(short) > 1200:
            short = short[:1000] + "\n...[TRUNCATED]...\n" + short[-180:]
        snippets.append(f"[PAGE {idx}]\n{short}")

    return f"""Bạn là AI nhận diện hồ sơ visa trong 1 file PDF có thể chứa nhiều giấy tờ.

Nhiệm vụ:
- Xác định file có bao nhiêu giấy tờ.
- Với mỗi giấy tờ, chỉ ra khoảng trang start_page/end_page (tính từ 1).
- Cho biết giấy tờ đó thuộc về ai (person_name).
- Đặt loại giấy tờ bằng TIẾNG ANH (doc_type_en), ví dụ:
  PASSPORT, CITIZEN IDENTITY CARD, BIRTH CERTIFICATE, BANK STATEMENT, HOTEL BOOKING CONFIRMATION

Trả về JSON hợp lệ duy nhất:
{{
  "documents": [
    {{
      "person_name": "Nguyen Thi Bao Tam",
      "doc_type_en": "BIRTH CERTIFICATE",
      "start_page": 1,
      "end_page": 1
    }}
  ]
}}

Quy tắc:
- Không để overlap trang giữa các giấy tờ.
- Phải theo thứ tự trang tăng dần.
- Nếu chỉ có 1 giấy tờ thì trả 1 mục bao phủ toàn bộ file.
- Không bịa thông tin. Nếu không chắc person_name thì dùng "UNKNOWN PERSON".

Tên file: {filename}
Nội dung theo trang:
{chr(10).join(snippets)}
"""


def _detect_pdf_documents(llm: Any, filename: str, page_texts: List[str]) -> List[Dict[str, Any]]:
    if not page_texts:
        return []
    prompt = _build_split_pdf_prompt(filename, page_texts)
    result = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
    try:
        parsed = json.loads(result.content or "")
    except Exception:
        return []
    docs = parsed.get("documents")
    if not isinstance(docs, list):
        return []
    max_page = len(page_texts)
    output: List[Dict[str, Any]] = []
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
        output.append(
            {
                "person_name": _sanitize_name(str(item.get("person_name") or ""), "UNKNOWN PERSON"),
                "doc_type_en": _sanitize_name(str(item.get("doc_type_en") or ""), "DOCUMENT"),
                "start_page": s,
                "end_page": e,
            }
        )
    output.sort(key=lambda x: (x["start_page"], x["end_page"]))
    return output


def _build_identify_prompt(filename: str, text: str) -> str:
    content = (text or "").strip()
    if len(content) > 12000:
        content = content[:8000] + "\n...[TRUNCATED]...\n" + content[-3000:]
    return f"""Bạn là AI nhận diện loại giấy tờ visa và chủ thể giấy tờ.

Trả về JSON hợp lệ duy nhất:
{{
  "person_name": "Nguyen Thi Bao Tam",
  "doc_type_en": "BIRTH CERTIFICATE",
  "reason": "short reason"
}}

Quy tắc:
- person_name: tên người mà giấy tờ thuộc về.
- doc_type_en: loại giấy tờ bằng tiếng Anh, in hoa, ngắn gọn.
- Không bịa thông tin; nếu không chắc tên người dùng "UNKNOWN PERSON".

Tên file: {filename}
Nội dung:
{content}
"""


def _identify_document(llm: Any, filename: str, text: str) -> Optional[Dict[str, str]]:
    prompt = _build_identify_prompt(filename, text)
    result = llm.invoke([SystemMessage(content=SYSTEM_BASE), HumanMessage(content=prompt)])
    try:
        parsed = json.loads(result.content or "")
    except Exception:
        return None
    person_name = _sanitize_name(str(parsed.get("person_name") or ""), "UNKNOWN PERSON")
    doc_type_en = _sanitize_name(str(parsed.get("doc_type_en") or ""), "DOCUMENT")
    reason = (parsed.get("reason") or "").strip()
    return {"person_name": person_name, "doc_type_en": doc_type_en, "reason": reason}


def _copy_to_output(
    src_path: str, output_dir: str, person_name: str, doc_type_en: str
) -> str:
    person_dir = os.path.join(output_dir, _sanitize_name(person_name, "UNKNOWN PERSON"))
    os.makedirs(person_dir, exist_ok=True)
    ext = os.path.splitext(src_path)[1] or ""
    target = _pick_unique_destination(person_dir, _sanitize_name(doc_type_en, "DOCUMENT"), ext)
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
        out_path = _pick_unique_destination(
            person_dir, _sanitize_name(item["doc_type_en"], "DOCUMENT"), ".pdf"
        )
        with open(out_path, "wb") as f:
            writer.write(f)
        results.append(
            {
                "filename": os.path.basename(src_path),
                "pages": f"{s}-{e}",
                "person_name": item["person_name"],
                "doc_type_en": item["doc_type_en"],
                "to": os.path.relpath(out_path, output_dir).replace("\\", "/"),
            }
        )
    return results


def classify_files_in_folder(
    input_dir: str,
    output_dir: str,
    model: str = "gpt-5-mini",
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

    for src_path in files:
        filename = os.path.basename(src_path)
        ext = os.path.splitext(filename)[1].lower()

        if ext == ".pdf":
            try:
                page_texts = _extract_pdf_pages_text(src_path)
            except Exception:
                skipped.append(filename)
                continue
            docs = _detect_pdf_documents(llm, filename, page_texts)
            if len(docs) >= 2:
                split_results = _split_and_copy_pdf(src_path, output_dir, docs)
                if split_results:
                    split_logs.append(
                        {
                            "source_file": filename,
                            "detected_documents": len(split_results),
                            "outputs": split_results,
                        }
                    )
                    for item in split_results:
                        person_counts[item["person_name"]] = person_counts.get(item["person_name"], 0) + 1
                        copied.append(
                            {
                                "source": filename,
                                "person_name": item["person_name"],
                                "doc_type_en": item["doc_type_en"],
                                "to": item["to"],
                            }
                        )
                    continue

        try:
            text = extract_text_with_openai(llm, src_path)
        except Exception:
            text = ""
        identified = _identify_document(llm, filename, text)
        if not identified:
            skipped.append(filename)
            continue
        try:
            out_path = _copy_to_output(
                src_path,
                output_dir,
                identified["person_name"],
                identified["doc_type_en"],
            )
        except Exception:
            skipped.append(filename)
            continue

        person_counts[identified["person_name"]] = person_counts.get(identified["person_name"], 0) + 1
        copied.append(
            {
                "source": filename,
                "person_name": identified["person_name"],
                "doc_type_en": identified["doc_type_en"],
                "to": os.path.relpath(out_path, output_dir).replace("\\", "/"),
            }
        )

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

