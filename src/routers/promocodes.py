from datetime import datetime, timezone
from typing import List

from utils.database.database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Promocode
from schemas import ApplyPromocodeRequest

router = APIRouter()


@router.post("/apply", response_model=dict)
async def apply_promocode(
    request: ApplyPromocodeRequest, db: AsyncSession = Depends(get_db)
):
    """
    Calculate discount for a promocode. Public endpoint for customers and couriers.
    """
    result = await db.execute(
        select(Promocode).where(
            Promocode.code == request.code,
            Promocode.active == True,
            Promocode.valid_until > datetime.now(timezone.utc),
        )
    )
    promocode = result.scalar_one_or_none()

    if not promocode:
        raise HTTPException(status_code=404, detail="Invalid or expired promocode")

    # Check minimum order value
    if request.order_total < promocode.minimum_order_value:
        raise HTTPException(
            status_code=400,
            detail=f"Order total must be at least {promocode.minimum_order_value} to use this promocode",
        )

    # Check usage limit
    if promocode.usage_limit > 0 and promocode.usage_count >= promocode.usage_limit:
        raise HTTPException(status_code=400, detail="Promocode usage limit exceeded")

    # Calculate discount
    discount_amount = int(request.order_total * promocode.percentage / 100)

    # Apply max value limit
    if promocode.max_value > 0 and discount_amount > promocode.max_value:
        discount_amount = promocode.max_value

    return {
        "promocode_id": promocode.id,
        "code": promocode.code,
        "name": promocode.name,
        "percentage": promocode.percentage,
        "max_value": promocode.max_value,
        "discount_amount": discount_amount,
        "final_amount": request.order_total - discount_amount,
    }


@router.get("/active/list", response_model=List[dict])
async def get_active_promocodes(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all active promocodes. Public endpoint for customers and couriers.
    """
    result = await db.execute(
        select(Promocode)
        .where(
            Promocode.active == True, Promocode.valid_until > datetime.now(timezone.utc)
        )
        .offset(skip)
        .limit(limit)
    )
    promocodes = result.scalars().all()

    # Return simplified promocode info (without sensitive data like usage counts)
    result = []
    for promo in promocodes:
        result.append(
            {
                "id": promo.id,
                "name": promo.name,
                "code": promo.code,
                "description": promo.description,
                "percentage": promo.percentage,
                "max_value": promo.max_value,
                "minimum_order_value": promo.minimum_order_value,
                "applicable_to": promo.applicable_to,
                "valid_until": promo.valid_until,
            }
        )

    return result
