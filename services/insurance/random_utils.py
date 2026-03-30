import random
from datetime import datetime

def random_policy_no() -> str:
    """Generate random policy number like S-TAI-00XXXXXX-00-26"""
    num = random.randint(10000000, 99999999)
    return f"S-TAI-{num:08d}-00-26"

def random_customer_code() -> str:
    """Generate random 8-digit customer code"""
    return f"{random.randint(10000000, 99999999):08d}"

def random_membership_no() -> str:
    """Generate random membership number like IT-XXXXXX-00"""
    num = random.randint(100000, 999999)
    return f"IT-{num}-00"

def calc_trip_days(from_str: str, to_str: str) -> int:
    """Calculate number of days between two DD/MM/YYYY dates."""
    try:
        d1 = datetime.strptime(from_str, "%d/%m/%Y")
        d2 = datetime.strptime(to_str, "%d/%m/%Y")
        return max((d2 - d1).days, 1)
    except Exception:
        return 23  # fallback
