"""
Shared XML and form-filling helper utilities.

Used by both fill_imm5257.py and fill_imm5645.py for common operations
like XML escaping, date splitting, and code lookups.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Country code lookups (IRCC numeric codes)
# ---------------------------------------------------------------------------
COUNTRY_CODES: dict[str, str] = {
    "vietnam": "270", "viet nam": "270",
    "canada": "306",
    "usa": "400", "united states": "400",
    "australia": "501", "japan": "302",
    "korea": "312", "south korea": "312",
    "china": "308", "france": "337",
    "germany": "338", "united kingdom": "826",
    "thailand": "424", "singapore": "381",
    "malaysia": "357", "philippines": "367",
    "india": "301", "taiwan": "414",
}

MARITAL_CODES: dict[str, str] = {
    "married": "01", "single": "02",
    "common-law": "03", "divorced": "04",
    "separated": "05", "widowed": "06",
    "annulled": "07",
}


# ---------------------------------------------------------------------------
# Resolver functions
# ---------------------------------------------------------------------------

def resolve_country(val: str) -> str:
    """Resolve a country name or code to its IRCC numeric code."""
    if not val:
        return ""
    if val.isdigit():
        return val
    return COUNTRY_CODES.get(val.lower().strip(), val)


def resolve_marital(val: str) -> str:
    """Resolve a marital status name or code to its IRCC numeric code."""
    if not val:
        return ""
    if val.isdigit() and len(val) <= 2:
        return val.zfill(2)
    return MARITAL_CODES.get(val.lower().strip(), val)


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def xml_escape(val) -> str:
    """Escape XML special characters. Returns empty string for None."""
    if val is None:
        return ""
    s = str(val)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def yn(flag: str) -> str:
    """Return 'Y' or 'N' for checkbox exclGroup values."""
    return "Y" if flag == "Y" else "N"


def split_date(date_str: str) -> tuple[str, str, str]:
    """Split 'YYYY-MM-DD' into (year, month_no_leading_zero, day_no_leading_zero)."""
    if not date_str:
        return ("", "", "")
    parts = date_str.replace("/", "-").split("-")
    if len(parts) >= 3:
        return (parts[0], parts[1].lstrip("0") or "1", parts[2].lstrip("0") or "1")
    return (date_str, "", "")
