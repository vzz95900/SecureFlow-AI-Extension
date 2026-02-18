"""
SecureFlow AI — Restore Router.
POST /api/v1/restore — Reinject original PII into LLM response.
"""

from fastapi import APIRouter, HTTPException
import logging

from app.models.schemas import RestoreRequest, RestoreResponse
from app.pipeline.redactor import restore
from app.utils.token_map import token_map_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["restore"])


@router.post("/restore", response_model=RestoreResponse)
async def restore_text(request: RestoreRequest):
    """
    Restore redacted tokens in the LLM response with original values.

    Looks up the token map by session_id and replaces all [REDACTED_*] tokens.
    """
    try:
        # 1. Retrieve the token map for this session
        token_map = token_map_manager.get_map(request.session_id)

        if not token_map:
            logger.warning(f"No token map found for session {request.session_id}")
            return RestoreResponse(restored_text=request.text)

        # 2. Restore the original values
        restored_text = restore(request.text, token_map)

        logger.info(
            f"Session {request.session_id}: restored "
            f"{len(token_map)} tokens"
        )

        return RestoreResponse(restored_text=restored_text)

    except Exception as e:
        logger.error(f"Restoration error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Restoration failed: {str(e)}")
