"""
Structured JSON request logging middleware.

Emits one log line per request:
  {"request_id": "...", "method": "GET", "path": "/orders/", "status_code": 200,
   "duration_ms": 14.3, "user_id": "42"}
"""

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from jose import jwt, JWTError

from config import settings

logger = logging.getLogger("api.request")

# One-time basic config if no handler is set yet
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        # Extract user_id from Bearer token without blocking the request
        user_id = None
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            try:
                payload = jwt.decode(
                    auth.split(" ", 1)[1],
                    settings.secret_key,
                    algorithms=["HS256"],
                    options={"verify_exp": False},   # just reading claims, not validating here
                )
                if payload.get("type") != "refresh":
                    user_id = payload.get("sub")
            except JWTError:
                pass

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(json.dumps({
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
        }))
        return response
