import re
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from database import get_db
from models import User, City, Wallet
from schemas import SendOTP, OTPVerify, Token, UpdateUserProfile, RefreshTokenRequest
from auth import authenticate_user, create_access_token, create_refresh_token, create_tokens, generate_otp, get_user_by_phone, get_current_user, validate_refresh_token
from config import settings

router = APIRouter()

@router.post("/send-otp", response_model=dict)
async def send_otp(otp_request: SendOTP, db: AsyncSession = Depends(get_db)):
    phone_number = otp_request.phone_number
    user = await get_user_by_phone(db, phone_number)

    otp = generate_otp()
    print(f"OTP for {phone_number}: {otp}")  # Log the OTP

    if user:
        # Invalidate previous OTP
        user.otp = None
        await db.commit()
        # Set new OTP with timestamp
        user.otp = otp
        user.otp_created_at = datetime.utcnow()
        await db.commit()
    else:
        # Create temp user with OTP
        user = User(phone_number=phone_number, otp=otp)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return {"message": "OTP sent successfully", "otp": otp}

@router.post("/verify-otp", response_model=Token)
async def verify_otp(otp_data: OTPVerify, db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timedelta

    user = await get_user_by_phone(db, otp_data.phone_number)
    if not user:
        print(f"Error: User not found for phone {otp_data.phone_number}")
        raise HTTPException(status_code=400, detail="User not found")

    if not user.otp:
        print(f"Error: No OTP found for user {otp_data.phone_number}")
        raise HTTPException(status_code=400, detail="No OTP found")

    # Check if OTP is expired (90 seconds)
    if user.otp_created_at and datetime.utcnow() - user.otp_created_at > timedelta(seconds=90):
        print(f"Error: OTP expired for user {otp_data.phone_number}. Expected {user.otp}, got {otp_data.otp}")
        raise HTTPException(status_code=400, detail=f"OTP expired. Expected {user.otp}, got {otp_data.otp}")

    if user.otp != otp_data.otp:
        print(f"Error: Invalid OTP for user {otp_data.phone_number}. Expected {user.otp}, got {otp_data.otp}")
        raise HTTPException(status_code=400, detail=f"Invalid OTP. Expected {user.otp}, got {otp_data.otp}")

    user.otp = None  # Clear OTP

    # Check if user is a courier
    if user.role == 'Courier':
        if user.is_verified:
            # Verified courier, login
            access_token, refresh_token = await create_tokens(db, user)
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "needs_profile": False
            }
        else:
            # Unverified courier, show error
            raise HTTPException(status_code=400, detail="حسابك لم يتم التحقق منه بعد")
    else:
        # Customer or new user
        if user.is_verified:
            # Verified customer, login
            access_token, refresh_token = await create_tokens(db, user)
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "needs_profile": False
            }
        else:
            # Unverified customer/new user, needs to complete profile
            temp_token = create_access_token(
                data={"sub": user.phone_number, "temp": True},
                expires_delta=timedelta(minutes=30)
            )
            return {
                "access_token": temp_token,
                "refresh_token": "",
                "token_type": "bearer",
                "needs_profile": True
            }

@router.get("/me", response_model=dict)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "phone_number": current_user.phone_number,
        "email": current_user.email,
        "name": current_user.name,
        "date_of_birth": current_user.date_of_birth.isoformat() if current_user.date_of_birth else None,
        "national_id": current_user.national_id,
        "passport_id": current_user.passport_id,
        "is_verified": current_user.is_verified,
        "role": current_user.role
    }

@router.put("/me", response_model=dict)
async def update_current_user(user_update: UpdateUserProfile, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    errors = {}

    # Validate name
    if user_update.name is None or user_update.name.strip() == "":
        errors["name"] = "'D'3E E7DH("
    elif len(user_update.name.strip()) < 2:
        errors["name"] = "'D'3E J,( #F JCHF 2 #-1A 9DI 'D#BD"
    elif not re.match(r'^[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFFa-zA-Z0-9\s]+$', user_update.name.strip()):
        errors["name"] = "'D'3E J,( #F J-*HJ 9DI #-1A AB7"

    # Validate email
    if user_update.email is None or user_update.email.strip() == "":
        errors["email"] = "'D(1J/ 'D%DC*1HFJ E7DH("
    elif not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', user_update.email.strip()):
        errors["email"] = "5J:) 'D(1J/ 'D%DC*1HFJ :J1 5-J-)"
    else:
        # Check email uniqueness
        result = await db.execute(select(User).where(User.email == user_update.email.strip(), User.id != current_user.id))
        existing_email_user = result.scalar_one_or_none()
        if existing_email_user:
            errors["email"] = "'D(1J/ 'D%DC*1HFJ E3*./E ('DA9D"

    # Validate date_of_birth
    if user_update.date_of_birth is None:
        errors["date_of_birth"] = "*'1J. 'DEJD'/ E7DH("
    else:
        today = date.today()
        age = today.year - user_update.date_of_birth.year - ((today.month, today.day) < (user_update.date_of_birth.month, user_update.date_of_birth.day))
        if age < 16:
            errors["date_of_birth"] = "J,( #F JCHF 9E1C 16 3F) 9DI 'D#BD"
        elif user_update.date_of_birth > today:
            errors["date_of_birth"] = "*'1J. 'DEJD'/ D' JECF #F JCHF AJ 'DE3*B(D"

    if errors:
        raise HTTPException(status_code=400, detail=errors)

    # Update user fields
    current_user.name = user_update.name.strip()
    current_user.email = user_update.email.strip()
    current_user.date_of_birth = user_update.date_of_birth

    await db.commit()
    await db.refresh(current_user)

    return {
        "id": current_user.id,
        "phone_number": current_user.phone_number,
        "email": current_user.email,
        "name": current_user.name,
        "date_of_birth": current_user.date_of_birth.isoformat() if current_user.date_of_birth else None,
        "is_verified": current_user.is_verified
    }

@router.post("/refresh", response_model=Token)
async def refresh_access_token(refresh_request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    user_id, old_rt = await validate_refresh_token(db, refresh_request.refresh_token)
    old_rt.revoked = True
    await db.commit()
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    access_token, refresh_token = await create_tokens(db, user)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/complete-profile", response_model=Token)
async def complete_profile(profile_data: dict, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Complete profile for new users after OTP verification"""
    # Extract data from request
    phone_number = profile_data.get("phone_number")
    name = profile_data.get("name")
    email = profile_data.get("email")
    date_of_birth_str = profile_data.get("date_of_birth")
    role = profile_data.get("role", "Customer")

    if not all([phone_number, name, email, date_of_birth_str]):
        raise HTTPException(status_code=400, detail="Name, email, and date of birth are required")

    from datetime import datetime
    try:
        date_of_birth = datetime.fromisoformat(date_of_birth_str).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    user = await get_user_by_phone(db, phone_number)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    # Check if user already has complete profile
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Profile already completed")

    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == email, User.id != user.id))
    existing_email_user = result.scalar_one_or_none()
    if existing_email_user:
        raise HTTPException(status_code=400, detail="Email is already registered")

    # Update user profile
    user.name = name
    user.email = email
    user.date_of_birth = date_of_birth
    user.is_verified = True
    user.role = role

    await db.commit()
    await db.refresh(user)

    # Create wallet with balance 0 for the new user
    wallet = Wallet(user_id=user.id, balance=0)
    db.add(wallet)
    await db.commit()

    # Create and store permanent tokens
    access_token, refresh_token = await create_tokens(db, user)

    # Send welcome email in background
    from utils.background_email import send_welcome_email_background
    background_tasks.add_task(send_welcome_email_background, user.id, db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "needs_profile": False
    }

@router.post("/logout")
async def logout(refresh_request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Logout by revoking the provided refresh token and cleaning up WebSocket connections"""
    user_id, rt = await validate_refresh_token(db, refresh_request.refresh_token)
    rt.revoked = True
    await db.commit()

    # Clean up WebSocket connections for this user
    from websocket_manager import manager
    manager.disconnect(user_id)

    return {"message": "Successfully logged out"}
