from fastapi import FastAPI, Request, HTTPException, status, WebSocket, WebSocketDisconnect, Depends
from database import engine, Base, AsyncSessionLocal
from routers import auth, admin, orders, cities, invoices, chat, wallets, payments, promocodes
from sqladmin import Admin
from admin import UserAdmin, CityAdmin, OrderAdmin, InvoiceAdmin, ConversationAdmin, MessageAdmin, WalletAdmin, PaymentAdmin, PromocodeAdmin, ReviewAdmin
import base64
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import User, Conversation, Message
from fastapi.responses import JSONResponse
import os
from jose import JWTError, jwt
from config import settings
from websocket_manager import manager
from contextlib import asynccontextmanager

print(f"Current working directory: {os.getcwd()}")
print(f"Database URL: {engine.url}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)

from starlette.middleware.base import BaseHTTPMiddleware


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(orders.router, prefix="/orders", tags=["orders"])
app.include_router(cities.router, prefix="/cities", tags=["cities"])
app.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
app.include_router(payments.router, prefix="/payments", tags=["payments"])
app.include_router(promocodes.router, prefix="/promocodes", tags=["promocodes"])

# Middleware for admin authentication
@app.middleware("http")
async def admin_auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/admin"):
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Basic"}
            )

        try:
            encoded_credentials = auth_header.split(" ")[1]
            decoded_credentials = base64.b64decode(encoded_credentials).decode("utf-8")
            username, password = decoded_credentials.split(":", 1)

            async with AsyncSessionLocal() as db:
                user = await db.execute(
                    select(User).where(
                        User.admin_username == username,
                        User.is_admin == True,
                        User.role == 'Admin'
                    )
                )
                user = user.scalar_one_or_none()
                if not user or not bcrypt.checkpw(password.encode('utf-8'), user.admin_password_hash.encode('utf-8')):
                    return JSONResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content={"detail": "Invalid credentials"},
                        headers={"WWW-Authenticate": "Basic"}
                    )
        except:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid credentials"},
                headers={"WWW-Authenticate": "Basic"}
            )

    response = await call_next(request)
    return response

# Metadata reflection removed for async engine compatibility

# Create and mount SQLAdmin
from starlette.datastructures import URL
def https_url_for(context, name: str, **path_params):
    request: Request = context["request"]
    url: URL = request.url_for(name, **path_params)
    return str(url.replace(scheme="https"))
    
sqladmin = Admin(app, engine, title="Admin Dashboard", title="Admin Dashboard")
admin.templates.env.globals["url_for"] = https_url_for
@app.get("/test-scheme")
async def test_scheme(request: Request):
    return {"scheme": request.url.scheme, "url": str(request.url), "https_url_for": admin.templates.env}

sqladmin.add_view(UserAdmin)
sqladmin.add_view(CityAdmin)
sqladmin.add_view(OrderAdmin)
sqladmin.add_view(InvoiceAdmin)
sqladmin.add_view(WalletAdmin)
sqladmin.add_view(PaymentAdmin)
sqladmin.add_view(PromocodeAdmin)
sqladmin.add_view(ConversationAdmin)
sqladmin.add_view(MessageAdmin)
sqladmin.add_view(ReviewAdmin)

@app.get("/")
def read_root():
    return {"message": "Welcome to the API"}





async def get_user_from_token(token: str) -> User:
    """Extract user from JWT token for WebSocket authentication (stateless)"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        sub: str = payload.get("sub")
        if sub is None:
            raise credentials_exception
        token_type: str = payload.get("type")
        if token_type == "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not allowed",
            )
        user_id = int(sub)
    except (JWTError, ValueError):
        raise credentials_exception

    phone_number = payload.get("phone_number")
    role = payload.get("role")
    name = payload.get("name")
    is_verified = payload.get("is_verified", False)

    return User(
        id=user_id,
        phone_number=phone_number,
        role=role,
        name=name,
        is_verified=is_verified
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    General WebSocket endpoint for real-time events.
    Authenticates user with JWT token and handles room-based messaging.
    """
    print(f"WebSocket: New connection attempt")

    db = AsyncSessionLocal()
    user = None
    try:
        # Authenticate user
        print(f"WebSocket: Starting authentication for token length: {len(token)}")
        user = await get_user_from_token(token)

        print(f"WebSocket: Authentication successful, connecting user {user.id}")
        # Connect to WebSocket
        await manager.connect(websocket, user.id)

        # Auto-join user-specific and role-specific rooms
        await manager.join_room(user.id, f"user_{user.id}")

        # Join city-specific courier room if user is a courier
        if user.role == "Courier":
            # Get user's city_id from database
            user_record = await db.execute(select(User).where(User.id == user.id))
            user_data = user_record.scalar_one_or_none()
            if user_data and user_data.city_id:
                await manager.join_room(user.id, f"couriers_city_{user_data.city_id}")
                print(f"WebSocket: Courier {user.id} joined city room couriers_city_{user_data.city_id}")

        while True:
            # Receive message from client
            data = await websocket.receive_json()
            print(f"WebSocket: Received message from user {user.id}: {data}")

            action = data.get("action")

            if action == "join_room":
                room = data.get("room")
                if room:
                    await manager.join_room(user.id, room)
                    print(f"WebSocket: User {user.id} joined room {room}")
                    await manager.send_to_user(user.id, {"action": "joined_room", "room": room})

            elif action == "leave_room":
                room = data.get("room")
                if room:
                    await manager.leave_room(user.id, room)
                    print(f"WebSocket: User {user.id} left room {room}")
                    await manager.send_to_user(user.id, {"action": "left_room", "room": room})

            elif action == "send_message":
                room = data.get("room")
                message_content = data.get("content")
                if room and message_content:
                    # For chat messages, we need to handle database insertion
                    if room.startswith("chat_"):
                        try:
                            conversation_id = int(room.split("_")[1])
                            # Verify user is participant
                            conversation = await db.execute(
                                select(Conversation).where(Conversation.id == conversation_id)
                            )
                            conversation = conversation.scalar_one_or_none()
                            if conversation and user.id in [conversation.customer_id, conversation.courier_id]:
                                message_type = data.get("message_type", "text")
                                # Create message in database
                                new_message = Message(
                                    conversation_id=conversation_id,
                                    sender_id=user.id,
                                    content=message_content,
                                    message_type=message_type,
                                    invoice_description=data.get("invoice_description"),
                                    invoice_gift_price=data.get("invoice_gift_price"),
                                    invoice_service_fee=data.get("invoice_service_fee"),
                                    invoice_delivery_fee=data.get("invoice_delivery_fee"),
                                    invoice_total=data.get("invoice_total")
                                )
                                db.add(new_message)
                                await db.commit()
                                await db.refresh(new_message)

                                # Prepare message to broadcast
                                message_data = {
                                    "event": "chat_message",
                                    "room": room,
                                    "data": {
                                        "id": new_message.id,
                                        "conversation_id": new_message.conversation_id,
                                        "sender_id": new_message.sender_id,
                                        "content": new_message.content,
                                        "message_type": new_message.message_type,
                                        "sent_at": new_message.sent_at.isoformat(),
                                        "invoice_description": new_message.invoice_description,
                                        "invoice_gift_price": new_message.invoice_gift_price,
                                        "invoice_service_fee": new_message.invoice_service_fee,
                                        "invoice_delivery_fee": new_message.invoice_delivery_fee,
                                        "invoice_total": new_message.invoice_total
                                    }
                                }
                                await manager.broadcast_to_room(message_data, room, user.id)
                        except Exception as e:
                            print(f"WebSocket: Error sending chat message: {e}")

    except WebSocketDisconnect:
        print(f"WebSocket: Client disconnected for user {user.id if user else 'unknown'}")
        if user:
            manager.disconnect(user.id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if user:
            manager.disconnect(user.id)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
    finally:
        # Always close the database session
        await db.close()
        print(f"WebSocket: Database session closed")



# Mount SQLAdmin static assets
from websocket_events import emit_order_status_change, emit_chat_message