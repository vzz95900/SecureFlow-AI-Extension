"""
SecureFlow AI — Pydantic request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ── Shared ────────────────────────────────────────────────────────

class EntitySummaryItem(BaseModel):
    """Summary of a detected entity type."""
    type: str
    count: int
    risk: str  # HIGH | MEDIUM | LOW


class DetectedEntity(BaseModel):
    """A single detected sensitive entity."""
    start: int
    end: int
    type: str           # PERSON, SSN, EMAIL, etc.
    text: str           # original text span
    risk: str = "HIGH"  # HIGH | MEDIUM | LOW
    source: str = ""    # "ner" | "regex" | "bert"


# ── Sanitize ──────────────────────────────────────────────────────

class SanitizeRequest(BaseModel):
    """POST /api/v1/sanitize request body."""
    text: str = Field(..., min_length=1, max_length=50_000)
    session_id: Optional[str] = None
    sensitivity: str = Field(default="high", pattern="^(high|medium|low)$")
    redaction_mode: str = Field(default="xxx", pattern="^(token|xxx)$")


class SanitizeResponse(BaseModel):
    """POST /api/v1/sanitize response body."""
    sanitized_text: str
    session_id: str
    entities_found: int
    risk_level: str  # HIGH | MEDIUM | LOW
    entity_summary: list[EntitySummaryItem] = []


# ── Restore ───────────────────────────────────────────────────────

class RestoreRequest(BaseModel):
    """POST /api/v1/restore request body."""
    text: str = Field(..., min_length=1, max_length=100_000)
    session_id: str


class RestoreResponse(BaseModel):
    """POST /api/v1/restore response body."""
    restored_text: str


# ── Health ────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """GET /api/v1/health response body."""
    status: str = "ok"
    version: str = "1.0.0"


# ── Stats ─────────────────────────────────────────────────────────

class StatsResponse(BaseModel):
    """GET /api/v1/stats/{session_id} response body."""
    session_id: str
    entities_found: int
    risk_level: str
    entity_breakdown: dict[str, int] = {}


# ── File Upload ───────────────────────────────────────────────────

class SanitizeFileResponse(BaseModel):
    """POST /api/v1/sanitize-file response body."""
    sanitized_text: str
    session_id: str
    entities_found: int
    risk_level: str
    entity_summary: list[EntitySummaryItem] = []
    entity_details: list[dict] = []  # [{type, text}, ...] for warning modal
    file_type: str  # "pdf" | "image" | "text" | "docx"
    original_text: str = ""  # extracted text before redaction
