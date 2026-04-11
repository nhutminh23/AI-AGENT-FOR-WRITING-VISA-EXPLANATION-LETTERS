"""
Build Group Tour Participant List — header text utility.

Provides build_group_header_text() used by generator.py to prepend
group info to the explanation letter.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def build_group_header_text(
    participants: List[Dict[str, Any]],
    group_id: str = "",
    group_label: str = "",
) -> str:
    """
    Build the group application header text to prepend to the explanation letter.
    
    Example output:
        Group Application ID: Q07VZU (Ha Family)
        Applicants in this group:
        Mr Tran Trung Anh – Passport No. B4841361
        Mrs Ngo Ngan Ha – Passport No. C3980690
    """
    lines = []
    
    id_line = f"Group Application ID: {group_id or '___________'}"
    if group_label:
        id_line += f" ({group_label})"
    lines.append(id_line)
    
    lines.append("Applicants in this group:")
    for p in participants:
        name = p.get("full_name", "Unknown")
        passport = p.get("passport_no", "")
        if passport:
            lines.append(f"{name} – Passport No. {passport}")
        else:
            lines.append(name)
    
    return "\n".join(lines)
