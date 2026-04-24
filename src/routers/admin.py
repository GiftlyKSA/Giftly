import logging
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field
from utils.auth.auth import verify_password
from utils.database.config import settings
from utils.database.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Admin,
    AuditLog,
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


async def _audit(
    db: AsyncSession,
    admin_id: int,
    action: str,
    target_type: str = None,
    target_id: str = None,
    detail: str = None,
    ip_address: str = None,
) -> None:
    db.add(AuditLog(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        detail=detail,
        ip_address=ip_address,
    ))


class AdminChargeWalletRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in halalas to add to wallet")


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
    await _audit(db, current_admin.id, "courier.approve", "courier", user_id)
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
    await _audit(db, current_admin.id, "courier.reject", "courier", user_id)
    await db.commit()
    return {"message": "Courier rejected", "user_id": user_id}


# ---------------------------------------------------------------------------
# Admin wallet charge (replaces the insecure user-accessible charge endpoint)
# ---------------------------------------------------------------------------


@router.post("/wallets/{user_id}/charge")
async def admin_charge_wallet(
    user_id: int,
    data: AdminChargeWalletRequest,
    current_admin: Admin = Depends(authenticate_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add funds to any user's wallet. Admin-only."""
    amount = data.amount
    if amount > settings.admin_wallet_charge_max_halalas:
        raise HTTPException(status_code=400, detail=f"Amount exceeds maximum allowed ({settings.admin_wallet_charge_max_halalas:,} halalas)")

    result = await db.execute(select(Wallet).where(Wallet.user_id == user_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    balance_before = wallet.balance
    wallet.balance += amount
    wallet.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(wallet)

    logging.info(
        "Admin wallet charge: admin=%s user=%s amount=%d balance_before=%d balance_after=%d",
        current_admin.id, user_id, amount, balance_before, wallet.balance,
    )
    await _audit(
        db, current_admin.id, "wallet.charge", "wallet", user_id,
        detail=f"amount={amount} balance_before={balance_before} balance_after={wallet.balance}",
    )
    await db.commit()

    return {
        "message": f"Successfully charged {amount / 100:.2f} SAR to wallet for user {user_id}",
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
    dry_run: bool = False,
    current_admin: Admin = Depends(authenticate_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Hard-delete soft-deleted records older than `retention_days` days.
    Pass `dry_run=true` to preview counts without deleting anything.
    """
    if retention_days < 1:
        raise HTTPException(status_code=400, detail="retention_days must be >= 1")

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    counts: dict[str, int] = {}

    for label, Model in _SOFT_DELETE_MODELS:
        if dry_run:
            from sqlalchemy import func as _func
            count_result = await db.execute(
                select(_func.count()).select_from(Model).where(
                    Model.deleted_at.isnot(None),
                    Model.deleted_at < cutoff,
                )
            )
            counts[label] = count_result.scalar() or 0
        else:
            result = await db.execute(
                delete(Model).where(
                    Model.deleted_at.isnot(None),
                    Model.deleted_at < cutoff,
                )
            )
            counts[label] = result.rowcount

    if not dry_run:
        await db.commit()
        await _audit(db, current_admin.id, "cleanup.soft_deleted", detail=f"retention_days={retention_days} cutoff={cutoff.isoformat()}")
        await db.commit()

    return {"dry_run": dry_run, "counts": counts, "cutoff_date": cutoff.isoformat()}
