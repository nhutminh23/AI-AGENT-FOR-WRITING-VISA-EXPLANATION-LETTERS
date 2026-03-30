from __future__ import annotations
import requests as http_requests

# Liberty Insurance API for pricing
LIBERTY_QUOTE_URL = (
    "https://direct.libertyinsurance.com.vn/prod/"
    "vn-ddp-quote/travel/quick-quote/premium-plan/calculate"
)

# Destination codes for Liberty API
DESTINATION_CODES = {
    "Singapore": "TC101", "Thailand": "TC101", "Japan": "TC101",
    "Korea": "TC101", "USA": "TC102", "Australia": "TC101",
    "France": "TC102", "UK": "TC102", "Canada": "TC102",
    "Worldwide": "TC101",
}

def fetch_liberty_premium(days: int, destination: str = "Worldwide",
                           adults: int = 1, children: int = 0) -> str | None:
    """Call Liberty Insurance API to get Classic plan premium."""
    try:
        trip_code = DESTINATION_CODES.get(destination, "TC101")
        payload = {
            "P_DISCOUNT": "",
            "P_NUMBER_ADULTS": adults,
            "P_NUMBER_CHILDREN": children,
            "P_NUMBER_DAYS": days,
            "P_TRIP_TO": trip_code,
            "P_COUNTRY": destination,
            "P_POLICY_PRODUCER_CODE": "00189660",
            "P_INFO": "",
        }
        resp = http_requests.post(LIBERTY_QUOTE_URL, json=payload, timeout=10)
        if resp.ok:
            result = resp.json()
            data = result.get("data", result)  # nested under "data"
            # Individual Classic plan price
            classic_price = data.get("GR_CLA_PREM") or data.get("FA_CLA_PREM")
            if classic_price:
                # Format with dots (Vietnamese style): 588000 -> "588,000"
                formatted = f"{int(classic_price):,}"
                return f"VND {formatted}"
    except Exception as e:
        print(f"[insurance] Liberty API error: {e}")
    return None
