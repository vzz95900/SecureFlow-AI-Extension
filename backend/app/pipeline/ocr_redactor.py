"""
SecureFlow AI — OCR-Based Redaction.
Extracts text from images/scanned PDFs using Tesseract (+ PaddleOCR fallback).

NOTE: Requires Tesseract to be installed on the system.
      pip install pytesseract paddleocr
"""

from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy-load OCR engines
_tesseract_available = None
_paddle_available = None


def _check_tesseract() -> bool:
    """Check if pytesseract is available."""
    global _tesseract_available
    if _tesseract_available is not None:
        return _tesseract_available
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        _tesseract_available = True
        logger.info("Tesseract OCR available")
    except Exception:
        _tesseract_available = False
        logger.warning("Tesseract OCR not available")
    return _tesseract_available


def _check_paddle() -> bool:
    """Check if PaddleOCR is available."""
    global _paddle_available
    if _paddle_available is not None:
        return _paddle_available
    try:
        from paddleocr import PaddleOCR
        _paddle_available = True
        logger.info("PaddleOCR available")
    except ImportError:
        _paddle_available = False
        logger.warning("PaddleOCR not available")
    return _paddle_available


async def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Extract text from an image using available OCR engines.

    Priority: Tesseract first, PaddleOCR as fallback.

    Args:
        image_bytes: Raw image file bytes.

    Returns:
        Extracted text string.
    """
    results: list[tuple[str, float]] = []  # (text, confidence)

    # Try Tesseract
    if _check_tesseract():
        try:
            text = _tesseract_extract(image_bytes)
            if text.strip():
                results.append((text, 0.8))
        except Exception as e:
            logger.error(f"Tesseract extraction failed: {e}")

    # Try PaddleOCR
    if _check_paddle():
        try:
            text = _paddle_extract(image_bytes)
            if text.strip():
                results.append((text, 0.85))
        except Exception as e:
            logger.error(f"PaddleOCR extraction failed: {e}")

    if not results:
        logger.warning("No OCR engine could extract text from image")
        return ""

    # Return the highest-confidence result
    results.sort(key=lambda x: x[1], reverse=True)
    return results[0][0]


def _tesseract_extract(image_bytes: bytes) -> str:
    """Extract text using Tesseract."""
    import pytesseract
    from PIL import Image
    import io

    image = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(image)
    return text


def _paddle_extract(image_bytes: bytes) -> str:
    """Extract text using PaddleOCR."""
    from paddleocr import PaddleOCR
    import numpy as np
    from PIL import Image
    import io

    ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    image = Image.open(io.BytesIO(image_bytes))
    img_array = np.array(image)

    result = ocr.ocr(img_array, cls=True)

    lines = []
    if result and result[0]:
        for line in result[0]:
            if line and len(line) >= 2:
                text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                lines.append(text)

    return "\n".join(lines)


async def extract_text_from_images(images: list[bytes]) -> str:
    """
    Extract text from multiple images and concatenate.

    Args:
        images: List of image byte arrays.

    Returns:
        Concatenated extracted text.
    """
    texts = []
    for i, img_bytes in enumerate(images):
        text = await extract_text_from_image(img_bytes)
        if text.strip():
            texts.append(f"--- Page {i + 1} ---\n{text}")

    return "\n\n".join(texts)
