from datetime import datetime, timedelta
from typing import Optional
import random
import string
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from models import User, JWTToken
from config import settings
from database import get_db
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

async def authenticate_user(db: AsyncSession, phone_number: str, password: str):
    user = await get_user_by_phone(db, phone_number)
    if not user:
        return False
    if not verify_password(password, user.admin_password_hash):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)  # Refresh token lasts 7 days
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    return encoded_jwt

async def create_jwt_tokens_async(db: AsyncSession, user: User):
    """Create and store JWT tokens for a user"""
    # Create tokens with 60-minute access token and 30-day refresh token
    access_token_expires = datetime.utcnow() + timedelta(minutes=60)
    refresh_token_expires = datetime.utcnow() + timedelta(days=30)

    # Include essential user data in JWT payload to avoid DB lookups
    access_token = create_access_token(
        data={
            "sub": user.phone_number,
            "user_id": user.id,
            "role": user.role,
            "name": user.name,
            "is_verified": user.is_verified
        },
        expires_delta=timedelta(minutes=60)
    )
    refresh_token = create_refresh_token(
        data={
            "sub": user.phone_number,
            "user_id": user.id,
            "role": user.role
        },
        expires_delta=timedelta(days=30)
    )

    # Store in database
    jwt_token = JWTToken(
        user_id=user.id,
        access_token=access_token,
        refresh_token=refresh_token,
        access_token_expires_at=access_token_expires,
        refresh_token_expires_at=refresh_token_expires,
        is_revoked=False
    )
    db.add(jwt_token)
    await db.commit()
    await db.refresh(jwt_token)

    return access_token, refresh_token

async def revoke_user_tokens(db: AsyncSession, user_id: int):
    """Revoke all tokens for a user"""
    from sqlalchemy import update
    await db.execute(
        update(JWTToken).where(
            JWTToken.user_id == user_id,
            JWTToken.is_revoked == False
        ).values(is_revoked=True)
    )
    await db.commit()

async def revoke_token_by_refresh_token(db: AsyncSession, refresh_token: str):
    """Revoke a specific token by refresh token"""
    from sqlalchemy import update
    await db.execute(
        update(JWTToken).where(
            JWTToken.refresh_token == refresh_token
        ).values(is_revoked=True)
    )
    await db.commit()

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

async def get_user_by_phone(db: AsyncSession, phone_number: str):
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.phone_number == phone_number))
    return result.scalar_one_or_none()

async def get_current_user(token: str = Depends(security), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token.credentials, settings.secret_key, algorithms=["HS256"])
        phone_number: str = payload.get("sub")
        if phone_number is None:
            raise credentials_exception
        token_type: str = payload.get("type")
        is_temp: bool = payload.get("temp", False)
        if token_type == "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not allowed for this endpoint",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise credentials_exception

    # For temporary tokens (used during profile completion), skip database check
    if not is_temp:
        from sqlalchemy import select
        # Check if token exists in database and is not revoked (single DB query)
        result = await db.execute(
            select(JWTToken).where(
                JWTToken.access_token == token.credentials,
                JWTToken.is_revoked == False
            )
        )
        jwt_token = result.scalar_one_or_none()

        if not jwt_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked or does not exist",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if access token is expired
        if datetime.utcnow() > jwt_token.access_token_expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Extract user data from JWT payload (no additional DB query needed)
    user_id = payload.get("user_id")
    role = payload.get("role")
    name = payload.get("name")
    is_verified = payload.get("is_verified", False)

    # Update user's last activity timestamp (async, non-blocking)
    # This tracks when the user was last active for session management
    if user_id:
        # Fire and forget - don't wait for this to complete
        import asyncio
        asyncio.create_task(update_user_activity(db, user_id))

    # Return user object constructed from JWT payload
    return User(
        id=user_id,
        phone_number=phone_number,
        role=role,
        name=name,
        is_verified=is_verified
    )

async def update_user_activity(db: AsyncSession, user_id: int):
    """Update user's last activity timestamp asynchronously"""
    try:
        from sqlalchemy import update
        await db.execute(
            update(User).where(User.id == user_id).values(last_activity=datetime.utcnow())
        )
        await db.commit()
    except Exception as e:
        # Log error but don't fail the request
        print(f"Failed to update user activity for user {user_id}: {e}")

async def get_user_from_refresh_token(token: str, db: AsyncSession):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        phone_number: str = payload.get("sub")
        if phone_number is None:
            raise credentials_exception
        token_type: str = payload.get("type")
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise credentials_exception

    from sqlalchemy import select
    # Check if refresh token exists in database and is not revoked
    result = await db.execute(
        select(JWTToken).where(
            JWTToken.refresh_token == token,
            JWTToken.is_revoked == False
        )
    )
    jwt_token = result.scalar_one_or_none()

    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or does not exist",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if refresh token is expired
    if datetime.utcnow() > jwt_token.refresh_token_expires_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user data from JWT payload (no additional DB query needed)
    user_id = payload.get("user_id")
    role = payload.get("role")

    # Return user object constructed from JWT payload
    return User(
        id=user_id,
        phone_number=phone_number,
        role=role
    )

