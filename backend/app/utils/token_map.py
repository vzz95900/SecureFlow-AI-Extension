"""
SecureFlow AI — Reversible Token Map Manager.
Stores PII ↔ token mappings per session, with TTL-based expiry.
"""

import uuid
import time
from threading import Lock
from typing import Optional

from app.config import get_settings


class TokenMapManager:
    """In-memory token map store keyed by session_id with TTL expiry."""

    def __init__(self):
        self._store: dict[str, dict] = {}
        self._timestamps: dict[str, float] = {}
        self._lock = Lock()

    def create_session(self, session_id: Optional[str] = None) -> str:
        """Create a new session and return its ID."""
        if not session_id:
            session_id = uuid.uuid4().hex[:16]
        with self._lock:
            self._store[session_id] = {}
            self._timestamps[session_id] = time.time()
        return session_id

    def store(self, session_id: str, token: str, original: str):
        """Map a redaction token to its original text."""
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = {}
                self._timestamps[session_id] = time.time()
            self._store[session_id][token] = original

    def store_map(self, session_id: str, token_map: dict[str, str]):
        """Store an entire token map for a session."""
        with self._lock:
            self._store[session_id] = token_map
            self._timestamps[session_id] = time.time()

    def get_map(self, session_id: str) -> dict[str, str]:
        """Retrieve the token map for a session."""
        self._cleanup_expired()
        with self._lock:
            return dict(self._store.get(session_id, {}))

    def get_original(self, session_id: str, token: str) -> Optional[str]:
        """Look up the original text for a single token."""
        with self._lock:
            return self._store.get(session_id, {}).get(token)

    def delete_session(self, session_id: str):
        """Remove a session's token map."""
        with self._lock:
            self._store.pop(session_id, None)
            self._timestamps.pop(session_id, None)

    def _cleanup_expired(self):
        """Remove sessions older than TTL."""
        settings = get_settings()
        ttl_seconds = settings.token_map_ttl_minutes * 60
        now = time.time()
        with self._lock:
            expired = [
                sid for sid, ts in self._timestamps.items()
                if now - ts > ttl_seconds
            ]
            for sid in expired:
                del self._store[sid]
                del self._timestamps[sid]

    @property
    def active_sessions(self) -> int:
        """Number of active sessions."""
        self._cleanup_expired()
        return len(self._store)


# Global singleton
token_map_manager = TokenMapManager()
