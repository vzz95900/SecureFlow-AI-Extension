"""
SecureFlow AI — File Sanitization Router.
POST /api/v1/sanitize-file — Upload a file (PDF, image, text, DOCX),
extract text, detect & redact PII.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import logging

from app.models.schemas import SanitizeFileResponse
from app.pipeline.orchestrator import detect_all
from app.pipeline.redactor import redact
from app.pipeline.ocr_redactor import extract_text_from_image
from app.utils.pdf_parser import extract_text_from_pdf
from app.utils.token_map import token_map_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sanitize-file"])

# ── Supported MIME types ─────────────────────────────────────────
_PDF_TYPES = {"application/pdf"}
_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/bmp",
    "image/tiff",
}
_TEXT_TYPES = {
    "text/plain",
    "text/csv",
    "text/markdown",
    "text/rtf",
    "text/html",
    "text/xml",
    "application/json",
    "application/xml",
    "application/rtf",
}
_DOCX_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Extensions we accept even if MIME type is wrong/missing
_TEXT_EXTENSIONS = {
    ".txt", ".csv", ".md", ".rtf", ".log", ".json", ".xml",
    ".html", ".htm", ".yaml", ".yml", ".ini", ".cfg", ".conf",
}

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def _get_ext(filename: str | None) -> str:
    """Return the lowercased file extension."""
    if not filename:
        return ""
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def _try_decode_text(data: bytes) -> str:
    """Try UTF-8 first, then latin-1 as a universal fallback."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def _extract_docx_text(data: bytes) -> str:
    """Extract paragraphs from a .docx file using python-docx."""
    import io
    try:
        from docx import Document   # python-docx
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="python-docx is not installed. Run: pip install python-docx",
        )
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


@router.post("/sanitize-file", response_model=SanitizeFileResponse)
async def sanitize_file(
    file: UploadFile = File(...),
    sensitivity: str = Form(default="high"),
    redaction_mode: str = Form(default="xxx"),
    session_id: str = Form(default=None),
):
    """
    Upload a file (PDF, image, text, DOCX), extract text, detect PII,
    and return details of sensitive items found.
    """
    # ── Classify file type ───────────────────────────────────────
    content_type = (file.content_type or "").lower()
    ext = _get_ext(file.filename)

    is_pdf = content_type in _PDF_TYPES or ext == ".pdf"
    is_image = content_type in _IMAGE_TYPES
    is_text = content_type in _TEXT_TYPES or ext in _TEXT_EXTENSIONS
    is_docx = content_type in _DOCX_TYPES or ext == ".docx"

    if not (is_pdf or is_image or is_text or is_docx):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type} ({ext}). "
                   f"Accepted: PDF, images, text files (.txt, .csv, .md, .rtf, .log, .json, .xml), DOCX.",
        )

    # ── Read file bytes ──────────────────────────────────────────
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 20 MB limit.")

    # ── Extract text ─────────────────────────────────────────────
    file_category = "unknown"
    try:
        if is_text:
            extracted_text = _try_decode_text(file_bytes)
            file_category = "text"
        elif is_docx:
            extracted_text = _extract_docx_text(file_bytes)
            file_category = "docx"
        elif is_pdf:
            pdf_result = extract_text_from_pdf(file_bytes)
            extracted_text = pdf_result["text"]

            # If scanned PDF (no text layer), OCR the embedded images
            if not pdf_result["has_text_layer"] and pdf_result["images"]:
                ocr_parts = []
                for img_bytes in pdf_result["images"]:
                    ocr_text = await extract_text_from_image(img_bytes)
                    if ocr_text.strip():
                        ocr_parts.append(ocr_text)
                if ocr_parts:
                    extracted_text = "\n\n".join(ocr_parts)
            file_category = "pdf"
        else:
            extracted_text = await extract_text_from_image(file_bytes)
            file_category = "image"

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Text extraction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract text from file: {str(e)}",
        )

    if not extracted_text or not extracted_text.strip():
        raise HTTPException(
            status_code=422,
            detail="No readable text could be extracted from the file.",
        )

    # ── Detect & redact PII ──────────────────────────────────────
    try:
        sid = token_map_manager.create_session(session_id)
        entities, risk_level, summary = await detect_all(
            extracted_text, sensitivity=sensitivity
        )
        sanitized_text, token_map = redact(
            extracted_text, entities, mode=redaction_mode
        )
        token_map_manager.store_map(sid, token_map)

        # Build entity_details list for the warning modal
        entity_details = []
        for ent in entities:
            entity_details.append({
                "type": ent.type,
                "text": ent.text,
            })

        logger.info(
            f"File '{file.filename}': extracted {len(extracted_text)} chars, "
            f"found {len(entities)} entities, risk={risk_level}"
        )

        return SanitizeFileResponse(
            sanitized_text=sanitized_text,
            session_id=sid,
            entities_found=len(entities),
            risk_level=risk_level,
            entity_summary=summary,
            entity_details=entity_details,
            file_type=file_category,
            original_text=extracted_text,
        )

    except Exception as e:
        logger.error(f"File sanitization error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"File sanitization failed: {str(e)}",
        )

