from utils.auth.auth import get_current_user
from utils.database.database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import CourierProfile, User
from models.enums import UserRole

router = APIRouter()


@router.put("/availability")
async def toggle_availability(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle courier availability on/off. Couriers only."""
    if current_user.role != UserRole.COURIER:
        raise HTTPException(
            status_code=403, detail="Only couriers can toggle availability"
        )

    result = await db.execute(
        select(CourierProfile).where(CourierProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Courier profile not found")

    if not profile.is_approved:
        raise HTTPException(status_code=403, detail="Your account is not yet approved")

    profile.is_available = not profile.is_available
    await db.commit()
    return {"is_available": profile.is_available}


@router.get("/available/{city_id}")
async def get_available_couriers(
    city_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List approved and available couriers in a city."""
    result = await db.execute(
        select(CourierProfile)
        .options(selectinload(CourierProfile.user))
        .where(
            CourierProfile.city_id == city_id,
            CourierProfile.is_approved == True,
            CourierProfile.is_available == True,
        )
        .offset(skip)
        .limit(limit)
    )
    profiles = result.scalars().all()
    return [
        {
            "user_id": p.user_id,
            "name": p.user.name if p.user else None,
            "vehicle": p.vehicle,
            "rate": p.get_average_rate(),
        }
        for p in profiles
    ]
