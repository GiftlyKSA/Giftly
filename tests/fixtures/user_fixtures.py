"""
User-related fixtures for the test suite.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datetime import date

import pytest_asyncio
from auth import create_tokens
from enums import UserRole
from sqlalchemy.ext.asyncio import AsyncSession

from models import CourierProfile, CustomerProfile, User, Wallet


@pytest_asyncio.fixture
async def customer(db: AsyncSession) -> User:
    """Create a test customer user."""
    u = User(
        phone_number="+966500000001",
        email="customer@test.com",
        name="Test Customer",
        date_of_birth=date(1990, 1, 1),
        is_verified=True,
        role=UserRole.CUSTOMER,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    db.add(Wallet(user_id=u.id, balance=50_000))  # 500 SAR
    db.add(CustomerProfile(user_id=u.id, timezone="Asia/Riyadh"))
    await db.commit()
    return u


@pytest_asyncio.fixture
async def courier(db: AsyncSession, city: City) -> User:
    """Create a test courier user."""
    u = User(
        phone_number="+966500000002",
        email="courier@test.com",
        name="Test Courier",
        date_of_birth=date(1985, 5, 15),
        is_verified=True,
        role=UserRole.COURIER,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    db.add(Wallet(user_id=u.id, balance=0))
    db.add(
        CourierProfile(
            user_id=u.id,
            national_id="1234567890",
            city_id=city.id,
            iban="SA1234567890123456789012",
            is_approved=True,
            is_available=True,
        )
    )
    await db.commit()
    return u


@pytest_asyncio.fixture
async def unapproved_courier(db: AsyncSession, city: City) -> User:
    """Create an unapproved courier user."""
    u = User(
        phone_number="+966500000003",
        email="unapproved@test.com",
        name="Unapproved Courier",
        date_of_birth=date(1990, 6, 1),
        is_verified=True,
        role=UserRole.COURIER,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    db.add(Wallet(user_id=u.id, balance=0))
    db.add(
        CourierProfile(
            user_id=u.id,
            national_id="0987654321",
            city_id=city.id,
            iban="SA9876543210123456789012",
            is_approved=False,
            is_available=False,
        )
    )
    await db.commit()
    return u


@pytest_asyncio.fixture
async def customer_headers(db: AsyncSession, customer: User):
    """Get auth headers for customer."""
    access, _ = await create_tokens(db, customer, device_id="test-device")
    return {"Authorization": f"Bearer {access}"}


@pytest_asyncio.fixture
async def courier_headers(db: AsyncSession, courier: User):
    """Get auth headers for courier."""
    access, _ = await create_tokens(db, courier, device_id="test-device")
    return {"Authorization": f"Bearer {access}"}


@pytest_asyncio.fixture
async def unapproved_courier_headers(db: AsyncSession, unapproved_courier: User):
    """Get auth headers for unapproved courier."""
    access, _ = await create_tokens(db, unapproved_courier, device_id="test-device")
    return {"Authorization": f"Bearer {access}"}
