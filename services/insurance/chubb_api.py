from __future__ import annotations
import requests as http_requests

# Chubb Travel Insurance API for pricing
CHUBB_QUOTE_URL = "https://buy.chubbtravelinsurance.com/ctivn/api/quote/quoteArray"

# Mapping region to regionCode expected by Chubb
# "Toàn Cầu" is "RG.DWLW" and "Châu Á" is "RG.DAS"
REGION_CODES = {
    "Worldwide": "RG.DWLW",
    "Toàn Cầu": "RG.DWLW",
    "Châu Á": "RG.DAS",
}

def fetch_chubb_premium(start_date: str, end_date: str, policy_type: str = "AMT", cover_type: str = "CT.IND",
                        region: str = "Worldwide", adults: int = 1, children: int = 0) -> str | None:
    """
    Call Chubb Travel Insurance API to get GOLD package premium.
    start_date, end_date should be in YYYY-MM-DD format (API expects this format).
    """
    try:
        region_code = REGION_CODES.get(region, "RG.DWLW")
        
        payload = {
            "tripDetails": {
                "policyType": policy_type, # "AMT" or "SIT"
                "coverTypeCode": cover_type,
                "tripStartDate": start_date,
                "tripEndDate": end_date,
                "regionCode": region_code,
                "productGroup": "international"
            },
            "coverOptions": {},
            "traveller": {
                "option": 1,
                "travellerCount": {
                    "adultCount": int(adults),
                    "childCount": int(children),
                    "infantCount": 0,
                    "seniorCount": 0
                }
            },
            "settings": {
                "benefitResponseFormat": {
                    "standardBenefit": 1,
                    "optionalBenefit": 2
                }
            },
            "premiumOptions": {
                "discountCode": ""
            },
            "brokerCode": ""
        }
        
        headers = {
            "Content-Type": "application/json"
        }

        # Just post to the API
        resp = http_requests.post(CHUBB_QUOTE_URL, json=payload, headers=headers, timeout=10)
        
        if resp.ok:
            data = resp.json()
            # The API returns an array, we must find the GOLD or highest package or one that matches standard.
            # Example package is like Data inside the response.
            # The plan code for Gold Annual might be "AMT.PGAN" or something.
            # Let's iterate and find the package, or just get the first one if unsure, but let's try to get GOLD.
            gold_premium = None
            fallback_premium = None
            
            # API usually returns a list of quote options directly or inside an object
            # It usually returns a list of plans
            quotes = data if isinstance(data, list) else data.get("quotes", [])
            if not isinstance(quotes, list):
                # Sometimes it returns a bare json obj {"data": [...]}
                quotes = data.get("data", [])
            
            for plan in quotes:
                plan_code = str(plan.get("planCode", "")).upper()
                price = plan.get("totalPrice") or plan.get("premium", {}).get("totalAmount")
                if not price:
                    continue
                # Save the first one as fallback
                if fallback_premium is None:
                    fallback_premium = price
                # If it's a GOLD plan (Annual Gold is AMT.PGAN)
                if "GAN" in plan_code or "GOLD" in str(plan.get("planName", "")).upper() or "PGAN" in plan_code:
                    gold_premium = price
                    break
            
            final_price = gold_premium if gold_premium is not None else fallback_premium
            
            if final_price:
                # Format with dots: 5040000 -> "VND5.040.000"
                formatted = f"{int(final_price):,}".replace(",", ".")
                return f"VND{formatted}"
                
    except Exception as e:
        print(f"[insurance] Chubb API error: {e}")
    return None
