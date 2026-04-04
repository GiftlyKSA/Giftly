from auth import get_current_customer
from utils.database.database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ImportantEvent
from schemas import (
    CreateImportantEventRequest,
    ImportantEventResponse,
    UpdateImportantEventRequest,
)

router = APIRouter()


@router.post("/", response_model=ImportantEventResponse)
async def create_important_event(
    event_data: CreateImportantEventRequest,
    current_user=Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    """Create a new important event for the current customer"""
    event = ImportantEvent(
        user_id=current_user.id,
        title=event_data.title,
        event_date=event_data.event_date,
        recurring=event_data.recurring,
    )

    db.add(event)
    await db.commit()
    await db.refresh(event)

    return event


@router.get("/", response_model=list[ImportantEventResponse])
async def get_important_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    """Get all important events for the current customer"""
    result = await db.execute(
        select(ImportantEvent)
        .where(ImportantEvent.user_id == current_user.id)
        .order_by(ImportantEvent.event_date)
        .offset(skip)
        .limit(limit)
    )
    events = result.scalars().all()
    return events


@router.get("/{event_id}", response_model=ImportantEventResponse)
async def get_important_event(
    event_id: int,
    current_user=Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific important event by ID"""
    result = await db.execute(
        select(ImportantEvent).where(
            ImportantEvent.id == event_id, ImportantEvent.user_id == current_user.id
        )
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    return event


@router.put("/{event_id}", response_model=ImportantEventResponse)
async def update_important_event(
    event_id: int,
    event_data: UpdateImportantEventRequest,
    current_user=Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    """Update an important event"""
    result = await db.execute(
        select(ImportantEvent).where(
            ImportantEvent.id == event_id, ImportantEvent.user_id == current_user.id
        )
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    # Update fields if provided
    if event_data.title is not None:
        event.title = event_data.title
    if event_data.event_date is not None:
        event.event_date = event_data.event_date
    if event_data.recurring is not None:
        event.recurring = event_data.recurring

    await db.commit()
    await db.refresh(event)

    return event


@router.delete("/{event_id}")
async def delete_important_event(
    event_id: int,
    current_user=Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    """Delete an important event"""
    result = await db.execute(
        select(ImportantEvent).where(
            ImportantEvent.id == event_id, ImportantEvent.user_id == current_user.id
        )
    )
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )

    await db.delete(event)
    await db.commit()

    return {"message": "Event deleted successfully"}
