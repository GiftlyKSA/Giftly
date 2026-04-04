from datetime import datetime, timedelta, timezone

from auth import verify_password
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Admin,
    Conversation,
    CourierProfile,
    CourierReview,
    Invoice,
    Message,
    Order,
    Payment,
    Promocode,
    Wallet,
)

router = APIRouter()
security = HTTPBasic()


# ---------------------------------------------------------------------------
# Admin auth dependency (reused by all admin endpoints + wallets charge)
# ---------------------------------------------------------------------------


async def authenticate_admin(
    credentials: HTTPBasicCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Admin:
    result = await db.execute(
        select(Admin).where(
            Admin.username == credentials.username, Admin.is_active == True
        )
    )
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(credentials.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return admin


# ---------------------------------------------------------------------------
# Admin info
# ---------------------------------------------------------------------------


@router.get("/me")
async def get_admin_info(current_admin: Admin = Depends(authenticate_admin)):
    return {
        "id": current_admin.id,
        "username": current_admin.username,
        "name": current_admin.name,
        "email": current_admin.email,
    }


# ---------------------------------------------------------------------------
# Courier approval
# ---------------------------------------------------------------------------


@router.post("/couriers/{user_id}/approve")
async def approve_courier(
    user_id: int,
    current_admin: Admin = Depends(authenticate_admin),
    db: AsyncSession = Depends(get_db),
):
    """Approve a courier so they can receive orders and join WebSocket city rooms."""
    result = await db.execute(
        select(CourierProfile).where(CourierProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Courier profile not found")

    profile.is_approved = True
    await db.commit()
    return {"message": "Courier approved", "user_id": user_id}


@router.post("/couriers/{user_id}/reject")
async def reject_courier(
    user_id: int,
    current_admin: Admin = Depends(authenticate_admin),
    db: AsyncSession = Depends(get_db),
):
    """Revoke approval for a courier."""
    result = await db.execute(
        select(CourierProfile).where(CourierProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Courier profile not found")

    profile.is_approved = False
    await db.commit()
    return {"message": "Courier rejected", "user_id": user_id}


# ---------------------------------------------------------------------------
# Admin wallet charge (replaces the insecure user-accessible charge endpoint)
# ---------------------------------------------------------------------------


@router.post("/wallets/{user_id}/charge")
async def admin_charge_wallet(
    user_id: int,
    data: dict,
    current_admin: Admin = Depends(authenticate_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add funds to any user's wallet. Admin-only."""
    amount = data.get("amount")
    if not isinstance(amount, int) or amount <= 0:
        raise HTTPException(
            status_code=400, detail="amount must be a positive integer (halaym)"
        )

    result = await db.execute(select(Wallet).where(Wallet.user_id == user_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    wallet.balance += amount
    wallet.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(wallet)

    return {
        "message": f"Charged {amount} halaym to user {user_id}",
        "new_balance": wallet.balance,
    }


# ---------------------------------------------------------------------------
# Soft-delete cleanup (hard-delete records older than retention_days)
# ---------------------------------------------------------------------------

_SOFT_DELETE_MODELS = [
    ("orders", Order),
    ("invoices", Invoice),
    ("payments", Payment),
    ("conversations", Conversation),
    ("messages", Message),
    ("courier_reviews", CourierReview),
    ("promocodes", Promocode),
]


@router.post("/cleanup/soft-deleted")
async def cleanup_soft_deleted(
    retention_days: int = 90,
    current_admin: Admin = Depends(authenticate_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Hard-delete soft-deleted records older than `retention_days` days.
    Returns count of deleted rows per model.
    """
    if retention_days < 1:
        raise HTTPException(status_code=400, detail="retention_days must be >= 1")

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted: dict[str, int] = {}

    for label, Model in _SOFT_DELETE_MODELS:
        result = await db.execute(
            select(Model).where(
                Model.deleted_at.isnot(None),
                Model.deleted_at < cutoff,
            )
        )
        records = result.scalars().all()
        for record in records:
            await db.delete(record)
        deleted[label] = len(records)

    await db.commit()
    return {"deleted": deleted, "cutoff_date": cutoff.isoformat()}
