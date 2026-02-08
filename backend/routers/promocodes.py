from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db_sync
from models import Promocode
from schemas import ApplyPromocodeRequest
from typing import List
from datetime import datetime

router = APIRouter()

@router.post("/apply", response_model=dict)
def apply_promocode(request: ApplyPromocodeRequest, db: Session = Depends(get_db_sync)):
    """
    Calculate discount for a promocode. Public endpoint for customers and couriers.
    """
    promocode = db.query(Promocode).filter(
        Promocode.code == request.code,
        Promocode.active == True,
        Promocode.valid_until > datetime.utcnow()
    ).first()

    if not promocode:
        raise HTTPException(status_code=404, detail="Invalid or expired promocode")

    # Check minimum order value
    if request.order_total < promocode.minimum_order_value:
        raise HTTPException(
            status_code=400,
            detail=f"Order total must be at least {promocode.minimum_order_value} to use this promocode"
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
        "final_amount": request.order_total - discount_amount
    }

@router.get("/active/list", response_model=List[dict])
def get_active_promocodes(db: Session = Depends(get_db_sync)):
    """
    Get all active promocodes. Public endpoint for customers and couriers.
    """
    promocodes = db.query(Promocode).filter(
        Promocode.active == True,
        Promocode.valid_until > datetime.utcnow()
    ).all()

    # Return simplified promocode info (without sensitive data like usage counts)
    result = []
    for promo in promocodes:
        result.append({
            "id": promo.id,
            "name": promo.name,
            "code": promo.code,
            "description": promo.description,
            "percentage": promo.percentage,
            "max_value": promo.max_value,
            "minimum_order_value": promo.minimum_order_value,
            "applicable_to": promo.applicable_to,
            "valid_until": promo.valid_until
        })

    return result
