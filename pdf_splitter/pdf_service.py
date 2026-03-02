"""
PDF Processing Service
Handles PDF to image conversion and PDF splitting/merging operations.
"""

import fitz  # PyMuPDF
import base64
import os
import io
from PIL import Image
from typing import List, Dict, Tuple


def pdf_to_images(pdf_path: str, dpi: int = 150) -> List[str]:
    """
    Convert each page of a PDF to base64-encoded JPEG images.
    
    Args:
        pdf_path: Path to the PDF file
        dpi: Resolution for image conversion (150 = good balance of quality/speed)
    
    Returns:
        List of base64-encoded JPEG strings, one per page
    """
    doc = fitz.open(pdf_path)
    images_base64 = []
    
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=matrix)
        
        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Resize if too large (max 1500px) to reduce API cost
        max_size = 1500
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        
        # Convert to JPEG base64 (much smaller than PNG)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        images_base64.append(img_base64)
    
    doc.close()
    return images_base64


def get_page_count(pdf_path: str) -> int:
    """Get total number of pages in a PDF."""
    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count


def extract_pages_to_pdf(pdf_path: str, page_numbers: List[int], output_path: str) -> str:
    """
    Extract specific pages from a PDF and save as a new PDF.
    
    Args:
        pdf_path: Source PDF path
        page_numbers: List of 0-indexed page numbers to extract
        output_path: Where to save the new PDF
    
    Returns:
        Path to the created PDF
    """
    src_doc = fitz.open(pdf_path)
    new_doc = fitz.open()  # Create empty PDF
    
    for page_num in page_numbers:
        if 0 <= page_num < len(src_doc):
            new_doc.insert_pdf(src_doc, from_page=page_num, to_page=page_num)
    
    new_doc.save(output_path)
    new_doc.close()
    src_doc.close()
    
    return output_path


def create_output_files(
    pdf_path: str,
    classifications: List[Dict],
    output_dir: str
) -> List[Dict]:
    """
    Group CONSECUTIVE pages into documents, then create separate PDF files.
    
    Grouping rules:
    - Pages with is_continuation=True are merged with the immediately preceding document.
    - Pages with a DIFFERENT document_type_en from the previous page start a new document.
    - Pages with the SAME document_type_en AND same person_name_en as previous
      AND is_continuation=True are merged into the current document.
    
    Args:
        pdf_path: Source PDF path
        classifications: List of classification results from AI, one per page.
            Each dict has: document_type_en, person_name_en, is_continuation
        output_dir: Directory to save output files
    
    Returns:
        List of dicts with info about created files:
            [{filename, document_type, person_name, pages, path}, ...]
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Group consecutive pages into documents
    # KEY RULE: Consecutive pages with the SAME document_type are ALWAYS merged
    # into one group, using the FIRST page's person name.
    # This handles bank statements where AI picks up transaction recipient names
    # instead of the account holder on different pages.
    documents = []
    current_doc = None
    
    for page_idx, cls in enumerate(classifications):
        doc_type = cls.get("document_type_en", "Unknown")
        person = cls.get("person_name_en", "Unknown")
        is_cont = cls.get("is_continuation", False)
        
        if current_doc is not None and (
            is_cont  # AI says it's a continuation
            or doc_type == current_doc["document_type"]  # Same document type = merge
        ):
            # Merge into current document group
            current_doc["pages"].append(page_idx)
        else:
            # Different document type = start a new group
            if current_doc is not None:
                documents.append(current_doc)
            current_doc = {
                "document_type": doc_type,
                "person_name": person,
                "pages": [page_idx],
            }
    
    # Don't forget the last document
    if current_doc is not None:
        documents.append(current_doc)
    
    # Create output files
    output_files = []
    # Track duplicate names to add numbering
    name_counter = {}
    
    for doc in documents:
        person = doc["person_name"].replace(" ", "_")
        doc_type = doc["document_type"].replace(" ", "_")
        base_name = f"{person}_{doc_type}"
        
        # Handle duplicates (e.g., same person with 2 separate bank statements)
        if base_name in name_counter:
            name_counter[base_name] += 1
            filename = f"{base_name}_{name_counter[base_name]}.pdf"
        else:
            name_counter[base_name] = 1
            filename = f"{base_name}.pdf"
        
        output_path = os.path.join(output_dir, filename)
        
        # Extract pages and create new PDF
        extract_pages_to_pdf(pdf_path, doc["pages"], output_path)
        
        output_files.append({
            "filename": filename,
            "document_type": doc["document_type"],
            "person_name": doc["person_name"],
            "pages": [p + 1 for p in doc["pages"]],  # 1-indexed for display
            "path": output_path,
        })
    
    return output_files
