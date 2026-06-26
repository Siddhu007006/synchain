"""
Security utilities for authentication (Phase E8).

Provides:
  - Password hashing (bcrypt)
  - JWT token creation and verification
  - API key generation and hashing

Design Decision: JWT tokens contain only user_id and org_id.
Role is NOT embedded in the token to avoid stale authorization.
Role is loaded from the database on every request via the
get_current_user dependency.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from config import settings

logger = logging.getLogger("synchain.auth")


# ---------------------------------------------------------------------------
# Password hashing (bcrypt)
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        logger.warning("Password verification failed (malformed hash)")
        return False


# ---------------------------------------------------------------------------
# JWT token management
#
# Token payload:
#   sub: user_id (int as string)
#   org: org_id (int)
# type: "access" | "refresh"
#   exp: expiration timestamp
#   iat: issued at timestamp
#
# Note: role is deliberately excluded. It is loaded from the DB
# on each request to prevent stale authorization after role changes.
# ---------------------------------------------------------------------------


def create_access_token(user_id: int, org_id: int) -> str:
    """Create a short-lived access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "org": org_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def create_refresh_token(user_id: int) -> str:
    """
    Create a long-lived refresh token.

    Refresh tokens carry only the user_id (no org). The org is
    re-selected during the refresh flow so users can switch orgs.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_refresh_token_expire_days),
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_token(token: str) -> dict | None:
    """
    Decode and verify a JWT token.

    Returns the payload dict on success, or None on failure
    (expired, invalid signature, malformed).
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug("Invalid token: %s", e)
        return None


# ---------------------------------------------------------------------------
# API key management
#
# Keys are generated with cryptographic randomness (secrets module).
# The full key is returned once at creation. Only the bcrypt hash
# and a prefix (first 8 chars) are stored in the database.
# ---------------------------------------------------------------------------

API_KEY_PREFIX = "sc_live_"


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.

    Returns:
        (full_key, key_hash, key_prefix)
        - full_key: the complete key to return to the user (once)
        - key_hash: bcrypt hash for storage
        - key_prefix: first 8 chars of the random part for identification
    """
    random_part = secrets.token_urlsafe(32)
    full_key = f"{API_KEY_PREFIX}{random_part}"
    key_hash = hash_api_key(full_key)
    key_prefix = f"{API_KEY_PREFIX}{random_part[:8]}"
    return full_key, key_hash, key_prefix


def hash_api_key(key: str) -> str:
    """
    Hash an API key for storage.

    Uses SHA-256 instead of bcrypt for API keys because:
    - API keys are high-entropy (cryptographically random)
    - bcrypt is designed for low-entropy passwords
    - SHA-256 is faster for high-entropy inputs
    - We need to look up keys by hash (bcrypt salts make this impossible)
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def verify_api_key(key: str, stored_hash: str) -> bool:
    """Verify an API key against its stored SHA-256 hash."""
    return hash_api_key(key) == stored_hash
