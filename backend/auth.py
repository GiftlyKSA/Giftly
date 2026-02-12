from datetime import datetime, timedelta
from typing import Optional, Tuple
import random
import string
from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import User, RefreshToken
from config import settings
from database import get_db
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

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
        expire = datetime.utcnow() + timedelta(days=60)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    return encoded_jwt

async def create_tokens(db: AsyncSession, user: User) -> Tuple[str, str]:
    access_delta = timedelta(minutes=15)
    refresh_delta = timedelta(days=60)
    access_payload = {
        "sub": str(user.id),
        "phone_number": user.phone_number,
        "role": user.role,
        "name": user.name,
        "is_verified": user.is_verified,
        "city_id": user.city_id
    }
    access_token = create_access_token(access_payload, access_delta)
    refresh_payload = {
        "sub": str(user.id),
        "type": "refresh"
    }
    refresh_token = create_refresh_token(refresh_payload, refresh_delta)
    # Truncate refresh token to 72 bytes for bcrypt compatibility
    token_hash = pwd_context.hash(refresh_token[:72])
    refresh_db = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + refresh_delta
    )
    db.add(refresh_db)
    await db.commit()
    return access_token, refresh_token

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

async def get_user_by_phone(db: AsyncSession, phone_number: str):
    result = await db.execute(select(User).where(User.phone_number == phone_number))
    return result.scalar_one_or_none()

async def get_current_user(token: str = Depends(security)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token.credentials, settings.secret_key, algorithms=["HS256"])
        sub: str = payload.get("sub")
        if sub is None:
            raise credentials_exception
        token_type: str = payload.get("type")
        if token_type == "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not allowed for this endpoint",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = int(sub)
    except (JWTError, ValueError):
        raise credentials_exception
    phone_number = payload.get("phone_number")
    role = payload.get("role")
    name = payload.get("name")
    is_verified = payload.get("is_verified", False)
    city_id = payload.get("city_id")
    return User(
        id=user_id,
        phone_number=phone_number,
        role=role,
        name=name,
        is_verified=is_verified,
        city_id=city_id
    )

async def validate_refresh_token(db: AsyncSession, token: str) -> Tuple[int, RefreshToken]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        sub: str = payload.get("sub")
        if sub is None or payload.get("type") != "refresh":
            raise JWTError
        user_id = int(sub)
    except JWTError:
        raise credentials_exception
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.utcnow()
        )
    )
    tokens = result.scalars().all()
    for rt in tokens:
        # Verify against truncated token (first 72 bytes)
        if pwd_context.verify(token[:72], rt.token_hash):
            return user_id, rt
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token invalid, revoked or expired",
        headers={"WWW-Authenticate": "Bearer"},
    )