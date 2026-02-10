from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select
from database import get_db
from models import User
from auth import get_password_hash, verify_password
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

router = APIRouter()

security = HTTPBasic()

async def authenticate_admin(credentials: HTTPBasicCredentials = Depends(security), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(
            User.admin_username == credentials.username,
            User.is_admin == True
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    if not verify_password(credentials.password, user.admin_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user

@router.post("/create-admin")
async def create_admin_user(username: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)):
    # Check if admin already exists
    result = await db.execute(select(User).where(User.admin_username == username))
    existing_admin = result.scalar_one_or_none()
    if existing_admin:
        raise HTTPException(status_code=400, detail="Admin user already exists")

    # Create admin user
    hashed_password = get_password_hash(password)
    admin_user = User(
        phone_number=f"admin_{username}",  # dummy phone number
        name=f"Admin {username}",
        is_admin=True,
        admin_username=username,
        admin_password_hash=hashed_password,
        is_verified=True
    )
    db.add(admin_user)
    await db.commit()
    await db.refresh(admin_user)
    return {"message": "Admin user created successfully"}

@router.get("/me")
async def get_admin_info(current_admin: User = Depends(authenticate_admin)):
    return {
        "id": current_admin.id,
        "username": current_admin.admin_username,
        "name": current_admin.name,
        "is_admin": current_admin.is_admin
    }
