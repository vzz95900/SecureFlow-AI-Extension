"""
SecureFlow AI — Sanitize Router.
POST /api/v1/sanitize — Detect and redact PII from text.
"""

from fastapi import APIRouter, HTTPException
import logging

from app.models.schemas import SanitizeRequest, SanitizeResponse
from app.pipeline.orchestrator import detect_all
from app.pipeline.redactor import redact
from app.utils.token_map import token_map_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sanitize"])


@router.post("/sanitize", response_model=SanitizeResponse)
async def sanitize_text(request: SanitizeRequest):
    """
    Detect PII/PHI in text, redact it, and return the sanitized version.

    The token map is stored server-side for later restoration via /restore.
    """
    try:
        # 1. Create or reuse session
        session_id = token_map_manager.create_session(request.session_id)

        # 2. Run the detection pipeline
        entities, risk_level, summary = await detect_all(
            request.text,
            sensitivity=request.sensitivity,
        )

        # 3. Redact detected entities
        sanitized_text, token_map = redact(
            request.text, entities, mode=request.redaction_mode
        )

        # 4. Store the token map for this session
        token_map_manager.store_map(session_id, token_map)

        logger.info(
            f"Session {session_id}: sanitized {len(entities)} entities, "
            f"risk={risk_level}"
        )

        return SanitizeResponse(
            sanitized_text=sanitized_text,
            session_id=session_id,
            entities_found=len(entities),
            risk_level=risk_level,
            entity_summary=summary,
        )

    except Exception as e:
        logger.error(f"Sanitization error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sanitization failed: {str(e)}")
