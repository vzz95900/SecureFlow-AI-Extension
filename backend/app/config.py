"""
SecureFlow AI — Application Configuration.
Loads settings from environment variables / .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # API Security
    api_key: str = ""

    # CORS
    allowed_origins: str = "*"

    # Database
    database_url: str = "sqlite+aiosqlite:///./secureflow.db"

    # spaCy
    spacy_model: str = "en_core_web_sm"

    # BERT Risk Classifier
    bert_model_path: str = "./models/bert_risk_classifier"
    bert_confidence_threshold: float = 0.6

    # Token Map
    token_map_ttl_minutes: int = 30

    # Rate Limiting
    rate_limit: str = "60/minute"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()
