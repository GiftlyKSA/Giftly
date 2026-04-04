"""
Last-activity tracking middleware.

Updates User.last_activity on every authenticated request, debounced to at most
once per DEBOUNCE_SECONDS per user (avoids a DB write on every single request).
Uses an in-process dict for the debounce — good enough for single-process deployments.
For multi-process, swap the dict for a Redis SETEX call.
"""

import logging
import time
from datetime import datetime, timezone

from config import settings
from database import AsyncSessionLocal
from jose import JWTError, jwt
from sqlalchemy import update
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from models import User

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 60  # Only write to DB at most once per minute per user

# user_id (int) -> last_write timestamp (float, epoch seconds)
_last_write: dict[int, float] = {}


class LastActivityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return response

        try:
            payload = jwt.decode(
                auth.split(" ", 1)[1],
                settings.secret_key,
                algorithms=["HS256"],
                options={"verify_exp": False},
            )
            if payload.get("type") == "refresh":
                return response
            sub = payload.get("sub")
            if not sub:
                return response
            user_id = int(sub)
        except (JWTError, ValueError):
            return response

        now = time.monotonic()
        if (now - _last_write.get(user_id, 0)) < DEBOUNCE_SECONDS:
            return response  # Debounced — skip DB write

        _last_write[user_id] = now

        # Fire-and-forget: update last_activity without blocking the response
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(last_activity=datetime.now(timezone.utc))
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to update last_activity for user %s", user_id)

        return response
