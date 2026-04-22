import base64
import hashlib
import html
import logging
import time
from contextlib import asynccontextmanager

import bcrypt
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from utils.admin.admin import (
    AdminAdmin,
    CityAdmin,
    ConversationAdmin,
    CourierReviewAdmin,
    InvoiceAdmin,
    MessageAdmin,
    OrderAdmin,
    PaymentAdmin,
    PromocodeAdmin,
    UserAdmin,
    WalletAdmin,
)
from utils.database.config import settings
from utils.database.database import AsyncSessionLocal, engine
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import JSONResponse, RedirectResponse
from jose import JWTError, jwt
from sqladmin import Admin as SQLAdmin
from sqlalchemy import select
from utils.websocket.websocket_manager import manager

import tasks.email_tasks  # noqa: F401 — registers task decorators with the broker
from middleware.activity import LastActivityMiddleware
from middleware.logging import RequestLoggingMiddleware
from models import Admin, Conversation, CourierProfile, Message, User
from models.enums import UserRole
from routers import (
    admin,
    auth,
    chat,
    cities,
    couriers,
    events,
    invoices,
    orders,
    payments,
    promocodes,
    wallets,
)
from tasks.broker import broker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is owned by Alembic — run `uv run alembic upgrade head` to apply migrations.
    # Start the broker connection (skipped automatically inside the worker process)
    if not broker.is_worker_process:
        await broker.startup()
    yield
    if not broker.is_worker_process:
        await broker.shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging + activity tracking
app.add_middleware(LastActivityMiddleware)
app.add_middleware(RequestLoggingMiddleware)


# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            f"max-age={settings.hsts_max_age_seconds}; includeSubDomains"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "object-src 'none'; frame-ancestors 'none';"
        )
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# Force HTTPS for all requests
class ForceHTTPSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Check if request is HTTP and redirect to HTTPS
        if request.url.scheme == "http" and not settings.debug:
            https_url = str(request.url).replace("http://", "https://", 1)
            return RedirectResponse(
                url=https_url, status_code=status.HTTP_301_MOVED_PERMANENTLY
            )

        # For HTTPS requests, continue normally
        response = await call_next(request)
        return response


app.add_middleware(ForceHTTPSMiddleware)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(orders.router, prefix="/orders", tags=["orders"])
app.include_router(cities.router, prefix="/cities", tags=["cities"])
app.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
app.include_router(payments.router, prefix="/payments", tags=["payments"])
app.include_router(promocodes.router, prefix="/promocodes", tags=["promocodes"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(couriers.router, prefix="/couriers", tags=["couriers"])


# ---------------------------------------------------------------------------
# Admin middleware (Basic auth gate for /admin/* routes)
# Cache successful bcrypt verifications for 60 s to avoid bcrypt DoS on static assets
# ---------------------------------------------------------------------------

_admin_auth_cache: dict[str, float] = {}  # sha256(Authorization) -> expiry monotonic
_ADMIN_AUTH_CACHE_TTL = 60  # seconds


@app.middleware("http")
async def admin_auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/admin"):
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Basic"},
            )

        now = time.monotonic()
        cache_key = hashlib.sha256(auth_header.encode()).hexdigest()

        # Evict expired entries (admin panel has few users — O(n) is fine)
        expired = [k for k, v in _admin_auth_cache.items() if v <= now]
        for k in expired:
            del _admin_auth_cache[k]

        if _admin_auth_cache.get(cache_key, 0) > now:
            return await call_next(request)

        try:
            encoded_credentials = auth_header.split(" ")[1]
            decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
            username, password = decoded_credentials.split(":", 1)

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Admin).where(
                        Admin.username == username, Admin.is_active == True
                    )
                )
                admin = result.scalar_one_or_none()
                if not admin or not bcrypt.checkpw(
                    password.encode("utf-8"), admin.password_hash.encode("utf-8")
                ):
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Invalid credentials"},
                        headers={"WWW-Authenticate": "Basic"},
                    )

            _admin_auth_cache[cache_key] = now + _ADMIN_AUTH_CACHE_TTL
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid credentials"},
                headers={"WWW-Authenticate": "Basic"},
            )

    response = await call_next(request)
    return response


# ---------------------------------------------------------------------------
# SQLAdmin
# ---------------------------------------------------------------------------

sqladmin = SQLAdmin(app, engine, title="Admin Dashboard")

sqladmin.add_view(UserAdmin)
sqladmin.add_view(AdminAdmin)
sqladmin.add_view(CityAdmin)
sqladmin.add_view(OrderAdmin)
sqladmin.add_view(InvoiceAdmin)
sqladmin.add_view(WalletAdmin)
sqladmin.add_view(PaymentAdmin)
sqladmin.add_view(PromocodeAdmin)
sqladmin.add_view(ConversationAdmin)
sqladmin.add_view(MessageAdmin)
sqladmin.add_view(CourierReviewAdmin)


# ---------------------------------------------------------------------------
# Misc endpoints
# ---------------------------------------------------------------------------


@app.get("/")
def read_root():
    return {"message": "Welcome to the API"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# WebSocket helpers
# ---------------------------------------------------------------------------


async def get_user_from_token(token: str) -> User:
    """Extract user from JWT token for WebSocket authentication (stateless)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        sub: str = payload.get("sub")
        if sub is None:
            raise credentials_exception
        if payload.get("type") == "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not allowed",
            )
        user_id = int(sub)
    except (JWTError, ValueError):
        raise credentials_exception

    return User(
        id=user_id,
        phone_number=payload.get("phone_number"),
        role=payload.get("role"),
        name=payload.get("name"),
        is_verified=payload.get("is_verified", False),
    )


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    General WebSocket endpoint for real-time events.
    Authenticates user with JWT token and handles room-based messaging.
    """
    db = AsyncSessionLocal()
    user = None
    try:
        user = await get_user_from_token(token)
        await manager.connect(websocket, user.id)
        await manager.join_room(user.id, f"user_{user.id}")

        # Courier room join: only approved + available couriers
        if user.role == UserRole.COURIER.value:
            profile_record = await db.execute(
                select(CourierProfile).where(CourierProfile.user_id == user.id)
            )
            profile = profile_record.scalar_one_or_none()
            if (
                profile
                and profile.city_id
                and profile.is_approved
                and profile.is_available
            ):
                await manager.join_room(user.id, f"couriers_city_{profile.city_id}")

        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "join_room":
                room = data.get("room")
                # Only allow users to join their own personal room or chat rooms
                # they are a participant of — prevents IDOR/eavesdropping
                allowed = False
                if room == f"user_{user.id}":
                    allowed = True
                elif room and room.startswith("chat_"):
                    try:
                        conv_id = int(room.split("_")[1])
                        conv_check = await db.execute(
                            select(Conversation).where(
                                Conversation.id == conv_id,
                            )
                        )
                        conv = conv_check.scalar_one_or_none()
                        if conv and user.id in [conv.customer_id, conv.courier_id]:
                            allowed = True
                    except (ValueError, IndexError):
                        pass
                if allowed:
                    await manager.join_room(user.id, room)
                    await manager.send_to_user(
                        user.id, {"action": "joined_room", "room": room}
                    )

            elif action == "leave_room":
                room = data.get("room")
                if room:
                    await manager.leave_room(user.id, room)
                    await manager.send_to_user(
                        user.id, {"action": "left_room", "room": room}
                    )

            elif action == "leave_all_rooms":
                manager.disconnect(user.id)
                await manager.send_to_user(user.id, {"action": "left_all_rooms"})
            elif action == "send_message":
                room = data.get("room")
                message_content = data.get("content")
                # Basic input sanitization to prevent injection attacks
                if room and message_content and room.startswith("chat_"):
                    # Limit length, strip control characters, then HTML-escape to prevent XSS
                    if len(message_content) > 1000:
                        message_content = message_content[:1000] + "..."
                    message_content = "".join(
                        char
                        for char in message_content
                        if ord(char) >= 32 or char in "\n\r\t"
                    )
                    message_content = html.escape(message_content)
                    try:
                        conversation_id = int(room.split("_")[1])
                        conv_result = await db.execute(
                            select(Conversation).where(
                                Conversation.id == conversation_id
                            )
                        )
                        conversation = conv_result.scalar_one_or_none()
                        if conversation and user.id in [
                            conversation.customer_id,
                            conversation.courier_id,
                        ]:
                            new_message = Message(
                                conversation_id=conversation_id,
                                sender_id=user.id,
                                content=message_content,
                                message_type=data.get("message_type", "text"),
                            )
                            db.add(new_message)
                            await db.commit()
                            await db.refresh(new_message)

                            await manager.broadcast_to_room(
                                {
                                    "event": "chat_message",
                                    "room": room,
                                    "data": {
                                        "id": new_message.id,
                                        "conversation_id": new_message.conversation_id,
                                        "sender_id": new_message.sender_id,
                                        "content": new_message.content,
                                        "message_type": new_message.message_type,
                                        "sent_at": new_message.sent_at.isoformat(),
                                    },
                                },
                                room,
                                user.id,
                            )
                    except Exception as e:
                        logging.error(f"WebSocket error sending chat message: {str(e)}")

    except WebSocketDisconnect:
        if user:
            manager.disconnect(user.id)
    except Exception as e:
        logging.error(f"WebSocket error: {str(e)}")
        if user:
            manager.disconnect(user.id)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
    finally:
        await db.close()
