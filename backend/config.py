"""
Application configuration using pydantic-settings.

Reads from backend/.env file. All settings are overridable via environment variables.
"""

import logging as _logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for SynChain backend."""

    database_url: str = "sqlite:///./supply_chain.db"
    cors_origins: list[str] = ["http://localhost:3000"]
    app_version: str = "3.1.0"
    debug: bool = False

    # E7: External API keys (empty = use synthetic fallback)
    # Set via environment variables or .env file.
    # When external_provider_mode="auto", the system uses a real provider
    # if its API key is non-empty, otherwise falls back to synthetic.
    newsapi_key: str = ""
    openweathermap_key: str = ""
    alphavantage_key: str = ""
    fred_key: str = ""

    # E7: Provider mode
    #   "auto"      — real if API key present, synthetic otherwise (default)
    #   "synthetic"  — always synthetic (ignores API keys)
    #   "real"       — always real (fails if key missing)
    external_provider_mode: str = "auto"

    # E8: Authentication settings
    # SECURITY: No default JWT secret. Must be provided via env var.
    # In debug mode, a deterministic dev-only key is used with a warning.
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # E9: Logging
    log_level: str = "INFO"
    log_format: str = "text"  # "json" for production, "text" for development

    # E9: Rate limiting (in-memory sliding window)
    rate_limit_enabled: bool = True
    rate_limit_auth: int = 10  # login/register per minute
    rate_limit_write: int = 30  # POST simulate per minute
    rate_limit_read: int = 120  # GET endpoints per minute
    rate_limit_admin: int = 20  # admin operations per minute

    # E9: Database pool (PostgreSQL only; ignored for SQLite)
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout: int = 30

    # E9: Production hardening
    allowed_hosts: list[str] = ["*"]
    secure_cookies: bool = False

    # E9: Audit log retention
    audit_archive_days: int = 90

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()

# ---------------------------------------------------------------------------
# Startup validation: enforce JWT secret in production
# ---------------------------------------------------------------------------
_DEV_JWT_KEY = "synchain-dev-only-not-for-production"

_startup_logger = _logging.getLogger("synchain.startup")

if not settings.jwt_secret_key:
    if settings.debug:
        _startup_logger.warning(
            "JWT_SECRET_KEY not set. Using dev-only fallback. "
            "DO NOT deploy with DEBUG=true."
        )
        settings.jwt_secret_key = _DEV_JWT_KEY
    else:
        raise RuntimeError(
            "FATAL: JWT_SECRET_KEY environment variable is required when DEBUG=false. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
elif settings.jwt_secret_key == _DEV_JWT_KEY and not settings.debug:
    # Key was explicitly set to the known dev fallback with DEBUG=false.
    # This is a misconfigured production deployment — crash early.
    raise RuntimeError(
        "FATAL: JWT_SECRET_KEY is set to the development fallback value. "
        "Generate a unique secret for production: "
        'python -c "import secrets; print(secrets.token_urlsafe(32))"'
    )
elif settings.jwt_secret_key == _DEV_JWT_KEY and settings.debug:
    _startup_logger.warning(
        "JWT_SECRET_KEY is the known dev fallback. "
        "DO NOT use this key in production."
    )
