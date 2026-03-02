"""
AI Classification Service
Uses OpenAI Vision API to classify document pages and extract names.
Features:
- Batch processing (5 pages/batch for accuracy)
- Parallel waves (5 concurrent batches for speed)
- Automatic Gemini fallback on OpenAI rate limits
- Smart post-processing to fix cross-batch issues
"""

import json
import os
import re
import time
import asyncio
from typing import Dict, List, Optional
from dotenv import load_dotenv

import openai
from openai import OpenAI
import google.generativeai as genai

load_dotenv()

_openai_client = None
_gemini_configured = False
_gemini_model = None

# Global state to track if we should preferentially use Gemini because OpenAI ran out of credits
gemini_fallback_active = False


def get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your_openai_api_key_here":
            raise ValueError("OPENAI_API_KEY not configured.")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client

def configure_gemini():
    global _gemini_configured, _gemini_model
    if not _gemini_configured:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key and gemini_api_key != "your_gemini_api_key_here":
            genai.configure(api_key=gemini_api_key)
            model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()
            _gemini_model = genai.GenerativeModel(model_name)
            _gemini_configured = True
    return _gemini_configured

def get_gemini_model():
    configure_gemini()
    return _gemini_model


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()


# ----- Prompts -----

BATCH_PROMPT = """You are a document classification expert. I will show you {num_pages} scanned page images (pages {start_idx} to {end_idx}).

YOUR TASK: For EACH page, classify it INDEPENDENTLY by looking at its visual content.

For each page, return:
1. document_type_en: The document type visible on THIS page. Common types:
   - Passport (has photo, MRZ machine-readable code at bottom, says "HO CHIEU / PASSPORT")
   - Birth_Certificate (says "GIAY KHAI SINH", has government seal, handwritten birth details)
   - CCCD (Vietnamese ID card with chip)
   - Marriage_Certificate (says "GIAY CHUNG NHAN KET HON")
   - Contract (multi-page legal agreement, numbered articles/clauses)
   - Agreement (similar to contract but shorter)
   - Decision (official government decision document)
   - Social_Insurance_Record (social insurance booklet pages)
   - Account_Statement (bank statement with transaction rows)
   - Power_of_Attorney (says "GIAY UY QUYEN")
   - Receipt_Voucher (payment receipt)
   - Registration_Form (form with fields to fill)
   - Commitment_Letter (says "CAM KET" or commitment)
   - Price_Quotation (quotation/pricing document)
   - Land_Certificate (land ownership document)
   - Other document types as appropriate

2. person_name_en: Primary person's name in UPPERCASE, no diacritics, underscores for spaces (e.g., NGUYEN_VAN_A).

3. is_continuation: true ONLY if this page is part of the SAME physical document as the PREVIOUS page. 
   - IMPORTANT: If the page layout/format CHANGES (different headers, different document style), it is NOT a continuation even if person name is the same.
   - A Passport page CANNOT be a continuation of a Contract.
   - A Birth Certificate CANNOT be a continuation of a Contract.
{previous_context}

RULES:
- EXAMINE each page individually. Do NOT lazily mark pages as continuations.
- For multi-person documents (contracts with 2+ signers): use the FIRST person's name for ALL pages.
- Person names must be UPPERCASE with underscores (e.g., NGUYEN_LE_KIM_NGAN, not Nguyen_Le_Kim_Ngan).
- Return EXACTLY {num_pages} JSON objects.

Return ONLY a JSON array:
[
  {{"page_index": {start_idx}, "document_type_en": "Contract", "person_name_en": "NGUYEN_VAN_A", "is_continuation": false}},
  {{"page_index": {start_idx_plus_1}, "document_type_en": "Contract", "person_name_en": "NGUYEN_VAN_A", "is_continuation": true}}
]"""


# ----- Response Parsing -----

def parse_batch_response(text: str, expected_count: int, start_idx: int) -> List[Dict]:
    """Parse the JSON array response from AI."""
    results = []
    
    if not text:
        return _generate_error_batch("Empty response", expected_count, start_idx)
        
    text = text.strip()
    
    # Try to extract JSON array from markdown or plain text
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        json_str = match.group(0)
    else:
        json_str = text
        
    try:
        parsed_array = json.loads(json_str)
        if isinstance(parsed_array, list):
            for item in parsed_array:
                if isinstance(item, dict):
                    results.append({
                        "document_type_en": item.get("document_type_en", "Unknown_Document"),
                        "person_name_en": item.get("person_name_en", "Unknown"),
                        "is_continuation": bool(item.get("is_continuation", False)),
                        "confidence": float(item.get("confidence", 0.8))
                    })
    except json.JSONDecodeError:
        print(f"  ❌ JSON parse failed on batch. Raw text:\n{text[:200]}...")
    
    # Pad or truncate to ensure exactly expected_count items
    while len(results) < expected_count:
        results.append({
            "document_type_en": "Error",
            "person_name_en": "Unknown",
            "is_continuation": False,
            "confidence": 0.0,
            "notes": "Missing from AI response"
        })
        
    if len(results) > expected_count:
        results = results[:expected_count]
        
    return results

def _generate_error_batch(error_msg: str, count: int, start_idx: int) -> List[Dict]:
    return [{
        "document_type_en": "Error",
        "person_name_en": "Unknown",
        "is_continuation": False,
        "confidence": 0.0,
        "notes": f"API Error: {error_msg}"
    } for _ in range(count)]


def normalize_person_name(name: str) -> str:
    """Normalize person name to UPPERCASE with underscores."""
    name = name.strip()
    # Replace spaces with underscores  
    name = name.replace(" ", "_")
    # Convert to uppercase
    name = name.upper()
    # Remove double underscores
    while "__" in name:
        name = name.replace("__", "_")
    name = name.strip("_")
    return name if name else "UNKNOWN"


# ----- AI Inference Calls -----

async def call_openai(model_name: str, prompt: str, images_base64: List[str]) -> str:
    content = [{"type": "text", "text": prompt}]
    for b64 in images_base64:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}",
                "detail": "auto"
            }
        })
    
    api_params = {
        "model": model_name,
        "messages": [{"role": "user", "content": content}],
    }
    
    if "gpt-5" in model_name or "gpt-4.1" in model_name:
        api_params["max_completion_tokens"] = 1500
    else:
        api_params["max_tokens"] = 1500
        api_params["temperature"] = 0.1
        
    # Running blocking call in thread pool to prevent blocking asyncio loop
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, 
        lambda: get_openai_client().chat.completions.create(**api_params)
    )
    return response.choices[0].message.content


async def call_gemini(prompt: str, images_base64: List[str]) -> str:
    gemini_model = get_gemini_model()
    if not gemini_model:
        raise ValueError("Gemini is not configured.")
        
    contents = [prompt]
    for b64 in images_base64:
        contents.append({
            "mime_type": "image/jpeg",
            "data": b64
        })
        
    generation_config = genai.types.GenerationConfig(
        temperature=0.1,
        max_output_tokens=1500,
    )
    
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: gemini_model.generate_content(
            contents, 
            generation_config=generation_config
        )
    )
    return response.text


# ----- API Call with Retry & Fallback -----

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


async def classify_batch(
    images_base64: List[str],
    start_idx: int,
    previous_classification: Optional[Dict] = None,
    openai_model: str = None
) -> List[Dict]:
    global gemini_fallback_active
    
    if openai_model is None:
        openai_model = get_openai_model()

    num_pages = len(images_base64)
    end_idx = start_idx + num_pages - 1
    
    prev_context = ""
    if previous_classification and previous_classification.get("document_type_en") not in ("Error", "Unknown_Document"):
        prev_t = previous_classification.get("document_type_en")
        prev_n = previous_classification.get("person_name_en")
        prev_context = f"\nFor page {start_idx}, the page immediately preceding it was: type='{prev_t}', person='{prev_n}'. Only set is_continuation=true if THIS page is clearly the same physical document."
    else:
        prev_context = f"\nPage {start_idx} is the first page or follows an unknown page, so its is_continuation should be false."

    prompt = BATCH_PROMPT.format(
        num_pages=num_pages,
        start_idx=start_idx,
        end_idx=end_idx,
        start_idx_plus_1=start_idx + 1,
        previous_context=prev_context
    )
    
    # Retry loop
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result_text = None
            
            # Use Gemini if fallback is active
            use_gemini = gemini_fallback_active and configure_gemini()
            
            if use_gemini:
                print(f"  [AI] Gemini → batch {start_idx}-{end_idx}")
                result_text = await call_gemini(prompt, images_base64)
            else:
                try:
                    print(f"  [AI] OpenAI ({openai_model}) → batch {start_idx}-{end_idx}")
                    result_text = await call_openai(openai_model, prompt, images_base64)
                except openai.RateLimitError as e:
                    print(f"  ⚠️ OpenAI Rate Limit (429)")
                    if configure_gemini():
                        print(f"  🔄 Switching to Gemini!")
                        gemini_fallback_active = True
                        result_text = await call_gemini(prompt, images_base64)
                    else:
                        raise e
            
            if not result_text or not result_text.strip():
                print(f"  [attempt {attempt}] Empty response, retrying...")
                last_error = "Empty response"
                await asyncio.sleep(RETRY_DELAY)
                continue
            
            results = parse_batch_response(result_text, num_pages, start_idx)
            
            # Sanitize and normalize each result
            for i, result in enumerate(results):
                result["document_type_en"] = sanitize_filename(result.get("document_type_en", "Unknown_Document"))
                result["person_name_en"] = normalize_person_name(result.get("person_name_en", "Unknown"))
                result["document_type"] = result["document_type_en"]
                result["person_name"] = result["person_name_en"]
                
                print(f"  ✅ P{start_idx + i}: {result['document_type_en']} | {result['person_name_en']}" + 
                      (" ↳" if result.get("is_continuation") else ""))
            return results
            
        except Exception as e:
            last_error = str(e)
            print(f"  [attempt {attempt}] Error: {last_error[:100]}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY * attempt)
    
    # All retries failed
    print(f"  ❌ All {MAX_RETRIES} attempts failed for batch {start_idx}-{end_idx}: {last_error}")
    return _generate_error_batch(last_error, num_pages, start_idx)


# ----- Post-processing -----

def post_process_classifications(classifications: List[Dict]) -> List[Dict]:
    """Fix continuations, normalize names, and fill Error pages."""
    results = [c.copy() for c in classifications]
    
    # Pass 1: Normalize all person names to UPPERCASE
    for i in range(len(results)):
        results[i]["person_name_en"] = normalize_person_name(results[i].get("person_name_en", "Unknown"))
        results[i]["person_name"] = results[i]["person_name_en"]
    
    # Pass 2: Fix incorrect continuation flags
    # If document type is different from previous, it CANNOT be a continuation
    for i in range(1, len(results)):
        curr = results[i]
        prev = results[i - 1]
        if curr.get("is_continuation") and curr.get("document_type_en") != "Error":
            prev_type = prev.get("document_type_en", "").upper().replace("_", "")
            curr_type = curr.get("document_type_en", "").upper().replace("_", "")
            if prev_type != curr_type and curr_type and prev_type:
                print(f"  [Fix] P{i+1}: {curr['document_type_en']} != {prev['document_type_en']}, removing continuation flag")
                results[i]["is_continuation"] = False
    
    # Pass 3: If the same document_type appears consecutively with same person,
    # set is_continuation=true (catches cases where batches didn't have context)
    for i in range(1, len(results)):
        curr = results[i]
        prev = results[i - 1]
        if (not curr.get("is_continuation") 
            and curr.get("document_type_en") == prev.get("document_type_en")
            and curr.get("person_name_en") == prev.get("person_name_en")
            and curr.get("document_type_en") != "Error"):
            results[i]["is_continuation"] = True
    
    # Pass 4: Fill in Error pages
    for i in range(len(results)):
        if results[i].get("document_type_en") != "Error":
            continue
        
        prev_good = None
        for j in range(i - 1, -1, -1):
            if results[j].get("document_type_en") != "Error":
                prev_good = results[j]
                break
        
        if not prev_good:
            for j in range(i + 1, len(results)):
                if results[j].get("document_type_en") != "Error":
                    prev_good = results[j]
                    break
                    
        if prev_good:
            results[i]["document_type_en"] = prev_good["document_type_en"]
            results[i]["document_type"] = prev_good.get("document_type", "")
            results[i]["person_name_en"] = prev_good["person_name_en"]
            results[i]["person_name"] = prev_good.get("person_name", "")
            results[i]["is_continuation"] = True
            results[i]["confidence"] = 0.5
            results[i]["notes"] = "Auto-assigned by post-processing"
    
    return results


# ----- Main function -----

BATCH_SIZE = 5    # Smaller batches = more accurate classification per page
MAX_PARALLEL = 5  # More parallel = compensates for smaller batches


async def classify_all_pages(
    images_base64: List[str],
    model: str = None,
    progress_callback=None
) -> List[Dict]:
    global gemini_fallback_active
    
    # Reset fallback at the start of a new run to give OpenAI a try again
    gemini_fallback_active = False
    
    if model is None:
        model = get_openai_model()

    total_pages = len(images_base64)
    
    # Build list of all batch tasks: [(batch_images, start_idx), ...]
    batch_tasks = []
    for i in range(0, total_pages, BATCH_SIZE):
        batch_images = images_base64[i:i + BATCH_SIZE]
        start_idx = i + 1
        batch_tasks.append((batch_images, start_idx))
    
    total_batches = len(batch_tasks)
    
    print(f"\n{'='*60}")
    print(f"[AI] {total_pages} pages | {BATCH_SIZE} pages/batch | {total_batches} batches | {MAX_PARALLEL} parallel")
    print(f"{'='*60}")
    
    # Process batches in parallel waves of MAX_PARALLEL
    all_results = [None] * total_batches  # Preserve order
    pages_done = 0
    
    for wave_start in range(0, total_batches, MAX_PARALLEL):
        wave_end = min(wave_start + MAX_PARALLEL, total_batches)
        wave_indices = list(range(wave_start, wave_end))
        
        wave_batch_info = [batch_tasks[idx] for idx in wave_indices]
        
        page_range = f"{wave_batch_info[0][1]}-{wave_batch_info[-1][1] + len(wave_batch_info[-1][0]) - 1}"
        print(f"\n{'─'*40}")
        print(f"[Wave] {len(wave_indices)} batches parallel (pages {page_range})")
        
        # Create async tasks for this wave
        async_tasks = []
        for batch_images, start_idx in wave_batch_info:
            task = classify_batch(batch_images, start_idx, None, model)
            async_tasks.append(task)
        
        # Run all batches in this wave simultaneously
        wave_results = await asyncio.gather(*async_tasks, return_exceptions=True)
        
        # Collect results in order
        for i, (batch_idx, result) in enumerate(zip(wave_indices, wave_results)):
            if isinstance(result, Exception):
                print(f"  ❌ Batch {batch_idx + 1} failed: {result}")
                num_pages = len(batch_tasks[batch_idx][0])
                start_idx = batch_tasks[batch_idx][1]
                all_results[batch_idx] = _generate_error_batch(str(result), num_pages, start_idx)
            else:
                all_results[batch_idx] = result
            
            # Send progress for this batch
            if progress_callback:
                batch_result = all_results[batch_idx]
                batch_start = batch_tasks[batch_idx][1]
                for j, res in enumerate(batch_result):
                    pages_done += 1
                    await progress_callback(batch_start + j, total_pages, res)
    
    # Flatten all batch results into a single list (in correct page order)
    classifications = []
    for batch_result in all_results:
        if batch_result:
            classifications.extend(batch_result)
    
    # Post-process to fix cross-batch continuity and errors
    print(f"\n[Post-processing {len(classifications)} pages...]")
    classifications = post_process_classifications(classifications)
    
    print(f"\n{'='*60}")
    print(f"[AI] Done! Summary:")
    doc_types = {}
    for c in classifications:
        t = c.get("document_type_en", "Unknown")
        doc_types[t] = doc_types.get(t, 0) + 1
    for t, count in sorted(doc_types.items()):
        print(f"  {t}: {count} pages")
    print(f"{'='*60}\n")
    
    return classifications


def sanitize_filename(name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "")
    name = name.replace(" ", "_")
    while "__" in name:
        name = name.replace("__", "_")
    name = name.strip("_")
    return name if name else "Unknown"
