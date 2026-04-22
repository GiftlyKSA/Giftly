from utils.database.database import get_db
from utils.rate_limit import make_ip_rate_limiter
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import City
from schemas import CityResponse

router = APIRouter()

_rate_limit = make_ip_rate_limiter(max_requests=30, window_seconds=60)


@router.get("/", response_model=list[CityResponse])
async def get_active_cities(
    _: None = Depends(_rate_limit),
    db: AsyncSession = Depends(get_db),
):
    """Get all active cities. Public endpoint."""
    result = await db.execute(select(City).where(City.active == True))
    cities = result.scalars().all()
    return cities
