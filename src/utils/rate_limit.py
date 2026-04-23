"""Per-IP rate limiter for public endpoints.

Uses Redis INCR+EXPIRE when Redis is available (production multi-worker safe).
Falls back to an in-memory sliding window when Redis is not configured (dev/test).
"""
import time
from collections import defaultdict

from fastapi import HTTPException, Request

from utils.redis_client import redis_rate_check


def make_ip_rate_limiter(max_requests: int, window_seconds: float):
    """Return a FastAPI dependency that limits `max_requests` per `window_seconds` per IP."""
    _ns = f"rl:ip:{max_requests}:{int(window_seconds)}"
    _timestamps: dict[str, list[float]] = defaultdict(list)

    async def _limiter(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"

        # Redis path (multi-worker safe)
        key = f"{_ns}:{ip}"
        if await redis_rate_check(key, max_requests, int(window_seconds)):
            raise HTTPException(status_code=429, detail="Too many requests")

        # In-memory fallback (dev/test — Redis unavailable)
        # redis_rate_check returns False when Redis is down, so we double-check locally
        from utils.redis_client import get_redis
        if get_redis() is None:
            now = time.monotonic()
            valid = [t for t in _timestamps[ip] if now - t < window_seconds]
            _timestamps[ip] = valid
            if len(valid) >= max_requests:
                raise HTTPException(status_code=429, detail="Too many requests")
            _timestamps[ip].append(now)

    return _limiter
