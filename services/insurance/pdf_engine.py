from __future__ import annotations
import re
import fitz
# Helper: Extract editable fields from PDF with full metadata
# ══════════════════════════════════════════════════════════════════

def _extract_fields_from_pdf(pdf_path: str) -> dict:
    """
    Read a PDF and extract every text span with its:
      - text content
      - exact position (x, y, width, height bounding box)
      - font name, size, color
      - page number
    Returns a structured dict ready for JSON serialization.
    """
    doc = fitz.open(pdf_path)
    pages_data = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_dict = page.get_text("dict")
        spans_list = []

        for block in page_dict["blocks"]:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    bbox = span["bbox"]  # (x0, y0, x1, y1)
                    spans_list.append({
                        "text": text,
                        "bbox": [round(v, 2) for v in bbox],
                        "font": span["font"],
                        "size": round(span["size"], 1),
                        "color": span["color"],  # int RGB
                        "flags": span["flags"],
                    })

        pages_data.append({
            "page": page_idx + 1,
            "width": round(page.rect.width, 2),
            "height": round(page.rect.height, 2),
            "spans": spans_list,
        })

    doc.close()
    return {"pages": pages_data, "total_pages": len(pages_data)}


def _identify_editable_fields(full_data: dict) -> list[dict]:
    """
    From the raw span data, identify the key editable fields that users
    would want to modify (name, DOB, passport, dates, premium, etc.).
    Returns a simplified list of {field, value, page, span_index}.
    """
    editable = []
    # Patterns to identify interesting data fields
    patterns = [
        # Personal info
        (r"^[A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+$", "insured_name"),
        (r"^\d{2}/\d{2}/\d{4}$", "date_field"),
        (r"^[A-Z]\d{7,8}$", "passport_no"),
        (r"^CWTVN[A-Z0-9]+$", "policy_no"),
        (r"^VND[\d.,]+$", "premium"),
        (r"^Mr$|^Ms$|^Mrs$", "gender"),
        # General pattern: anything that looks like a value cell
    ]

    for page_data in full_data["pages"]:
        for idx, span in enumerate(page_data["spans"]):
            text = span["text"]
            for pattern, field_type in patterns:
                if re.match(pattern, text):
                    editable.append({
                        "field_type": field_type,
                        "value": text,
                        "page": page_data["page"],
                        "span_index": idx,
                        "bbox": span["bbox"],
                        "font": span["font"],
                        "size": span["size"],
                    })
                    break

    return editable


def _build_extraction_summary(full_data: dict) -> dict:
    """
    Build a human-readable summary by scanning all spans across all pages.
    Uses multiple strategies to reliably extract key fields.
    """
    # Collect ALL spans across all pages in order
    all_spans = []
    for page_data in full_data["pages"]:
        for span in page_data["spans"]:
            all_spans.append(span["text"])

    joined = "\n".join(all_spans)
    summary = {}

    # ── Strategy 1: Direct span matching (most reliable) ──────────
    for span_text in all_spans:
        text = span_text.strip()

        # Policy number (S-TAI-... or CWTVN...)
        if not summary.get("policy_no"):
            if re.match(r"^S-[A-Z]{3}-\d+-\d+-\d+$", text) or re.match(r"^CWTVN[A-Z0-9]+$", text):
                summary["policy_no"] = text

        # Full name in ALL CAPS with 2+ words (skip labels/headers)
        if not summary.get("insured_name"):
            if (re.match(r"^[A-Z]{2,}( [A-Z]{2,}){1,4}$", text) and
                len(text) > 8 and
                text not in ("CERTIFICATE OF INSURANCE", "LIBERTY INSURANCE LIMITED",
                             "TO WHOM IT MAY CONCERN", "TRAVEL INDIVIDUAL",
                             "TRAN QUANG KHAI TAN DINH")):
                summary["insured_name"] = text

        # Plan/coverage type
        if not summary.get("plan"):
            if text in ("Classic", "Gold", "Silver", "Platinum",
                        "GOLD", "SILVER", "PLATINUM", "CLASSIC"):
                summary["plan"] = text

        # Nationality
        if not summary.get("nationality"):
            if text in ("Vietnamese", "American", "British", "Chinese",
                        "Japanese", "Korean", "Australian", "Canadian"):
                summary["nationality"] = text

        # Category
        if not summary.get("category"):
            if text in ("Individual", "Family", "Group",
                        "Cá nhân", "Gia đình"):
                summary["category"] = text

    # ── Strategy 1.5: Span adjacency (label→value pairs) ─────────
    # For PDFs where labels and values are sequential spans
    for i, span_text in enumerate(all_spans):
        text = span_text.strip()

        # Name: "Name /" or "Tên" followed by actual name
        if not summary.get("insured_name") and re.match(r"^(Name\s*/|Tên)$", text):
            for j in range(i + 1, min(i + 5, len(all_spans))):
                candidate = all_spans[j].strip()
                if candidate and len(candidate) > 3 and not re.match(r"^(Address|Địa chỉ|Name|Tên)", candidate):
                    # Mixed case name like "Tran Quan Vinh"
                    if re.match(r"^[A-Z][a-z]+(\s+[A-Z][a-z]+)+$", candidate):
                        summary["insured_name"] = candidate
                        break

        # Issued date
        if not summary.get("issued_date") and re.match(r"^(Issued Date|Ngày cấp)", text, re.IGNORECASE):
            for j in range(i + 1, min(i + 5, len(all_spans))):
                date_m = re.match(r"^(\d{2}/\d{2}/\d{4})$", all_spans[j].strip())
                if date_m:
                    summary["issued_date"] = date_m.group(1)
                    break

        # Period dates from adjacent spans
        if not summary.get("period_from") and re.match(r"^(From|Từ)$", text, re.IGNORECASE):
            for j in range(i + 1, min(i + 5, len(all_spans))):
                date_m = re.match(r"^(\d{2}/\d{2}/\d{4})$", all_spans[j].strip())
                if date_m:
                    summary["period_from"] = date_m.group(1)
                    break

        if not summary.get("period_to") and re.match(r"^(To|đến)$", text, re.IGNORECASE):
            for j in range(i + 1, min(i + 5, len(all_spans))):
                date_m = re.match(r"^(\d{2}/\d{2}/\d{4})$", all_spans[j].strip())
                if date_m:
                    summary["period_to"] = date_m.group(1)
                    break

        # Total days
        if not summary.get("total_days") and re.match(r"^(Total days|Số ngày)", text, re.IGNORECASE):
            for j in range(i + 1, min(i + 5, len(all_spans))):
                if re.match(r"^\d+$", all_spans[j].strip()):
                    summary["total_days"] = all_spans[j].strip()
                    break

    # ── Strategy 2: Contextual regex on full text ─────────────────
    # DOB
    dob_match = re.search(r"Date of Birth\s*:?\s*(\d{2}/\d{2}/\d{4})", joined, re.IGNORECASE)
    if dob_match:
        summary["dob"] = dob_match.group(1)

    # Passport
    if not summary.get("passport_no"):
        pp_match = re.search(r"Passport\s*No\.?\s*:?\s*([A-Z]\d{7,8})", joined, re.IGNORECASE)
        if pp_match:
            summary["passport_no"] = pp_match.group(1)
        else:
            pp_fallback = re.search(r"\b([A-Z]\d{7,8})\b", joined)
            if pp_fallback:
                summary["passport_no"] = pp_fallback.group(1)

    # Period of coverage: from DD/MM/YYYY until DD/MM/YYYY (fallback)
    if not summary.get("period_from"):
        period_match = re.search(
            r"from\s*(\d{2}/\d{2}/\d{4})\s*(?:.*?)(?:until|to)\s*(\d{2}/\d{2}/\d{4})",
            joined, re.IGNORECASE | re.DOTALL
        )
        if period_match:
            summary["period_from"] = period_match.group(1)
            summary["period_to"] = period_match.group(2)

    # Premium (VND XXX,XXX)
    premium_match = re.search(r"VND\s*[\d,.]+", joined)
    if premium_match:
        summary["total_premium"] = premium_match.group(0).strip().rstrip(".")

    # Region
    if not summary.get("region") and "Worldwide" in joined:
        summary["region"] = "Worldwide"

    # Address — look for the span with street info
    for span_text in all_spans:
        if re.search(r"\d+\s+.*?(Ward|District|City|Street|Phường|Quận|KHAI|HO CHI MINH)", span_text, re.IGNORECASE):
            summary["address"] = span_text.strip()
            break

    # Customer code (8-digit number after "Customer code")
    cc_match = re.search(r"Customer\s*code\s*:?\s*(\d{6,8})", joined, re.IGNORECASE)
    if cc_match:
        summary["customer_code"] = cc_match.group(1)
    else:
        for span_text in all_spans:
            if re.match(r"^\d{8}$", span_text.strip()):
                summary["customer_code"] = span_text.strip()
                break

    # Membership number (IT-XXXXXX-XX)
    for span_text in all_spans:
        if re.match(r"^IT-\d{4,}-\d{2}$", span_text.strip()):
            summary["membership_no"] = span_text.strip()
            break

    # Length of trip — use bounding box Y-proximity instead of span index
    # "23" and "Length of trip" are on the same Y-line but far apart in span order
    if full_data and "pages" in full_data and full_data["pages"]:
        page0_spans = full_data["pages"][0].get("spans", [])
        label_y = None
        for sp in page0_spans:
            if re.match(r"^Length of trip", sp.get("text", ""), re.IGNORECASE):
                bbox = sp.get("bbox", [0, 0, 0, 0])
                label_y = bbox[1]  # y0
                break
        if label_y:
            for sp in page0_spans:
                t = sp.get("text", "").strip()
                bbox = sp.get("bbox", [0, 0, 0, 0])
                sp_y = bbox[1]
                if re.match(r"^\d{1,3}$", t) and abs(sp_y - label_y) < 15:
                    summary["length_of_trip"] = t
                    break

    # ── Strategy 3: Tabular column matching (Chubb page 2 insured table) ──
    # In tabular PDFs, the header "Date of Birth" and value "11/11/1985"
    # are in different rows but the SAME X-column.
    # We find the header's X-range, then look for a date value in a data row
    # that falls within the same X-column.
    if full_data and "pages" in full_data:
        for page_data in full_data["pages"]:
            page_spans = page_data.get("spans", [])

            # --- DOB from table ---
            if not summary.get("dob"):
                dob_header = None
                for sp in page_spans:
                    if re.match(r"^Date of Birth", sp.get("text", ""), re.IGNORECASE):
                        dob_header = sp
                        break
                if dob_header:
                    hx0 = dob_header["bbox"][0]
                    hx1 = dob_header["bbox"][2]
                    hy1 = dob_header["bbox"][3]
                    for sp in page_spans:
                        t = sp.get("text", "").strip()
                        sx0 = sp["bbox"][0]
                        sy0 = sp["bbox"][1]
                        # Value must be BELOW the header and within the X-column
                        if (re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", t)
                                and sy0 > hy1
                                and abs(sx0 - hx0) < 40):
                            summary["dob"] = t
                            break

            # --- Gender from table ---
            if not summary.get("gender"):
                gender_header = None
                for sp in page_spans:
                    if sp.get("text", "").strip() == "Gender":
                        gender_header = sp
                        break
                if gender_header:
                    hx0 = gender_header["bbox"][0]
                    hy1 = gender_header["bbox"][3]
                    for sp in page_spans:
                        t = sp.get("text", "").strip()
                        sx0 = sp["bbox"][0]
                        sy0 = sp["bbox"][1]
                        if (t in ("Mr", "Ms", "Mrs")
                                and sy0 > hy1
                                and abs(sx0 - hx0) < 40):
                            summary["gender"] = t
                            break

            # --- Period dates from label+column (Chubb template) ---
            # "From" at x0=111.9, y0=382.7 and "19/02/2026" at x0=111.9, y0=396.7
            # Same X-column, ~14px below — span adjacency misses this
            if not summary.get("period_from"):
                from_label = None
                for sp in page_spans:
                    if sp.get("text", "").strip() == "From":
                        from_label = sp
                        break
                if from_label:
                    lx0 = from_label["bbox"][0]
                    ly1 = from_label["bbox"][3]
                    for sp in page_spans:
                        t = sp.get("text", "").strip()
                        sx0 = sp["bbox"][0]
                        sy0 = sp["bbox"][1]
                        if (re.match(r"^\d{2}/\d{2}/\d{4}$", t)
                                and sy0 > ly1
                                and sy0 - ly1 < 25
                                and abs(sx0 - lx0) < 30):
                            summary["period_from"] = t
                            break

            if not summary.get("period_to"):
                to_label = None
                for sp in page_spans:
                    if sp.get("text", "").strip() == "To":
                        to_label = sp
                        break
                if to_label:
                    lx0 = to_label["bbox"][0]
                    ly1 = to_label["bbox"][3]
                    for sp in page_spans:
                        t = sp.get("text", "").strip()
                        sx0 = sp["bbox"][0]
                        sy0 = sp["bbox"][1]
                        if (re.match(r"^\d{2}/\d{2}/\d{4}$", t)
                                and sy0 > ly1
                                and sy0 - ly1 < 25
                                and abs(sx0 - lx0) < 30):
                            summary["period_to"] = t
                            break

    return summary


# ══════════════════════════════════════════════════════════════════
# Helper: Apply edits to PDF using redaction (font + position match)
# ══════════════════════════════════════════════════════════════════

def _find_and_replace_text(page, old_text: str, new_text: str, font_info: dict = None,
                            template_path: str = "chubb", expected_rect=None,
                            page_idx: int = 0):
    """
    Find old_text on a page, redact (erase) it, and insert new_text
    at the exact same position with matching font/size/color.

    font_info: optional dict with {font, size, color} to override
    template_path: helps determine the accurate background color (white vs beige)
    expected_rect: optional fitz.Rect — if provided, only replace instances
                   whose Y-position is within 30px of this rect (prevents
                   collateral damage to phone numbers, dates, etc.)
    page_idx: page number (0-indexed) — only page 0 of Chubb uses beige bg
    """
    text_instances = page.search_for(old_text)
    if not text_instances:
        return False

    # ── Filter: if expected_rect is given, only keep rects near it ──
    if expected_rect is not None:
        TOLERANCE = 30  # pixels
        filtered = [r for r in text_instances
                    if abs(r.y0 - expected_rect.y0) < TOLERANCE
                    and abs(r.x0 - expected_rect.x0) < TOLERANCE]
        if not filtered:
            return False
        text_instances = filtered

    replaced = False
    
    # ── Background Color Config ──
    # Mã màu HEX. Nếu sau này PDF đổi màu, anh chỉ cần sửa chuỗi HEX ở đây
    # Ví dụ: màu cam nhạt của Chubb là "#ffdfbf", trắng là "#ffffff"
    CHUBB_BG_HEX = "#ffdfbf"
    STANDARD_BG_HEX = "#ffffff"

    def hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))

    for rect in text_instances:
        # ── Strategy: Hardcoded precise background colors per template ──
        # Chubb page 0 (certificate) has beige bg in the data fields area (y < 400)
        # Page 1+ (confirmation letter, etc.) always has WHITE background
        if "chubb" in template_path.lower() and page_idx == 0 and rect.y0 < 400:
            fill_color = hex_to_rgb(CHUBB_BG_HEX)
        else:
            fill_color = hex_to_rgb(STANDARD_BG_HEX)

        # Determine font properties for this location
        target_font = "Times-Roman"
        target_size = 10.0
        target_color = (0, 0, 0)

        if font_info:
            target_font = font_info.get("font", target_font)
            target_size = font_info.get("size", target_size)
            color_int = font_info.get("color", 0)
            if isinstance(color_int, int):
                r = ((color_int >> 16) & 0xFF) / 255.0
                g = ((color_int >> 8) & 0xFF) / 255.0
                b = (color_int & 0xFF) / 255.0
                target_color = (r, g, b)
        else:
            # Try to detect font from the span at this location
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        if old_text in span["text"]:
                            target_font = span["font"]
                            target_size = span["size"]
                            color_int = span["color"]
                            r = ((color_int >> 16) & 0xFF) / 255.0
                            g = ((color_int >> 8) & 0xFF) / 255.0
                            b = (color_int & 0xFF) / 255.0
                            target_color = (r, g, b)
                            break

        # Map PDF font name to a usable fontname for insertion
        insert_fontname = _map_font_name(target_font)

        # Redact (erase) old text with matching background fill
        annot = page.add_redact_annot(rect, fill=fill_color)
        page.apply_redactions()

        # Step 2: Calculate text position
        # Check if new text fits in original bounding box
        text_width = fitz.get_text_length(new_text, fontname=insert_fontname, fontsize=target_size)
        box_width = rect.x1 - rect.x0

        adjusted_size = target_size
        if text_width > box_width and box_width > 0:
            # Shrink font to fit
            ratio = box_width / text_width
            adjusted_size = max(target_size * ratio, 4.0)  # minimum 4pt

        # Insert new text at baseline position
        # baseline is approximately at y1 - descent (roughly y0 + ascent)
        baseline_y = rect.y1 - (adjusted_size * 0.15)  # approximate descent
        insert_point = fitz.Point(rect.x0, baseline_y)

        page.insert_text(
            insert_point,
            new_text,
            fontname=insert_fontname,
            fontsize=adjusted_size,
            color=target_color,
        )
        replaced = True

    return replaced


def _map_font_name(pdf_font_name: str) -> str:
    """
    Map embedded PDF font names to PyMuPDF base-14 font names.
    PyMuPDF can only insert text with these standard fonts unless
    we embed custom fonts.
    """
    name_lower = pdf_font_name.lower()

    if "timesnewroman" in name_lower or "times" in name_lower:
        if "bold" in name_lower and "italic" in name_lower:
            return "tibi"  # Times-BoldItalic
        elif "bold" in name_lower:
            return "tibo"  # Times-Bold
        elif "italic" in name_lower:
            return "tiit"  # Times-Italic
        else:
            return "tiro"  # Times-Roman
    elif "arial" in name_lower or "helvetica" in name_lower:
        if "bold" in name_lower:
            return "hebo"
        else:
            return "helv"
    elif "courier" in name_lower:
        return "cour"
    else:
        # Default to Times-Roman (closest to the insurance PDFs)
        return "tiro"


def _apply_changes_to_pdf(template_path: str, changes: dict, output_path: str) -> str:
    """
    Apply a set of field changes to the PDF template.

    changes: dict of {old_value: new_value} pairs
    Returns: path to the output PDF
    """
    doc = fitz.open(template_path)

    # Build a font info map from the original document
    # Store ALL occurrences (multiple pages) WITH their bounding boxes
    font_map = {}  # {text: [{font, size, color, page, bbox}, ...]}
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if text and text in changes:
                        if text not in font_map:
                            font_map[text] = []
                        font_map[text].append({
                            "font": span["font"],
                            "size": span["size"],
                            "color": span["color"],
                            "page": page_idx,
                            "bbox": span["bbox"],
                        })

    # Apply each change
    results = []
    for old_val, new_val in changes.items():
        if old_val == new_val:
            results.append({"field": old_val, "status": "unchanged"})
            continue

        occurrences = font_map.get(old_val, [])
        fi = occurrences[0] if occurrences else None
        success = False

        # ── ALWAYS use position-aware replacement when font_map has data ──
        # This prevents redaction from eating into adjacent text spans.
        # Without expected_rect, page.search_for() can return wider rects
        # that overlap neighboring text (e.g. "Issued04/04/2026áp" garble).
        if occurrences:
            for occ in occurrences:
                pg_idx = occ["page"]
                page = doc[pg_idx]
                expected = fitz.Rect(occ["bbox"])
                # Use this occurrence's own font info for accurate rendering
                if _find_and_replace_text(page, old_val, new_val, occ, template_path,
                                          expected_rect=expected, page_idx=pg_idx):
                    success = True
        else:
            # Fallback: no font_map data, search every page unrestricted
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                if _find_and_replace_text(page, old_val, new_val, fi, template_path,
                                          page_idx=page_idx):
                    success = True

        results.append({
            "field": old_val,
            "new_value": new_val,
            "status": "replaced" if success else "not_found",
        })

    doc.save(output_path)
    doc.close()
    return results


# ══════════════════════════════════════════════════════════════════
