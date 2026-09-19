"""
Security and observability response headers.

Nginx should also set these for static files; this middleware covers API responses.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        settings = get_settings()

        # Baseline security headers (safe on HTTP and HTTPS)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )
        response.headers.setdefault("X-XSS-Protection", "0")  # rely on CSP, not legacy XSS filter
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        # API is JSON-only; CSP above is intentionally strict for API responses.

        # Cross-Origin policies
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")

        # API responses may contain account or investment-screening data.
        response.headers.setdefault("Cache-Control", "no-store")

        # Observability / debugging (non-sensitive)
        response.headers.setdefault("X-Request-Id", request.headers.get("X-Request-Id", ""))
        response.headers.setdefault("X-App-Env", settings.app_env)

        # HSTS only when explicitly enabled (terminate TLS at nginx in production)
        if settings.enable_hsts:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        # Do not advertise server tech
        if "Server" in response.headers:
            del response.headers["Server"]

        return response
