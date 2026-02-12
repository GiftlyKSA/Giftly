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



@router.get("/me")
async def get_admin_info(current_admin: User = Depends(authenticate_admin)):
    return {
        "id": current_admin.id,
        "username": current_admin.admin_username,
        "name": current_admin.name,
        "is_admin": current_admin.is_admin
    }
