"""
Shared XML and form-filling helper utilities.

Used by both fill_imm5257.py and fill_imm5645.py for common operations
like XML escaping, date splitting, and code lookups.

Country codes use XFA "lic" values from the IRCC PDF template.
These are NOT ISO-3166 codes.  They were extracted from the
LOVFile > CountryList section of the XFA datasets stream.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Country code lookups (XFA lic codes from IRCC PDF template)
# ---------------------------------------------------------------------------
COUNTRY_CODES: dict[str, str] = {
    "vietnam": "270", "viet nam": "270",
    "canada": "511",
    "usa": "461", "united states": "461", "united states of america": "461",
    "australia": "305",
    "japan": "207",
    "korea": "258", "south korea": "258", "korea, south": "258",
    "china": "202",
    "france": "022",
    "germany": "024", "germany, federal republic of": "024",
    "united kingdom": "003", "uk": "003", "england": "002", "scotland": "007",
    "thailand": "267",
    "singapore": "246",
    "malaysia": "242",
    "philippines": "227",
    "india": "205",
    "taiwan": "203",
    "italy": "028",
    "greece": "025",
    "turkey": "045",
    "hungary": "026",
    "mexico": "501",
    "indonesia": "222",
    "cambodia": "256",
    "laos": "260",
    "myanmar": "241", "burma": "241", "burma (myanmar)": "241",
    "spain": "037",
    "netherlands": "031", "the netherlands": "031",
    "belgium": "012",
    "switzerland": "041",
    "sweden": "040",
    "norway": "032",
    "denmark": "017",
    "new zealand": "339",
    "brazil": "709",
    "hong kong": "204", "china (hong kong sar)": "200",
    "ireland": "027",
    "poland": "033",
    "russia": "056",
    "ukraine": "059",
    "egypt": "101",
    "south africa": "121",
    "nigeria": "177",
    "kenya": "132",
    "morocco": "133",
    "saudi arabia": "231",
    "uae": "280", "united arab emirates": "280",
    "kuwait": "226",
    "qatar": "265",
    "pakistan": "209",
    "bangladesh": "212",
    "sri lanka": "201",
    "nepal": "264",
    "iran": "223",
    "iraq": "224",
    "israel": "206",
    "jordan": "225",
    "lebanon": "208",
    "cuba": "650",
    "jamaica": "602",
    "colombia": "722",
    "peru": "723",
    "chile": "721",
    "argentina": "703",
}

# Map from codes AI might use (ISO-3166, or old wrong IRCC codes)
# to correct XFA lic codes
WRONG_CODE_FIX: dict[str, str] = {
    # ISO-3166 numeric → XFA lic
    "704": "270",   # Vietnam
    "764": "267",   # Thailand
    "124": "511",   # Canada
    "840": "461",   # USA
    "036": "305",   # Australia
    "392": "207",   # Japan
    "156": "202",   # China
    "250": "022",   # France
    "276": "024",   # Germany
    "826": "003",   # UK
    "702": "246",   # Singapore
    "458": "242",   # Malaysia
    "608": "227",   # Philippines
    "356": "205",   # India
    "158": "203",   # Taiwan
    "360": "222",   # Indonesia
    "116": "256",   # Cambodia
    "418": "260",   # Laos
    "104": "241",   # Myanmar
    "410": "258",   # South Korea (ISO 410)
    # Old wrong IRCC codes → correct XFA lic
    "306": "511",   # Canada
    "400": "461",   # USA
    "501": "305",   # Australia (501=Mexico in XFA!)
    "302": "207",   # Japan
    "312": "258",   # South Korea
    "308": "202",   # China
    "337": "022",   # France
    "338": "024",   # Germany
    "424": "267",   # Thailand
    "381": "246",   # Singapore
    "357": "242",   # Malaysia
    "367": "227",   # Philippines
    "301": "205",   # India
    "414": "203",   # Taiwan (414=Niue in XFA!)
    "344": "222",   # Indonesia
    "303": "256",   # Cambodia
    "304": "260",   # Laos
    "305": "305",   # Australia (correct! same)
    "328": "028",   # Italy
    "339": "339",   # New Zealand (correct! same)
    "422": "045",   # Turkey
    "340": "026",   # Hungary
    "355": "501",   # Mexico (wrong → 501)
    "321": "709",   # Brazil
}

# Known correct XFA lic codes (pass-through)
VALID_LIC_CODES = {
    "270", "511", "461", "305", "207", "258", "202", "022", "024",
    "003", "267", "246", "242", "227", "205", "203", "028", "025",
    "045", "026", "501", "222", "256", "260", "241", "037", "031",
    "012", "041", "040", "032", "017", "339", "709", "204", "200",
    "027", "033", "056", "059", "101", "121", "177", "132", "133",
    "231", "280", "226", "265", "209", "212", "201", "264", "223",
    "224", "206", "225", "208", "650", "602", "722", "723", "721",
    "703",
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
    """Resolve a country name or code to its XFA lic code.

    Handles:
    - Correct XFA lic codes (pass through): "270" → "270"
    - Wrong codes / ISO codes (auto-correct): "764" → "267" (Thailand)
    - Country names: "Thailand" → "267"
    """
    if not val:
        return ""
    val_str = str(val).strip()
    if val_str.isdigit() or (len(val_str) == 3 and val_str[0] == '0'):
        # It's a numeric code
        if val_str in VALID_LIC_CODES:
            return val_str
        # Try fixing known wrong codes
        return WRONG_CODE_FIX.get(val_str, val_str)
    return COUNTRY_CODES.get(val_str.lower().strip(), val_str)


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
