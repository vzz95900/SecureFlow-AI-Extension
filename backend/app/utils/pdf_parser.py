"""
SecureFlow AI — PDF & Image Text Extraction Utility.
Uses PyMuPDF (fitz) for PDF parsing, with OCR fallback.
"""

from __future__ import annotations
import io
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def extract_text_from_pdf(pdf_bytes: bytes) -> dict:
    """
    Extract text from a PDF file.

    Returns:
        {
            "text": str,            # Extracted text
            "pages": int,           # Number of pages
            "has_text_layer": bool,  # Whether PDF has text (not scanned)
            "images": list[bytes],  # Extracted images (for OCR if needed)
        }
    """
    if fitz is None:
        raise ImportError("PyMuPDF (fitz) is not installed. Run: pip install PyMuPDF")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = doc.page_count
    full_text = []
    images = []

    for page in doc:
        page_text = page.get_text("text").strip()
        full_text.append(page_text)

        # Extract images from the page (for OCR on scanned PDFs)
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            if base_image and base_image.get("image"):
                images.append(base_image["image"])

    doc.close()

    combined_text = "\n\n".join(full_text).strip()
    has_text = len(combined_text) > 20  # Heuristic: very short = likely scanned

    return {
        "text": combined_text,
        "pages": pages,
        "has_text_layer": has_text,
        "images": images,
    }


def extract_text_from_image_bytes(image_bytes: bytes) -> Optional[str]:
    """
    Placeholder for OCR extraction from raw image bytes.
    Actual OCR is handled by ocr_redactor.py in the pipeline.
    """
    return None
