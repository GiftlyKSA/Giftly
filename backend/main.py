from fastapi import FastAPI, Request, HTTPException, status, WebSocket, WebSocketDisconnect, Depends
from database import engine, Base, AsyncSessionLocal
from routers import auth, admin, orders, cities, invoices, chat, wallets, payments, promocodes
from sqladmin import Admin
from admin import UserAdmin, CityAdmin, OrderAdmin, InvoiceAdmin, ConversationAdmin, MessageAdmin, WalletAdmin, PaymentAdmin, PromocodeAdmin
import base64
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import User, Conversation, Message, JWTToken
from fastapi.responses import JSONResponse
import os
import asyncio
import json
from typing import Dict, Set
from jose import JWTError, jwt
from config import settings

print(f"Current working directory: {os.getcwd()}")
print(f"Database URL: {engine.url}")

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
sqladmin = Admin(app, engine, title="Admin Dashboard")
sqladmin.add_view(UserAdmin)
sqladmin.add_view(CityAdmin)
sqladmin.add_view(OrderAdmin)
sqladmin.add_view(InvoiceAdmin)
sqladmin.add_view(WalletAdmin)
sqladmin.add_view(PaymentAdmin)
sqladmin.add_view(PromocodeAdmin)
sqladmin.add_view(ConversationAdmin)
sqladmin.add_view(MessageAdmin)

@app.get("/")
def read_root():
    return {"message": "Welcome to the API"}


class ConnectionManager:
    def __init__(self):
        # conversation_id -> set of websockets
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, conversation_id: int, user_id: int):
        await websocket.accept()
        if conversation_id not in self.active_connections:
            self.active_connections[conversation_id] = set()
        self.active_connections[conversation_id].add(websocket)

    def disconnect(self, websocket: WebSocket, conversation_id: int):
        if conversation_id in self.active_connections:
            self.active_connections[conversation_id].discard(websocket)
            if not self.active_connections[conversation_id]:
                del self.active_connections[conversation_id]

    async def broadcast_to_conversation(self, message: dict, conversation_id: int, exclude_websocket: WebSocket = None):
        if conversation_id in self.active_connections:
            for connection in self.active_connections[conversation_id]:
                if connection != exclude_websocket:
                    try:
                        await connection.send_json(message)
                    except:
                        # Connection might be closed, remove it
                        self.active_connections[conversation_id].discard(connection)


manager = ConnectionManager()


async def get_current_user_from_token(token: str, db: AsyncSession) -> User:
    """Extract user from JWT token for WebSocket authentication"""
    print(f"WebSocket auth: Validating token (length: {len(token)})")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        phone_number: str = payload.get("sub")
        token_type: str = payload.get("type")
        is_temp: bool = payload.get("temp", False)

        print(f"WebSocket auth: Token payload - phone: {phone_number}, type: {token_type}, temp: {is_temp}")

        if phone_number is None:
            print("WebSocket auth: No phone number in token")
            raise credentials_exception
        if token_type == "refresh":
            print("WebSocket auth: Refresh token not allowed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not allowed",
            )
    except JWTError as e:
        print(f"WebSocket auth: JWT decode error: {e}")
        raise credentials_exception

    # For temporary tokens (used during profile completion), skip database check
    if not is_temp:
        print("WebSocket auth: Checking permanent token in database")
        # Check if token exists in database and is not revoked
        jwt_token = await db.execute(
            select(JWTToken).where(
                JWTToken.access_token == token,
                JWTToken.is_revoked == False
            )
        )
        jwt_token = jwt_token.scalar_one_or_none()

        if not jwt_token:
            print("WebSocket auth: Token not found in database or revoked")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked or does not exist",
            )

        # Check if access token is expired
        from datetime import datetime
        if datetime.utcnow() > jwt_token.access_token_expires_at:
            print(f"WebSocket auth: Token expired. Now: {datetime.utcnow()}, Expires: {jwt_token.access_token_expires_at}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token expired",
            )
        print("WebSocket auth: Token validated successfully")
    else:
        print("WebSocket auth: Temporary token - skipping database check")

    user = await db.execute(select(User).where(User.phone_number == phone_number))
    user = user.scalar_one_or_none()
    if user is None:
        print(f"WebSocket auth: User not found for phone: {phone_number}")
        raise credentials_exception

    print(f"WebSocket auth: Authentication successful for user: {user.id} ({user.name})")
    return user


@app.websocket("/ws/chat/{conversation_id}")
async def websocket_chat(
    websocket: WebSocket,
    conversation_id: int,
    token: str
):
    """
    WebSocket endpoint for real-time chat.
    Authenticates user with JWT token and ensures they are a participant in the conversation.
    """
    print(f"WebSocket: New connection attempt for conversation {conversation_id}")

    db = AsyncSessionLocal()
    user = None
    try:
        # Authenticate user
        print(f"WebSocket: Starting authentication for token length: {len(token)}")
        user = await get_current_user_from_token(token, db)

        # Get conversation and check authorization
        conversation = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = conversation.scalar_one_or_none()

        if not conversation:
            print(f"WebSocket: Conversation {conversation_id} not found")
            await websocket.close(code=1008, reason="Conversation not found")
            return

        # Check if user is a participant
        if user.id not in [conversation.customer_id, conversation.courier_id]:
            print(f"WebSocket: User {user.id} not authorized for conversation {conversation_id}")
            await websocket.close(code=1008, reason="Not authorized for this conversation")
            return

        print(f"WebSocket: Authentication successful, connecting user {user.id} to conversation {conversation_id}")
        # Connect to WebSocket
        await manager.connect(websocket, conversation_id, user.id)

        while True:
            # Receive message from client
            data = await websocket.receive_json()

            # Validate message structure
            if not isinstance(data, dict) or "content" not in data:
                continue

            message_type = data.get("message_type", "text")

            # Create message in database
            new_message = Message(
                conversation_id=conversation_id,
                sender_id=user.id,
                content=data["content"],
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

            # Broadcast to other participants in the conversation
            await manager.broadcast_to_conversation(message_data, conversation_id, websocket)

    except WebSocketDisconnect:
        print(f"WebSocket: Client disconnected from conversation {conversation_id}")
        manager.disconnect(websocket, conversation_id)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket, conversation_id)
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
    finally:
        # Always close the database session
        await db.close()
        print(f"WebSocket: Database session closed for conversation {conversation_id}")
