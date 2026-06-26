"""
HTTP middleware stack (Phase E9).

Provides:
  - RequestIDMiddleware: Generates UUID per request, propagates via contextvars
  - TimingMiddleware: Logs request duration, method, path, status code
  - SecurityHeadersMiddleware: Adds protective HTTP headers

Concept:
  Starlette middleware wraps every request/response cycle. Order matters —
  outermost middleware executes first on request and last on response.
  The RequestID is generated at entry and stored in a ContextVar so any
  function in the call stack (sync or async) can access it without explicit
  parameter passing.
"""

import logging
import time
import uuid

from logging_config import request_id_var
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("synchain.middleware")


# ---------------------------------------------------------------------------
# Request ID Middleware
# ---------------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Generate a unique request ID for every HTTP request.

    - Sets the `X-Request-Id` response header
    - Stores the ID in a ContextVar for structured logging
    - If the client sends `X-Request-Id`, it is used (passthrough)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Use client-provided ID or generate a new one
        req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        token = request_id_var.set(req_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = req_id
            return response
        finally:
            request_id_var.reset(token)


# ---------------------------------------------------------------------------
# Timing Middleware
# ---------------------------------------------------------------------------


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Log request duration, method, path, and status code.

    Emits a single structured log line per request at INFO level.
    Adds `X-Response-Time` header (milliseconds).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        # Skip health endpoints to reduce noise
        if request.url.path not in ("/health", "/live", "/ready", "/"):
            logger.info(
                "%s %s -> %d (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

        response.headers["X-Response-Time"] = f"{duration_ms:.1f}ms"
        return response


# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add protective HTTP headers to every response.

    Headers:
      - X-Content-Type-Options: nosniff — prevents MIME type sniffing
      - X-Frame-Options: DENY — prevents clickjacking
      - X-XSS-Protection: 0 — modern browsers use CSP instead
      - Referrer-Policy: strict-origin-when-cross-origin
      - Strict-Transport-Security: max-age=31536000 (HTTPS enforcement)
    """

    def __init__(self, app, enable_hsts: bool = False):
        super().__init__(app)
        self.enable_hsts = enable_hsts

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response
