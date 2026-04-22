"""Simple in-memory per-IP rate limiter for public endpoints."""
import time
from collections import defaultdict

from fastapi import HTTPException, Request


def make_ip_rate_limiter(max_requests: int, window_seconds: float):
    """Return a FastAPI dependency that limits `max_requests` per `window_seconds` per IP."""
    _timestamps: dict[str, list[float]] = defaultdict(list)

    async def _limiter(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        valid = [t for t in _timestamps[ip] if now - t < window_seconds]
        _timestamps[ip] = valid
        if len(valid) >= max_requests:
            raise HTTPException(status_code=429, detail="Too many requests")
        _timestamps[ip].append(now)

    return _limiter
