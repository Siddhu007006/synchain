"""
Rate-limited HTTP client for external API providers.

Provides a shared HTTP client with:
  - Per-domain rate limiting (configurable requests/minute)
  - Exponential backoff on 429 / 5xx responses
  - Global request timeout
  - API key stripping from log output

Design Decision D4 (E7 Architecture Report):
  Uses httpx synchronous client. Providers run inside the background
  scheduler's synchronous refresh_all_providers(), not in async request
  handlers.

Usage:
    client = RateLimitedClient(timeout=10.0)
    resp = client.get("https://api.example.com/data", params={"key": "..."})
"""

import logging
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger("synchain.http_client")

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


@dataclass
class _RateBucket:
    """Token-bucket rate limiter for a single domain."""

    max_requests: int = 10  # per window
    window_seconds: float = 60.0  # 1 minute
    _timestamps: list[float] = field(default_factory=list)

    def acquire(self) -> float:
        """
        Acquire a slot. Returns wait time in seconds (0.0 = immediate).

        Evicts timestamps older than the window, then checks capacity.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._timestamps = [t for t in self._timestamps if t > cutoff]

        if len(self._timestamps) < self.max_requests:
            self._timestamps.append(now)
            return 0.0

        # Full — calculate wait until oldest expires
        oldest = self._timestamps[0]
        wait = (oldest + self.window_seconds) - now
        return max(0.0, wait)


# ---------------------------------------------------------------------------
# Default rate limits per API domain
# ---------------------------------------------------------------------------

DEFAULT_RATE_LIMITS: dict[str, tuple[int, float]] = {
    # (max_requests_per_window, window_seconds)
    "newsapi.org": (10, 60.0),  # 100/day → ~10/min is safe
    "api.openweathermap.org": (10, 60.0),  # 1000/day → generous
    "www.alphavantage.co": (5, 60.0),  # 5/min hard limit
    "api.stlouisfed.org": (20, 60.0),  # No hard limit, be polite
}


# ---------------------------------------------------------------------------
# Sanitizer — strip API keys from log output
# ---------------------------------------------------------------------------

_SENSITIVE_PARAMS = {"apikey", "apiKey", "api_key", "appid", "access_key"}


def _sanitize_url(url: str) -> str:
    """Strip API key query params from URL for safe logging."""
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(url)
    if not parsed.query:
        return url

    params = parse_qs(parsed.query, keep_blank_values=True)
    sanitized = {}
    for k, v in params.items():
        if k.lower() in {p.lower() for p in _SENSITIVE_PARAMS}:
            sanitized[k] = ["***"]
        else:
            sanitized[k] = v

    clean_query = urlencode(sanitized, doseq=True)
    return urlunparse(parsed._replace(query=clean_query))


# ---------------------------------------------------------------------------
# RateLimitedClient
# ---------------------------------------------------------------------------

# Retry config
MAX_RETRIES = 3
BACKOFF_BASE = 1.0  # seconds
BACKOFF_FACTOR = 2.0  # exponential

# HTTP status codes that trigger retry
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class RateLimitedClient:
    """
    HTTP client with per-domain rate limiting and retry logic.

    Features:
      - Token-bucket rate limiting per domain
      - Exponential backoff on 429/5xx
      - Configurable timeout (default 10s)
      - API key stripping from log output
      - Never raises on failure — returns None

    Usage:
        client = RateLimitedClient(timeout=10.0)
        data = client.get_json("https://api.example.com/data", params={"key": "..."})
    """

    def __init__(self, timeout: float = 10.0):
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "SynChain/3.1.0"},
        )
        self._buckets: dict[str, _RateBucket] = {}

    def _get_bucket(self, domain: str) -> _RateBucket:
        """Get or create rate limit bucket for domain."""
        if domain not in self._buckets:
            limit = DEFAULT_RATE_LIMITS.get(domain, (10, 60.0))
            self._buckets[domain] = _RateBucket(
                max_requests=limit[0],
                window_seconds=limit[1],
            )
        return self._buckets[domain]

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse

        return urlparse(url).netloc

    def get(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response | None:
        """
        GET request with rate limiting and retry.

        Returns httpx.Response on success, None on failure.
        Never raises.
        """
        domain = self._extract_domain(url)
        bucket = self._get_bucket(domain)
        safe_url = _sanitize_url(url)

        for attempt in range(MAX_RETRIES):
            # Rate limit check
            wait = bucket.acquire()
            if wait > 0:
                logger.info(
                    "Rate limit: waiting %.1fs for %s",
                    wait,
                    domain,
                )
                time.sleep(wait)
                bucket.acquire()  # Re-acquire after wait

            try:
                logger.debug("HTTP GET %s (attempt %d)", safe_url, attempt + 1)
                response = self._client.get(url, params=params, headers=headers)

                if response.status_code == 200:
                    logger.debug(
                        "HTTP 200 from %s (%d bytes)",
                        domain,
                        len(response.content),
                    )
                    return response

                if response.status_code in RETRYABLE_STATUS:
                    backoff = BACKOFF_BASE * (BACKOFF_FACTOR**attempt)
                    logger.warning(
                        "HTTP %d from %s, retrying in %.1fs (attempt %d/%d)",
                        response.status_code,
                        domain,
                        backoff,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    time.sleep(backoff)
                    continue

                # Non-retryable error
                logger.warning(
                    "HTTP %d from %s (non-retryable)",
                    response.status_code,
                    domain,
                )
                return None

            except httpx.TimeoutException:
                backoff = BACKOFF_BASE * (BACKOFF_FACTOR**attempt)
                logger.warning(
                    "Timeout from %s, retrying in %.1fs (attempt %d/%d)",
                    domain,
                    backoff,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(backoff)

            except httpx.HTTPError as e:
                logger.warning("HTTP error from %s: %s", domain, str(e))
                return None

        logger.error("All %d retries exhausted for %s", MAX_RETRIES, safe_url)
        return None

    def get_json(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> dict | None:
        """
        GET request, parse JSON response.

        Returns parsed dict on success, None on failure.
        """
        response = self.get(url, params=params, headers=headers)
        if response is None:
            return None

        try:
            return response.json()
        except Exception:
            logger.warning("Failed to parse JSON from %s", self._extract_domain(url))
            return None

    def close(self):
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
