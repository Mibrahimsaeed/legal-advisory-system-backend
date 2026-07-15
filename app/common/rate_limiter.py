"""
Per-user rate limiting to prevent chat endpoint misuse.

Currently backed by an in-memory dict (fine for a single dev server process).
For production with multiple server processes, swap this for Redis (the
project already has settings.redis_url configured) so limits are shared
across processes — only this file would need to change.
"""

import time
from collections import defaultdict

from app.common.exceptions import AppException
from fastapi import status

_request_log: dict[str, list[float]] = defaultdict(list)

MAX_REQUESTS_PER_WINDOW = 20
WINDOW_SECONDS = 60


def check_rate_limit(user_id: str) -> None:
    """Raises 429 if the user has exceeded the allowed requests in the current window."""
    now = time.time()
    window_start = now - WINDOW_SECONDS

    recent_requests = [t for t in _request_log[user_id] if t > window_start]
    _request_log[user_id] = recent_requests

    if len(recent_requests) >= MAX_REQUESTS_PER_WINDOW:
        raise AppException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Rate limit exceeded: max {MAX_REQUESTS_PER_WINDOW} requests per "
            f"{WINDOW_SECONDS} seconds. Please slow down.",
        )

    _request_log[user_id].append(now)
