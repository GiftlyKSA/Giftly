"""Shared async Redis client singleton.

Initialised in main.py lifespan when use_redis_broker=true.
Falls back to None when Redis is disabled (dev / test).
"""
from __future__ import annotations

import logging

from redis.asyncio import Redis

_redis: Redis | None = None


async def init_redis(url: str) -> None:
    global _redis
    _redis = Redis.from_url(url, decode_responses=True)
    try:
        await _redis.ping()
    except Exception as e:
        logging.warning("Redis ping failed — rate limiting will use in-memory fallback: %s", e)
        _redis = None


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_redis() -> Redis | None:
    return _redis


async def redis_rate_check(key: str, max_requests: int, window_seconds: int) -> bool:
    """Atomically increment a counter and return True if limit exceeded.

    Uses INCR + EXPIRE NX so the window starts on the first hit.
    Returns True  → caller should reject (rate limited).
    Returns False → caller should allow.
    Falls back to allow-all when Redis is unavailable.
    """
    r = get_redis()
    if r is None:
        return False
    try:
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        results = await pipe.execute()
        count = results[0]
        return count > max_requests
    except Exception as e:
        logging.warning("Redis rate check failed — allowing request: %s", e)
        return False
