"""
Document translation routes: bilingual check, OCR+translate, HTML generation.

This is the main entry point that:
1. Imports the shared Blueprint from translate_core
2. Imports sub-modules to register their routes on the Blueprint
3. Contains the SSE streaming route (run_translate_stream)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from flask import Response, jsonify, request

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from core.errors import QuotaExhaustedError

# ─── Import Blueprint and shared state from core ─────────────────────
from routes.translate_core import (
    splitter_translate_bp,
    TRANSLATE_TEMPLATE_DIR,
    TRANSLATE_DEFAULT_TEMPLATE,
    TRANSLATE_OUTPUT_DIR,
    translation_upload_cache,
    _is_quota_error,
    _safe_name,
    _resolve_translate_source_path,
    _ocr_and_translate_document,
    _build_translation_html,
    _build_html_vision_clone,
    _embed_template_images,
    _auto_detect_template,
    _ensure_translate_template_dir,
    _convert_image_to_a4_pdf,
)

# ─── Import sub-modules to register their routes on the Blueprint ────
import routes.translate_stamp   # noqa: F401 — registers stamp/drive routes
import routes.translate_api     # noqa: F401 — registers API/CRUD routes


# =====================================================================
# SSE Streaming Route (main translation pipeline)
# =====================================================================

@splitter_translate_bp.post("/api/translate/run_stream")
def run_translate_stream():
    payload = request.get_json(force=True) or {}
    input_dir = payload.get("input_dir", "input")
    file_ref = (payload.get("file_ref") or "").strip()
    template_name = (payload.get("template_name") or TRANSLATE_DEFAULT_TEMPLATE).strip()
    flow_id = payload.get("flow_id") or 1
    source_lang = (payload.get("source_lang") or "tiếng Việt").strip()
    ocr_model = payload.get("ocr_model") or "gpt-5-mini"
    translate_model = payload.get("translate_model") or "gpt-5-mini"

    if not file_ref:
        return jsonify({"error": "missing_file_ref"}), 400

    _ensure_translate_template_dir()
    is_auto_template = template_name.lower() in ("auto", "")
    if not is_auto_template:
        template_name = _safe_name(template_name) or TRANSLATE_DEFAULT_TEMPLATE
        template_path = os.path.abspath(os.path.join(TRANSLATE_TEMPLATE_DIR, template_name))
        template_root = os.path.abspath(TRANSLATE_TEMPLATE_DIR)
        if not template_path.startswith(template_root) or not os.path.exists(template_path):
            return jsonify({"error": "template_not_found"}), 404

    source_path = _resolve_translate_source_path(input_dir, file_ref)
    if not source_path:
        return jsonify({"error": "file_not_found"}), 404
        
    # User requested: Automatically convert input images to A4 PDF
    # so that the AI layout and HTML mapper don't overflow the page bounds.
    ext = os.path.splitext(source_path)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"):
        try:
            source_path = _convert_image_to_a4_pdf(source_path)
        except Exception as e:
            logging.exception("Failed to convert image to A4 PDF: %s", e)
            # Proceeding with original image if it fails

    upload_token = ""
    if file_ref.startswith("upload_token:"):
        upload_token = file_ref.split(":", 1)[1].strip()

    def generate():
        nonlocal template_name
        def send_event(step: int, msg: str, data: Optional[Dict[str, Any]] = None):
            evt: Dict[str, Any] = {"step": step, "msg": msg}
            if data is not None:
                evt["data"] = data
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

        try:
            # Step 1: OCR + Translate combined (per-page parallel)
            yield from send_event(1, "⏳ Đang OCR + Dịch tài liệu...")
            llm_ocr = ChatOpenAI(model=ocr_model, temperature=0)
            page_events: List[str] = []

            def on_page(page_idx: int, total: int) -> None:
                page_events.append(f"data: {json.dumps({'step': 1, 'msg': f'⏳ OCR+Dịch trang {page_idx}/{total}...'}, ensure_ascii=False)}\n\n")

            translated_text, layout_descriptions, page_images = _ocr_and_translate_document(llm_ocr, source_path, source_lang=source_lang, page_callback=on_page)
            # Yield page progress events
            for pe in page_events:
                yield pe
            if not translated_text.strip():
                yield from send_event(-1, "❌ Không trích xuất/dịch được từ file")
                return

            # Vietnamese text validation — check for leftover Vietnamese chars
            import re as _re
            viet_chars = _re.findall(r'[àáạảãăắằặẳẵâấầậẩẫèéẹẻẽêếềệểễìíịỉĩòóọỏõôốồộổỗơớờợởỡùúụủũưứừựửữỳýỵỷỹđÀÁẠẢÃĂẮẰẶẲẴÂẤẦẬẨẪÈÉẸẺẼÊẾỀỆỂỄÌÍỊỈĨÒÓỌỎÕÔỐỒỘỔỖƠỚỜỢỞỠÙÚỤỦŨƯỨỪỰỬỮỲÝỴỶỸĐ]', translated_text)
            if len(viet_chars) > 5:  # More than 5 Vietnamese chars = needs cleanup
                yield from send_event(1, "🔄 Phát hiện tiếng Việt còn sót, đang sửa...")
                llm_fix = ChatOpenAI(model=translate_model, temperature=0)
                fix_prompt = (
                    "The following text should be 100% English but contains some Vietnamese words/phrases. "
                    "Translate ALL remaining Vietnamese text to English. Keep the structure and formatting intact. "
                    "Output ONLY the corrected English text:\n\n" + translated_text
                )
                try:
                    fix_result = llm_fix.invoke([SystemMessage(content="Fix Vietnamese text remnants. Output pure English."), HumanMessage(content=fix_prompt)])
                    fixed = (fix_result.content or "").strip()
                    if fixed:
                        translated_text = fixed
                except Exception as e:
                    logging.debug("Vietnamese fix failed (non-fatal): %s", e)

            yield from send_event(1, "✅ OCR + Dịch hoàn tất")

            # Auto-detect template from translated text if needed
            use_vision_clone = False
            if is_auto_template:
                template_name = _auto_detect_template(translated_text)
                # If auto-detect falls back to default template AND we have page images,
                # use Vision Layout Clone with resized images (1024px JPEG = ~55% cheaper)
                if template_name == TRANSLATE_DEFAULT_TEMPLATE and page_images:
                    use_vision_clone = True
                    yield from send_event(1, "🎨 Không tìm thấy template phù hợp → Dùng Vision Clone layout gốc")
                else:
                    yield from send_event(1, f"🔍 Tự động chọn template: {template_name}")

            # Step 2: Build HTML
            if use_vision_clone:
                # Vision Layout Clone: send RESIZED page images + translated text
                yield from send_event(2, "🎨 Đang clone layout từ ảnh gốc (ảnh đã nén 1024px)...")
                llm_vision = ChatOpenAI(model=translate_model, temperature=0)
                html_result = _build_html_vision_clone(llm_vision, translated_text, page_images)
            else:
                # Template-based: use the matched template
                tpl_path = os.path.abspath(os.path.join(TRANSLATE_TEMPLATE_DIR, template_name))
                tpl_root = os.path.abspath(TRANSLATE_TEMPLATE_DIR)
                if not tpl_path.startswith(tpl_root) or not os.path.exists(tpl_path):
                    tpl_path = os.path.join(TRANSLATE_TEMPLATE_DIR, TRANSLATE_DEFAULT_TEMPLATE)
                if os.path.isfile(tpl_path):
                    with open(tpl_path, "r", encoding="utf-8") as f:
                        template_html = f.read()
                else:
                    logging.warning("Template not found: %s, using inline fallback", tpl_path)
                    template_html = (
                        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
                        '<title>Translated Document</title>'
                        '<style>body{font-family:"Times New Roman",serif;padding:20px;max-width:800px;margin:auto;}'
                        '.doc-content{white-space:pre-wrap;line-height:1.7;font-size:14px;}</style></head>'
                        '<body><div class="doc-content">{{CONTENT}}</div></body></html>'
                    )
                yield from send_event(2, "⏳ Đang tạo HTML theo template...")
                llm_translate = ChatOpenAI(model=translate_model, temperature=0)
                html_result = _build_translation_html(
                    llm_translate,
                    translated_text,
                    template_html,
                    translated_text,
                )

            if not html_result.strip():
                yield from send_event(-1, "❌ Không tạo được HTML")
                return
            # Embed local template images (e.g. Emblem_of_Vietnam.png) as base64
            html_result = _embed_template_images(html_result)
            yield from send_event(2, "✅ Tạo HTML hoàn tất")

            file_stem = os.path.splitext(os.path.basename(source_path))[0]
            safe_stem = _safe_name(file_stem) or "translated_document"
            out_dir = os.path.join(TRANSLATE_OUTPUT_DIR, f"flow_{flow_id}")
            os.makedirs(out_dir, exist_ok=True)

            translated_path = os.path.join(out_dir, f"{safe_stem}.translated.txt")
            html_path = os.path.join(out_dir, f"{safe_stem}.translated.html")
            with open(translated_path, "w", encoding="utf-8") as f:
                f.write(translated_text)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_result)

            yield from send_event(
                3,
                "✅ Hoàn tất",
                {
                    "translated_text": translated_text,
                    "html": html_result,
                    "paths": {
                        "translated_path": translated_path,
                        "html_path": html_path,
                    },
                },
            )
        except QuotaExhaustedError as qe:
            yield from send_event(-1, f"⚠️ HẾT QUOTA OpenAI! {str(qe)}")
        except Exception as e:
            logging.exception("[Safe Log] SSE stream error: %s", e)
            # Check if it's a quota error in disguise
            if _is_quota_error(e):
                yield from send_event(-1, "⚠️ HẾT QUOTA OpenAI! Vui lòng kiểm tra billing tại https://platform.openai.com/account/billing")
            else:
                yield from send_event(-1, f"❌ Lỗi: {str(e)}")
        finally:
            # Clear in-memory cache entry (but do NOT delete persistent file on disk)
            # File cleanup happens only when user explicitly deletes the flow
            if upload_token:
                translation_upload_cache.pop(upload_token, None)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
