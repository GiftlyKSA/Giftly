from utils.database.database import get_db
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import City
from schemas import CityResponse

router = APIRouter()


@router.get("/", response_model=list[CityResponse])
async def get_active_cities(db: AsyncSession = Depends(get_db)):
    """Get all active cities. Public endpoint."""
    result = await db.execute(select(City).where(City.active == True))
    cities = result.scalars().all()
    return cities
