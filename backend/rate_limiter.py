"""
In-memory sliding window rate limiter (Phase E9).

Concept:
  Sliding window algorithm tracks timestamps of recent requests per key
  (user_id or IP address). When a new request arrives, expired entries
  outside the window are pruned and the remaining count is checked
  against the limit. Returns 429 Too Many Requests with Retry-After
  header when exceeded.

  In-memory implementation is sufficient for single-instance deployment.
  Data resets on server restart (approved decision Q1: Option A).

Design:
  - Per-key tracking using a dict of deques (timestamp lists)
  - Thread-safe via a simple lock
  - Configurable per-category limits from settings
  - FastAPI dependency injection pattern
"""

import logging
import threading
import time
from collections import defaultdict, deque

from config import settings
from fastapi import HTTPException, Request, status

logger = logging.getLogger("synchain.ratelimit")

# ---------------------------------------------------------------------------
# Rate limit categories
# ---------------------------------------------------------------------------

RATE_CATEGORIES = {
    "auth": {"limit": settings.rate_limit_auth, "window": 60},
    "write": {"limit": settings.rate_limit_write, "window": 60},
    "read": {"limit": settings.rate_limit_read, "window": 60},
    "admin": {"limit": settings.rate_limit_admin, "window": 60},
}


# ---------------------------------------------------------------------------
# Sliding Window Store
# ---------------------------------------------------------------------------


class SlidingWindowStore:
    """
    Thread-safe in-memory sliding window counter.

    Stores request timestamps per key. On each check, prunes expired
    entries and returns whether the limit is exceeded.
    """

    def __init__(self):
        self._store: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(
        self, key: str, limit: int, window_seconds: int
    ) -> tuple[bool, int, float]:
        """
        Check if a request is allowed under the rate limit.

        Returns:
            (allowed, remaining, retry_after_seconds)
        """
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            timestamps = self._store[key]

            # Prune expired entries
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            if len(timestamps) >= limit:
                # Calculate when the oldest entry expires
                retry_after = timestamps[0] + window_seconds - now
                return False, 0, max(retry_after, 1.0)

            # Record this request
            timestamps.append(now)
            remaining = limit - len(timestamps)
            return True, remaining, 0.0

    def clear(self):
        """Clear all stored data (for testing)."""
        with self._lock:
            self._store.clear()


# Singleton store
_store = SlidingWindowStore()


def get_store() -> SlidingWindowStore:
    """Get the global rate limit store (testable via override)."""
    return _store


# ---------------------------------------------------------------------------
# Rate limit dependency
# ---------------------------------------------------------------------------


def rate_limit(category: str):
    """
    FastAPI dependency that enforces rate limiting.

    Usage:
        @router.post("/endpoint", dependencies=[Depends(rate_limit("write"))])

    The key is derived from:
      1. Authenticated user: "user:{user_id}"
      2. Unauthenticated: "ip:{client_ip}"
    """
    cat = RATE_CATEGORIES.get(category)
    if cat is None:
        raise ValueError(f"Unknown rate limit category: {category}")

    async def _check(request: Request):
        if not settings.rate_limit_enabled:
            return

        # Derive rate limit key
        # Check for auth context (set by auth dependency)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            key = f"user:{user_id}:{category}"
        else:
            # Fall back to client IP
            client_ip = request.client.host if request.client else "unknown"
            key = f"ip:{client_ip}:{category}"

        store = get_store()
        allowed, remaining, retry_after = store.is_allowed(
            key, cat["limit"], cat["window"]
        )

        if not allowed:
            logger.warning(
                "Rate limit exceeded: key=%s category=%s limit=%d",
                key,
                category,
                cat["limit"],
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {int(retry_after)} seconds.",
                headers={"Retry-After": str(int(retry_after))},
            )

    return _check
