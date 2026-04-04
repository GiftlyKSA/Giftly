import random
import re
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from utils.database.config import settings
from utils.database.database import get_db
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import RefreshToken, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def _now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = _now() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = _now() + (
        expires_delta or timedelta(days=settings.refresh_token_expire_days)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


async def create_tokens(
    db: AsyncSession, user: User, device_id: str = None
) -> Tuple[str, str]:
    access_delta = timedelta(minutes=settings.access_token_expire_minutes)
    refresh_delta = timedelta(days=settings.refresh_token_expire_days)

    # city_id lives on CourierProfile, not User directly
    city_id = None
    if hasattr(user, "courier_profile") and user.courier_profile:
        city_id = user.courier_profile.city_id

    access_payload = {
        "sub": str(user.id),
        "phone_number": user.phone_number,
        "role": user.role,
        "name": user.name,
        "is_verified": user.is_verified,
        "city_id": city_id,
        "timezone": user.customer_profile.timezone if user.customer_profile else None,
    }
    access_token = create_access_token(access_payload, access_delta)

    # Embed a unique jti so token refresh is O(1) — direct lookup instead of scanning all user tokens
    jti_value = str(uuid.uuid4())
    refresh_payload = {"sub": str(user.id), "type": "refresh", "jti": jti_value}
    refresh_token = create_refresh_token(refresh_payload, refresh_delta)

    # Truncate to 72 bytes before hashing (bcrypt ignores bytes beyond 72)
    token_hash = pwd_context.hash(refresh_token[:72])
    refresh_db = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        jti=jti_value,
        device_id=device_id,
        expires_at=_now() + refresh_delta,
    )
    db.add(refresh_db)
    await db.commit()
    return access_token, refresh_token


def generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


async def get_user_by_phone(db: AsyncSession, phone_number: str) -> Optional[User]:
    clean_phone = re.sub(r"^(\+966|0)+", "", phone_number)
    result = await db.execute(select(User).where(User.phone_number == clean_phone))
    return result.scalar_one_or_none()


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(security)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token.credentials, settings.secret_key, algorithms=["HS256"]
        )
        sub: str = payload.get("sub")
        if sub is None:
            raise credentials_exception
        if payload.get("type") == "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not allowed for this endpoint",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = int(sub)
    except (JWTError, ValueError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def validate_refresh_token(
    db: AsyncSession, token: str
) -> Tuple[int, RefreshToken]:
    """O(1) refresh-token validation using jti direct lookup."""
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
        jti: str = payload.get("jti")
        if not jti:
            raise credentials_exception
    except (JWTError, ValueError):
        raise credentials_exception

    # --- O(1) path: look up by jti directly ---
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > _now(),
        )
    )
    rt = result.scalar_one_or_none()
    if rt and pwd_context.verify(token[:72], rt.token_hash):
        return user_id, rt
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token invalid, revoked or expired",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_customer(
    db: AsyncSession = Depends(get_db), token: str = Depends(security)
) -> User:
    user = await get_current_user(db, token)
    if user.role != "Customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available for customers",
        )
    return user


async def get_current_courier(
    db: AsyncSession = Depends(get_db), token: str = Depends(security)
) -> User:
    user = await get_current_user(db, token)
    if user.role != "Courier":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available for couriers",
        )
    return user
