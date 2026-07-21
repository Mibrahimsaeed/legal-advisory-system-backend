"""
Security middleware — adds standard protective HTTP headers to every
response. These headers instruct browsers to avoid common attack vectors
(clickjacking, MIME sniffing, etc.). Part of Phase 6 hardening.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Prevent this API from being embedded in an <iframe> (clickjacking protection)
        response.headers["X-Frame-Options"] = "DENY"
        # Prevent browsers from guessing (sniffing) content types
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Control how much referrer information is sent with requests away from here
        response.headers["Referrer-Policy"] = "no-referrer"
        # Explicitly disable powerful browser features this API never needs
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response
