"""
Validator – Zero-cost document completeness checker.

Reads file names only (no AI calls), strips Vietnamese diacritics,
and matches against alias dictionaries defined in rules.json.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Path to rules.json (sits next to this file)
# ---------------------------------------------------------------------------
_RULES_PATH = Path(__file__).parent / "rules.json"


def _load_rules() -> dict[str, Any]:
    """Load and cache rules from JSON config."""
    with open(_RULES_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Vietnamese diacritics removal
# ---------------------------------------------------------------------------
_VIET_MAP = str.maketrans(
    "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
    "ÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ",
    "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"
    "AAAAAAAAAAAAAAAAAEEEEEEEEEEEIIIIIOOOOOOOOOOOOOOOOOUUUUUUUUUUUYYYYYD",
)


def normalize(text: str) -> str:
    """
    Normalise a Vietnamese string for keyword matching.

    1. Unicode NFC normalisation
    2. Vietnamese diacritics → ASCII
    3. Lowercase
    4. Strip non-alphanumeric (keep spaces)
    5. Collapse multiple spaces
    """
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_VIET_MAP)
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Country detection from folder name
# ---------------------------------------------------------------------------
def detect_country(folder_name: str, rules: dict) -> str | None:
    """
    Extract country code from a folder name.

    Folder format: ``UC - CHU HIEP CO CHINH - NHAN``
    The first segment before the first dash is the country token.
    Returns the country key (e.g. ``"UC"``, ``"CANADA"``, ``"MY"``)
    or *None* if unrecognised.
    """
    # Lấy phần đầu tiên trước dấu "-"
    first_segment = folder_name.split("-")[0].strip()
    normalised = normalize(first_segment)

    for code, info in rules.get("country_rules", {}).items():
        for alias in info.get("aliases", []):
            if normalize(alias) == normalised:
                return code
    return None


# ---------------------------------------------------------------------------
# File → category classification
# ---------------------------------------------------------------------------
def classify_file(filename: str, rules: dict) -> str | None:
    """
    Classify a single file into a document category by matching its
    name against the alias dictionary.

    Uses word-boundary matching to avoid false positives
    (e.g. alias ``"don"`` must NOT match inside ``"dong"``).

    Returns the category key (e.g. ``"passport"``) or *None*.
    """
    name_normalised = normalize(Path(filename).stem)  # strip extension
    ext = Path(filename).suffix.lower()

    categories: dict = rules.get("categories", {})

    # Score each category: longer alias matches win (more specific)
    best_match: str | None = None
    best_alias_len = 0

    for cat_key, cat_info in categories.items():
        for alias in cat_info.get("aliases", []):
            alias_norm = normalize(alias)

            # Word-boundary match: alias must appear as whole word(s)
            pattern = r"(?:^|\s)" + re.escape(alias_norm) + r"(?:\s|$)"
            if not re.search(pattern, f" {name_normalised} "):
                continue

            # Check file extension if restricted
            allowed_ext = cat_info.get("extensions", [])
            if allowed_ext and ext not in allowed_ext:
                continue

            # Prefer the LONGEST alias match (more specific wins)
            if len(alias_norm) > best_alias_len:
                best_alias_len = len(alias_norm)
                best_match = cat_key

    return best_match


def classify_files(filenames: list[str], rules: dict) -> dict[str, list[str]]:
    """
    Classify a list of filenames into categories.

    Returns a dict mapping ``category_key -> [matching filenames]``.
    Files that don't match any category are stored under ``"unknown"``.
    """
    result: dict[str, list[str]] = {}
    for fn in filenames:
        cat = classify_file(fn, rules)
        key = cat or "unknown"
        result.setdefault(key, []).append(fn)
    return result


# ---------------------------------------------------------------------------
# Core validation logic
# ---------------------------------------------------------------------------
def validate_folder(
    folder_name: str,
    filenames: list[str],
    rules: dict | None = None,
) -> dict[str, Any]:
    """
    Validate a folder's documents against country-specific rules.

    Parameters
    ----------
    folder_name : str
        The Google Drive folder name, e.g.
        ``"UC - CHU HIEP CO CHINH - NHAN - DONE"``
    filenames : list[str]
        List of file names inside the folder.
    rules : dict, optional
        Pre-loaded rules dict.  If *None*, loads from ``rules.json``.

    Returns
    -------
    dict with keys:
        - ``valid`` (bool): True if all requirements met.
        - ``country`` (str | None): Detected country code.
        - ``country_label`` (str): Human readable country name.
        - ``matched`` (dict): ``{category_key: [filenames]}``.
        - ``missing`` (list[str]): List of missing category labels.
        - ``missing_keys`` (list[str]): List of missing category keys.
        - ``conditional_missing`` (list[str]): Conditional rule violations.
        - ``summary`` (str): Human-readable summary for folder rename.
    """
    if rules is None:
        rules = _load_rules()

    country = detect_country(folder_name, rules)
    country_info = rules.get("country_rules", {}).get(country or "", {})
    country_label = country_info.get("label", "Không xác định")
    required_cats: list[str] = country_info.get("required_categories", [])

    # Classify all files
    matched = classify_files(filenames, rules)

    # --- Check required categories ---
    missing_keys: list[str] = []
    missing_labels: list[str] = []

    for cat_key in required_cats:
        if cat_key not in matched:
            cat_label = rules["categories"].get(cat_key, {}).get("label", cat_key)
            missing_keys.append(cat_key)
            missing_labels.append(cat_label)

    # --- Check conditional rules ---
    conditional_missing: list[str] = []
    for rule in rules.get("conditional_rules", []):
        trigger_key = rule["if_present"]
        require_key = rule["then_require"]

        if trigger_key in matched and require_key not in matched:
            conditional_missing.append(rule["error_message"])
            # Also add to missing if not already there
            if require_key not in missing_keys:
                req_label = rules["categories"].get(require_key, {}).get("label", require_key)
                missing_keys.append(require_key)
                missing_labels.append(req_label)

    # --- Skip validation for countries with no rules (e.g. MY) ---
    if not required_cats:
        return {
            "valid": True,
            "country": country,
            "country_label": country_label,
            "matched": matched,
            "missing": [],
            "missing_keys": [],
            "conditional_missing": [],
            "summary": "Bỏ qua kiểm tra (chưa có Rule)",
        }

    is_valid = len(missing_keys) == 0

    # Build human-readable summary for folder rename
    if is_valid:
        summary = "Đang dịch"
    else:
        joined = ", ".join(missing_labels)
        summary = f"THIẾU ({joined})"

    return {
        "valid": is_valid,
        "country": country,
        "country_label": country_label,
        "matched": matched,
        "missing": missing_labels,
        "missing_keys": missing_keys,
        "conditional_missing": conditional_missing,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Smart validation: Extract person names from flat filenames
# ---------------------------------------------------------------------------
def _extract_person_from_filename(filename: str, rules: dict) -> tuple[str | None, str | None]:
    """
    Extract (doc_category, person_name) from a filename like
    ``CO_CHINH_BIRTH_CERTIFICATE.pdf`` or ``Passport Chu Hiep.pdf``.

    Naming convention: ``[PERSON]_[DOC_TYPE].ext``
    The document type appears at the END of the filename.
    Everything BEFORE it is the person name.

    Returns (category_key, normalised_person_name) or (None, None).
    """
    stem = Path(filename).stem
    stem_norm = normalize(stem)

    categories = rules.get("categories", {})

    best_cat: str | None = None
    best_alias_norm: str = ""
    best_alias_len = 0

    for cat_key, cat_info in categories.items():
        # Check extension
        ext = Path(filename).suffix.lower()
        allowed_ext = cat_info.get("extensions", [])
        if allowed_ext and ext not in allowed_ext:
            continue

        for alias in cat_info.get("aliases", []):
            alias_norm = normalize(alias)
            if not alias_norm:
                continue

            # Strategy 1: Alias at the END of the stem (standard: PERSON_DOCTYPE)
            if stem_norm.endswith(alias_norm):
                if len(alias_norm) > best_alias_len:
                    best_alias_len = len(alias_norm)
                    best_cat = cat_key
                    best_alias_norm = alias_norm
                continue

            # Strategy 2: Alias at the START of the stem (Vietnamese: "passport chu hiep")
            if stem_norm.startswith(alias_norm):
                if len(alias_norm) > best_alias_len:
                    best_alias_len = len(alias_norm)
                    best_cat = cat_key
                    best_alias_norm = alias_norm
                continue

            # Strategy 3: Word-boundary match anywhere (fallback for mixed names)
            pattern = r"(?:^|\s)" + re.escape(alias_norm) + r"(?:\s|$)"
            if re.search(pattern, f" {stem_norm} "):
                if len(alias_norm) > best_alias_len:
                    best_alias_len = len(alias_norm)
                    best_cat = cat_key
                    best_alias_norm = alias_norm

    if not best_cat:
        return None, None

    # Extract person name: remove the matched alias from stem
    # Prefer suffix removal (PERSON_DOCTYPE pattern)
    if stem_norm.endswith(best_alias_norm):
        person_raw = stem_norm[: len(stem_norm) - len(best_alias_norm)].strip()
    elif stem_norm.startswith(best_alias_norm):
        person_raw = stem_norm[len(best_alias_norm):].strip()
    else:
        # Fallback: remove alias from middle
        person_raw = re.sub(
            r"(?:^|\s)" + re.escape(best_alias_norm) + r"(?:\s|$)",
            " ",
            f" {stem_norm} ",
        ).strip()

    # Clean up: remove common noise words and trailing numbers
    person_raw = re.sub(r"\b(cua|cùa|của)\b", "", person_raw).strip()
    person_raw = re.sub(r"\s*\(\d+\)\s*$", "", person_raw).strip()  # strip (1), (2)
    person_raw = re.sub(r"\s+", " ", person_raw).strip()

    if not person_raw:
        person_raw = "__chung__"  # Document for the whole group

    return best_cat, person_raw


def validate_folder_smart(
    folder_name: str,
    filenames: list[str],
    rules: dict | None = None,
) -> dict[str, Any]:
    """
    Smart validation: group files by person using common prefix detection,
    then validate each person individually.

    Strategy:
    1. Classify each file to get its document category.
    2. Group files by person prefix (e.g. CO_CHINH_*, BAC_HIEP_*).
    3. Check each person has all required document categories.

    Uses zero-cost string normalisation (no AI tokens).
    """
    if rules is None:
        rules = _load_rules()

    country = detect_country(folder_name, rules)
    country_info = rules.get("country_rules", {}).get(country or "", {})
    country_label = country_info.get("label", "Không xác định")
    required_cats: list[str] = country_info.get("required_categories", [])

    # Skip countries with no rules
    if not required_cats:
        return {
            "valid": True,
            "country": country,
            "country_label": country_label,
            "persons": {},
            "missing_details": [],
            "summary": "Bỏ qua kiểm tra (chưa có Rule)",
        }

    # Step 1: Classify each file and extract person prefix
    person_cats: dict[str, set[str]] = {}  # person -> set of categories
    all_cats: set[str] = set()

    for fn in filenames:
        cat = classify_file(fn, rules)
        if cat:
            all_cats.add(cat)

        # Try to extract person name from filename prefix
        person = _extract_person_prefix(fn, rules)
        if person and cat:
            person_cats.setdefault(person, set()).add(cat)

    # Step 1b: Check for compound documents (files containing multiple doc types)
    compound_rules = rules.get("compound_documents", {}).get("rules", [])
    for fn in filenames:
        fn_norm = normalize(Path(fn).stem)
        for crule in compound_rules:
            matched = False
            for alias in crule.get("aliases", []):
                alias_norm = normalize(alias)
                if alias_norm and alias_norm in fn_norm:
                    matched = True
                    break
            if matched:
                # Extract person from this compound file
                person = _extract_person_prefix(fn, rules)
                if not person:
                    # Try to guess person from remaining name after compound alias
                    for alias in crule.get("aliases", []):
                        alias_norm = normalize(alias)
                        if alias_norm and alias_norm in fn_norm:
                            remainder = fn_norm.replace(alias_norm, "").strip()
                            if remainder:
                                person = remainder
                            break
                if person:
                    for sat_cat in crule.get("satisfies", []):
                        person_cats.setdefault(person, set()).add(sat_cat)
                        all_cats.add(sat_cat)
                else:
                    # No person detected → add to global all_cats
                    for sat_cat in crule.get("satisfies", []):
                        all_cats.add(sat_cat)

    # Step 2: Merge similar person names (e.g. "co chinh" and "co chinh 1")
    person_cats = _merge_similar_persons(person_cats)

    # Step 3: If no distinct persons detected, do flat validation
    if not person_cats:
        missing_keys = [c for c in required_cats if c not in all_cats]
        if missing_keys:
            missing_labels = [
                rules["categories"].get(k, {}).get("label", k)
                for k in missing_keys
            ]
            return {
                "valid": False,
                "country": country,
                "country_label": country_label,
                "persons": {"__all__": list(all_cats)},
                "missing_details": [{"person": "(Chung)", "missing": missing_labels}],
                "summary": f"THIẾU ({', '.join(missing_labels)})",
            }
        return {
            "valid": True,
            "country": country,
            "country_label": country_label,
            "persons": {"__all__": list(all_cats)},
            "missing_details": [],
            "summary": "Đang dịch",
        }

    # Step 4: Check shared/group documents
    shared_cats = person_cats.pop("__chung__", set())

    # If after removing shared, no real persons left, treat as single group
    if not person_cats:
        combined = shared_cats | all_cats
        missing_keys = [c for c in required_cats if c not in combined]
        if missing_keys:
            missing_labels = [
                rules["categories"].get(k, {}).get("label", k)
                for k in missing_keys
            ]
            return {
                "valid": False,
                "country": country,
                "country_label": country_label,
                "persons": {"__all__": list(combined)},
                "missing_details": [{"person": "(Chung)", "missing": missing_labels}],
                "summary": f"THIẾU ({', '.join(missing_labels)})",
            }
        return {
            "valid": True,
            "country": country,
            "country_label": country_label,
            "persons": {"__all__": list(combined)},
            "missing_details": [],
            "summary": "Đang dịch",
        }

    # Step 5: Validate each person
    all_missing: list[dict] = []
    for person_name, cats in person_cats.items():
        combined = cats | shared_cats
        person_missing = []
        for req in required_cats:
            if req not in combined:
                cat_label = rules["categories"].get(req, {}).get("label", req)
                person_missing.append(cat_label)
        if person_missing:
            display_name = person_name.title()
            all_missing.append({"person": display_name, "missing": person_missing})

    # Step 6: Check conditional rules per person
    for person_name, cats in person_cats.items():
        combined = cats | shared_cats
        for rule in rules.get("conditional_rules", []):
            trigger_key = rule["if_present"]
            require_key = rule["then_require"]
            if trigger_key in combined and require_key not in combined:
                display_name = person_name.title()
                req_label = rules["categories"].get(require_key, {}).get("label", require_key)
                found = False
                for entry in all_missing:
                    if entry["person"] == display_name:
                        if req_label not in entry["missing"]:
                            entry["missing"].append(req_label)
                        found = True
                        break
                if not found:
                    all_missing.append({"person": display_name, "missing": [req_label]})

    is_valid = len(all_missing) == 0

    if is_valid:
        summary = "Đang dịch"
    else:
        parts = []
        for entry in all_missing:
            for doc in entry["missing"]:
                parts.append(f"{doc} ({entry['person']})")
        summary = f"THIẾU ({', '.join(parts)})"

    return {
        "valid": is_valid,
        "country": country,
        "country_label": country_label,
        "persons": {k: list(v) for k, v in person_cats.items()},
        "missing_details": all_missing,
        "summary": summary,
    }


def _extract_person_prefix(filename: str, rules: dict) -> str | None:
    """
    Extract person name from a filename using the PERSON_DOCTYPE naming convention.

    For English-named files (e.g. CO_CHINH_BIRTH_CERTIFICATE.pdf):
      → Match the longest alias at the end, everything before is the person.

    For Vietnamese-named files (e.g. "Sao kê bác Hiệp.pdf"):
      → Match alias anywhere, take remaining as person.
    """
    stem = Path(filename).stem
    stem_norm = normalize(stem)
    categories = rules.get("categories", {})

    best_cat_alias: str = ""
    best_alias_len = 0
    match_position = "none"  # "end", "start", "middle"

    for cat_key, cat_info in categories.items():
        ext = Path(filename).suffix.lower()
        allowed_ext = cat_info.get("extensions", [])
        if allowed_ext and ext not in allowed_ext:
            continue

        for alias in cat_info.get("aliases", []):
            alias_norm = normalize(alias)
            if not alias_norm or len(alias_norm) < 2:
                continue

            # Prefer END match (PERSON_DOCTYPE convention)
            if stem_norm.endswith(alias_norm) and len(alias_norm) > best_alias_len:
                best_alias_len = len(alias_norm)
                best_cat_alias = alias_norm
                match_position = "end"
            # Also try START match (Vietnamese: "passport chu hiep")
            elif stem_norm.startswith(alias_norm) and len(alias_norm) > best_alias_len:
                best_alias_len = len(alias_norm)
                best_cat_alias = alias_norm
                match_position = "start"
            # Fallback: middle match
            elif match_position == "none":
                pattern = r"(?:^|\s)" + re.escape(alias_norm) + r"(?:\s|$)"
                if re.search(pattern, f" {stem_norm} ") and len(alias_norm) > best_alias_len:
                    best_alias_len = len(alias_norm)
                    best_cat_alias = alias_norm
                    match_position = "middle"

    if not best_cat_alias:
        return None

    # Extract person from the appropriate side
    if match_position == "end":
        person = stem_norm[: len(stem_norm) - len(best_cat_alias)].strip()
    elif match_position == "start":
        person = stem_norm[len(best_cat_alias):].strip()
    else:
        person = re.sub(
            r"(?:^|\s)" + re.escape(best_cat_alias) + r"(?:\s|$)",
            " ", f" {stem_norm} ",
        ).strip()

    # Clean up noise (only filler words, NOT honorifics like bac/co/chu)
    person = re.sub(r"\b(cua|cùa|của)\b", " ", person).strip()
    person = re.sub(r"\s*\(\d+\)\s*$", "", person).strip()
    person = re.sub(r"\s*\d+\s*$", "", person).strip()  # trailing numbers
    person = re.sub(r"\s+", " ", person).strip()

    return person if person else "__chung__"


def _merge_similar_persons(person_cats: dict[str, set[str]]) -> dict[str, set[str]]:
    """
    Merge person entries that are clearly the same person.

    Strategies:
    1. If one name starts with another (prefix match), merge longer into shorter.
    2. If names share the last word (surname), merge them.
    3. Entries that look like document descriptions (not person names) go to __chung__.
    """
    if len(person_cats) <= 1:
        return person_cats

    # Known non-person tokens (these indicate doc descriptions, not real people)
    _NON_PERSON_WORDS = {
        "xac nhan", "bien lai", "ho so", "hso", "giay", "don",
        "nhan", "decision", "statement", "slip", "thu",
    }

    # Step 1: Filter out non-person entries → move to __chung__
    real_persons: dict[str, set[str]] = {}
    chung_cats: set[str] = person_cats.get("__chung__", set())

    for person, cats in person_cats.items():
        if person == "__chung__":
            continue
        # If the "person" looks like a document description, merge into __chung__
        if person in _NON_PERSON_WORDS or any(person.startswith(w) for w in _NON_PERSON_WORDS):
            chung_cats |= cats
        else:
            real_persons[person] = cats

    if chung_cats:
        real_persons["__chung__"] = chung_cats

    if len(real_persons) <= 1:
        return real_persons

    # Step 2: Merge by prefix OR shared last-word (surname)
    sorted_persons = sorted(
        [p for p in real_persons if p != "__chung__"],
        key=len,
    )
    merged: dict[str, set[str]] = {}
    used: set[str] = set()

    for short in sorted_persons:
        if short in used:
            continue
        merged_cats = set(real_persons[short])
        short_words = set(short.split())

        for long_name in sorted_persons:
            if long_name == short or long_name in used:
                continue
            long_words = set(long_name.split())

            # Merge if: prefix match OR they share the last word (surname)
            should_merge = (
                long_name.startswith(short)
                or short_words & long_words  # share at least one word
            )
            if should_merge:
                merged_cats |= real_persons[long_name]
                used.add(long_name)

        merged[short] = merged_cats

    # Preserve __chung__
    if "__chung__" in real_persons:
        merged["__chung__"] = real_persons["__chung__"]

    return merged


# ---------------------------------------------------------------------------
# Helper: Extract base folder name (strip status suffixes)
# ---------------------------------------------------------------------------
_STATUS_SUFFIXES = [
    "done", "check", "thieu", "thiếu",
    "cho it dich", "chờ it dịch",
    "doi hs khach", "đợi hs khách",
    "dang dich", "đang dịch",
    "dich", "dịch",
    "dang tach file", "đang tách file",
    "dang check da du file chua",
    "thieu thu muc final",
]


def extract_base_name(folder_name: str) -> str:
    """
    Strip emoji prefixes AND status suffixes from a folder name to get the clean base.

    ``"UC - CHU HIEP - NHAN - DONE"``  →  ``"UC - CHU HIEP - NHAN"``
    ``"🚨 UC - CHU HIEP - NHAN - THIẾU (Passport)"``  →  ``"UC - CHU HIEP - NHAN"``
    ``"✅ UC - CHU HIEP - NHAN - Chờ IT dịch"``  →  ``"UC - CHU HIEP - NHAN"``
    ``"🚨 UC - CHU HIEP - NHAN - DONE"``  →  ``"UC - CHU HIEP - NHAN"``
    """
    name = folder_name.strip()

    # 1. Strip emoji prefixes (🚨, ✅, 🔍, etc.)
    name = re.sub(r"^[\U0001f300-\U0001f9ff\u2705\u274c\u26a0\u2b50\U0001f4a1]+\s*", "", name)

    # 1.5 Strip legacy DONE prefix chains:
    #     "DONE - UC - ..." -> "UC - ..."
    #     "DONE - DONE - UC - ..." -> "UC - ..."
    while True:
        parts = name.split("-", 1)
        if len(parts) != 2:
            break
        leading = normalize(parts[0])
        if leading == "done":
            name = parts[1].strip()
            continue
        break

    # 2. Remove anything after " - THIẾU" or " - THIEU" (including parentheses)
    pattern = r"\s*-\s*(?:THIẾU|THIEU)\s*\(.*?\)\s*$"
    name = re.sub(pattern, "", name, flags=re.IGNORECASE)

    # 3. Remove trailing status keywords after last dash.
    #    Keep stripping in a loop to handle duplicated suffix chains:
    #    "... - Đang tách file - Đang tách file" -> "..."
    while True:
        parts = name.rsplit("-", 1)
        if len(parts) != 2:
            break

        trailing = normalize(parts[1])
        matched = False
        for suffix in _STATUS_SUFFIXES:
            if trailing == suffix or trailing.startswith(suffix):
                name = parts[0].strip()
                matched = True
                break

        if not matched:
            break

    return name.strip()


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import io
    # Fix Windows console encoding
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    rules = _load_rules()

    # Test normalisation
    print("=== Normalize Tests ===")
    print(f"  normalize('So Do nam 2023.pdf') -> '{normalize('So Do nam 2023.pdf')}'")
    print(f"  normalize('LAND cua chu Hiep')  -> '{normalize('LAND cua chu Hiep')}'")
    print(f"  normalize('passport_scan.jpg')  -> '{normalize('passport_scan.jpg')}'")

    # Test file classification
    print("\n=== Classification Tests ===")
    test_files = [
        "to khai visa.docx",
        "passport NGUYEN VAN A.pdf",
        "CCCD_mat_truoc.jpg",
        "so DO nha nam 2023.pdf",
        "random_file_123.pdf",
        "hop dong lao dong.pdf",
    ]
    for f in test_files:
        cat = classify_file(f, rules)
        print(f"  '{f}' -> {cat}")

    # Test folder validation (AUS - Full)
    print("\n=== Validation Test (AUS - Full) ===")
    result = validate_folder(
        "UC - NGUYEN VAN A - NHAN - DONE",
        ["to_khai.docx", "passport.pdf", "cccd.jpg", "so_do_nha.pdf"],
        rules,
    )
    print(f"  Valid: {result['valid']}, Summary: {result['summary']}")

    # Test folder validation (AUS - Missing Passport)
    print("\n=== Validation Test (AUS - Missing Passport) ===")
    result = validate_folder(
        "UC - NGUYEN VAN A - NHAN - DONE",
        ["to_khai.docx", "cccd.jpg", "so_do_nha.pdf"],
        rules,
    )
    print(f"  Valid: {result['valid']}, Summary: {result['summary']}")
    print(f"  Missing: {result['missing']}")

    # Test conditional rule (Employment contract without leave)
    print("\n=== Validation Test (Employment Contract without Leave) ===")
    result = validate_folder(
        "UC - NGUYEN VAN A - NHAN - DONE",
        ["to_khai.docx", "passport.pdf", "cccd.jpg", "bank.pdf", "hop_dong_ld.pdf"],
        rules,
    )
    print(f"  Valid: {result['valid']}, Summary: {result['summary']}")
    print(f"  Missing: {result['missing']}")
    print(f"  Conditional: {result['conditional_missing']}")
