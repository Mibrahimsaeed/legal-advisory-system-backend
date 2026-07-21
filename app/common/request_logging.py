"""
Request logging middleware — records every API request with its method,
path, status code, and how long it took. This is the structured
monitoring foundation from Phase 6: with these logs you can spot slow
endpoints, error spikes, and unusual traffic patterns.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from config.logging import get_logger

logger = get_logger("request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response
