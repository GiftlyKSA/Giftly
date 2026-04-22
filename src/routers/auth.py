import re
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import CourierProfile, CustomerProfile, User, Wallet
from models.enums import UserRole
from schemas import OTPVerify, RefreshTokenRequest, SendOTP, Token, UpdateUserProfile
from utils.auth.auth import (
    create_access_token,
    create_tokens,
    generate_otp,
    get_current_user,
    get_profile_user,
    get_user_by_phone,
    validate_refresh_token,
)
from utils.database.config import settings
from utils.database.database import get_db

router = APIRouter()

# ---------------------------------------------------------------------------
# In-process rate limiting for send-otp and verify-otp (per phone number)
# For multi-server deployments replace with Redis-backed counters.
# ---------------------------------------------------------------------------
_PHONE_WINDOW = settings.rate_limit_otp_window_seconds
_PHONE_MAX = settings.rate_limit_otp_max

_phone_timestamps: dict[str, list[float]] = defaultdict(list)
_verify_timestamps: dict[str, list[float]] = defaultdict(list)


def _check_phone_rate_limit(phone: str) -> None:
    now = time.monotonic()
    # Evict old entries
    _phone_timestamps[phone] = [
        t for t in _phone_timestamps[phone] if now - t < _PHONE_WINDOW
    ]
    if len(_phone_timestamps[phone]) >= _PHONE_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP requests for this number. Try again in 10 minutes.",
        )
    _phone_timestamps[phone].append(now)


def _check_phone_verify_rate_limit(phone: str) -> None:
    now = time.monotonic()
    # Evict old entries
    _verify_timestamps[phone] = [
        t for t in _verify_timestamps[phone] if now - t < _PHONE_WINDOW
    ]
    if len(_verify_timestamps[phone]) >= _PHONE_MAX:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTP verification attempts for this number. Try again in 10 minutes.",
        )
    _verify_timestamps[phone].append(now)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/send-otp", response_model=dict)
async def send_otp(
    otp_request: SendOTP, db: AsyncSession = Depends(get_db)
):
    # Normalize phone to prevent rate-limit bypass via format variations (+966, 0-prefix, etc.)
    phone_number = re.sub(r"^(\+966|0)+", "", otp_request.phone_number)

    # Per-phone rate limit (3 requests / 10 min)
    _check_phone_rate_limit(phone_number)

    user = await get_user_by_phone(db, phone_number)

    otp = generate_otp()

    if user:
        user.otp = otp
        user.otp_created_at = datetime.now(timezone.utc)
        await db.commit()
    else:
        user = User(
            phone_number=phone_number,
            otp=otp,
            otp_created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Deliver OTP via SMS via background task queue — never expose it in the API response
    from tasks.email_tasks import send_sms_task
    await send_sms_task.kiq(phone_number, otp)

    return {"message": "OTP sent successfully"}


@router.post("/verify-otp", response_model=Token)
async def verify_otp(otp_data: OTPVerify, db: AsyncSession = Depends(get_db)):
    # Normalize phone before rate limit to prevent bypass via format variations
    normalized_phone = re.sub(r"^(\+966|0)+", "", otp_data.phone_number)
    _check_phone_verify_rate_limit(normalized_phone)
    user = await get_user_by_phone(db, otp_data.phone_number)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    if not user.otp:
        raise HTTPException(status_code=400, detail="No OTP found for this number")

    # Check expiry (90 seconds)
    if user.otp_created_at:
        created = user.otp_created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created > timedelta(
            seconds=settings.otp_expiry_seconds
        ):
            # Invalidate expired OTP
            user.otp = None
            await db.commit()
            raise HTTPException(
                status_code=400, detail="OTP has expired. Please request a new one."
            )

    if user.otp != otp_data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    user.otp = None  # Consume OTP

    if user.role == UserRole.COURIER:
        if user.is_verified:
            access_token, refresh_token = await create_tokens(
                db, user, otp_data.device_id
            )
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "needs_profile": False,
                "user": {
                    "id": user.id,
                    "phone_number": user.phone_number,
                    "email": user.email,
                    "name": user.name,
                    "date_of_birth": user.date_of_birth.isoformat()
                    if user.date_of_birth
                    else None,
                    "is_verified": user.is_verified,
                    "role": user.role,
                },
                "profile": {
                    "national_id": user.courier_profile.national_id
                    if user.courier_profile
                    else None,
                    "passport_id": user.courier_profile.passport_id
                    if user.courier_profile
                    else None,
                    "city_id": user.courier_profile.city_id
                    if user.courier_profile
                    else None,
                    "iban": user.courier_profile.iban if user.courier_profile else None,
                    "vehicle": user.courier_profile.vehicle
                    if user.courier_profile
                    else None,
                    "license": user.courier_profile.license
                    if user.courier_profile
                    else None,
                    "rate": user.courier_profile.get_average_rate()
                    if user.courier_profile
                    else 0,
                    "is_approved": user.courier_profile.is_approved
                    if user.courier_profile
                    else False,
                    "is_available": user.courier_profile.is_available
                    if user.courier_profile
                    else False,
                },
            }
        else:
            raise HTTPException(status_code=400, detail="حسابك لم يتم التحقق منه بعد")
    elif user.role == UserRole.CUSTOMER:
        if user.is_verified:
            access_token, refresh_token = await create_tokens(
                db, user, otp_data.device_id
            )
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "needs_profile": False,
                "user": {
                    "id": user.id,
                    "phone_number": user.phone_number,
                    "email": user.email,
                    "name": user.name,
                    "date_of_birth": user.date_of_birth.isoformat()
                    if user.date_of_birth
                    else None,
                    "is_verified": user.is_verified,
                    "role": user.role,
                },
                "profile": {
                    "timezone": user.customer_profile.timezone
                    if user.customer_profile
                    else None,
                },
            }
        else:
            temp_token = create_access_token(
                data={"sub": str(user.id), "temp": True},
                expires_delta=timedelta(minutes=30),
            )
            await db.commit()
            return {
                "access_token": temp_token,
                "refresh_token": "",
                "token_type": "bearer",
                "needs_profile": True,
            }


@router.get("/me", response_model=dict)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "phone_number": current_user.phone_number,
        "email": current_user.email,
        "name": current_user.name,
        "date_of_birth": current_user.date_of_birth.isoformat()
        if current_user.date_of_birth
        else None,
        "is_verified": current_user.is_verified,
        "role": current_user.role,
        "timezone": current_user.customer_profile.timezone
        if current_user.customer_profile
        else None,
    }


@router.put("/me", response_model=dict)
async def update_current_user(
    user_update: UpdateUserProfile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    errors = {}

    if user_update.name is None or user_update.name.strip() == "":
        errors["name"] = "الاسم مطلوب"
    elif len(user_update.name.strip()) < 2:
        errors["name"] = "الاسم يجب أن يكون 2 أحرف على الأقل"
    elif not re.match(
        r"^[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFFa-zA-Z0-9\s]+$",
        user_update.name.strip(),
    ):
        errors["name"] = "الاسم يجب أن يحتوي على أحرف فقط"

    if user_update.email is None or user_update.email.strip() == "":
        errors["email"] = "البريد الإلكتروني مطلوب"
    elif not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", user_update.email.strip()):
        errors["email"] = "صيغة البريد الإلكتروني غير صحيحة"
    else:
        result = await db.execute(
            select(User).where(
                User.email == user_update.email.strip(), User.id != current_user.id
            )
        )
        if result.scalar_one_or_none():
            errors["email"] = "البريد الإلكتروني مستخدم بالفعل"

    if user_update.date_of_birth is None:
        errors["date_of_birth"] = "تاريخ الميلاد مطلوب"
    else:
        today = date.today()
        age = (
            today.year
            - user_update.date_of_birth.year
            - (
                (today.month, today.day)
                < (user_update.date_of_birth.month, user_update.date_of_birth.day)
            )
        )
        if age < 16:
            errors["date_of_birth"] = "يجب أن يكون عمرك 16 سنة على الأقل"
        elif user_update.date_of_birth > today:
            errors["date_of_birth"] = "تاريخ الميلاد لا يمكن أن يكون في المستقبل"

    if errors:
        raise HTTPException(status_code=400, detail=errors)

    current_user.name = user_update.name.strip()
    current_user.email = user_update.email.strip()
    current_user.date_of_birth = user_update.date_of_birth

    if user_update.timezone is not None:
        if current_user.customer_profile:
            current_user.customer_profile.timezone = user_update.timezone
        else:
            db.add(
                CustomerProfile(user_id=current_user.id, timezone=user_update.timezone)
            )

    await db.commit()
    await db.refresh(current_user)

    return {
        "id": current_user.id,
        "phone_number": current_user.phone_number,
        "email": current_user.email,
        "name": current_user.name,
        "date_of_birth": current_user.date_of_birth.isoformat()
        if current_user.date_of_birth
        else None,
        "is_verified": current_user.is_verified,
        "timezone": current_user.customer_profile.timezone
        if current_user.customer_profile
        else None,
    }


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    user_id, old_rt = await validate_refresh_token(db, refresh_request.refresh_token)
    old_rt.revoked = True
    await db.commit()

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    access_token, refresh_token = await create_tokens(db, user, old_rt.device_id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/complete-profile", response_model=Token)
async def complete_profile(
    profile_data: dict,
    current_user: User = Depends(get_profile_user),
    db: AsyncSession = Depends(get_db),
):
    phone_number = current_user.phone_number  # always use authenticated user's phone
    name = profile_data.get("name")
    email = profile_data.get("email")
    date_of_birth_str = profile_data.get("date_of_birth")
    timezone_val = profile_data.get("timezone")
    role_str = profile_data.get("role", "Customer")
    try:
        role = UserRole(role_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")

    if not all([phone_number, name, email, date_of_birth_str]):
        raise HTTPException(
            status_code=400, detail="Name, email, and date of birth are required"
        )

    try:
        date_of_birth = datetime.fromisoformat(date_of_birth_str).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    user = current_user
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Profile already completed")

    result = await db.execute(
        select(User).where(User.email == email, User.id != user.id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email is already registered")

    user.name = name
    user.email = email
    user.date_of_birth = date_of_birth
    user.is_verified = True
    user.role = role

    if role == UserRole.CUSTOMER:
        db.add(CustomerProfile(user_id=user.id, timezone=timezone_val))
    # Courier profile is created through a separate onboarding flow
    await db.commit()
    await db.refresh(user)

    db.add(Wallet(user_id=user.id, balance=0))
    await db.commit()

    access_token, refresh_token = await create_tokens(db, user)

    try:
        from tasks.email_tasks import send_welcome_email_task

        await send_welcome_email_task.kiq(user.id)
    except Exception:
        pass

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "needs_profile": False,
    }


@router.put("/timezone", response_model=dict)
async def update_timezone(
    timezone_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    new_timezone = timezone_data.get("timezone")
    if not new_timezone:
        raise HTTPException(status_code=400, detail="Timezone is required")

    current_tz = (
        current_user.customer_profile.timezone
        if current_user.customer_profile
        else None
    )
    if current_tz == new_timezone:
        return {
            "message": "Timezone is already set to this value",
            "timezone": current_tz,
        }

    if current_user.customer_profile:
        current_user.customer_profile.timezone = new_timezone
    else:
        db.add(CustomerProfile(user_id=current_user.id, timezone=new_timezone))

    await db.commit()
    await db.refresh(current_user)
    return {
        "message": "Timezone updated successfully",
        "timezone": current_user.customer_profile.timezone
        if current_user.customer_profile
        else None,
    }


@router.put("/push-token", response_model=dict)
async def update_push_token(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store FCM / APNs push token for the current user's device."""
    push_token = data.get("push_token", "").strip()
    if not push_token:
        raise HTTPException(status_code=400, detail="push_token is required")
    if len(push_token) > 300:
        raise HTTPException(status_code=400, detail="Invalid push token")

    if current_user.role == UserRole.CUSTOMER:
        if current_user.customer_profile:
            current_user.customer_profile.push_token = push_token
        else:
            db.add(CustomerProfile(user_id=current_user.id, push_token=push_token))
    else:
        result = await db.execute(
            select(CourierProfile).where(CourierProfile.user_id == current_user.id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Courier profile not found")
        profile.push_token = push_token

    await db.commit()
    return {"message": "Push token updated"}


@router.post("/logout")
async def logout(
    refresh_request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    user_id, rt = await validate_refresh_token(db, refresh_request.refresh_token)
    rt.revoked = True
    await db.commit()

    from utils.websocket.websocket_manager import manager

    manager.disconnect(user_id)

    return {"message": "Successfully logged out"}


# ---------------------------------------------------------------------------
# DEV ONLY — returns the stored OTP so tests can run without an SMS provider
# Route registered only when DEBUG=true so it cannot exist in production
# ---------------------------------------------------------------------------

if settings.debug:

    @router.get("/dev/otp")
    async def dev_get_otp(phone_number: str, db: AsyncSession = Depends(get_db)):
        user = await get_user_by_phone(db, phone_number)
        if not user or not user.otp:
            raise HTTPException(status_code=404, detail="No pending OTP for this number")

        return {"phone_number": phone_number, "otp": user.otp}
