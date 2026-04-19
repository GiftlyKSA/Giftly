"""
Shared fixtures for the test suite.

Database: async SQLite (aiosqlite) in-memory — no real PostgreSQL needed.
HTTP client: httpx AsyncClient.
External services (SMS, Paylink, S3) are mocked.
"""

import os
import sys

# Add the src directory to the Python path so tests can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from datetime import date, datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# ── must set env vars BEFORE importing app modules ──────────────────────────
os.environ.setdefault("secret_key", "TestSecretKey123!@#$%^&*()_+-=[]{}|;:',.<>?")
os.environ.setdefault("database_url", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("access_token_expire_minutes", "30")
os.environ.setdefault("refresh_token_expire_days", "7")
os.environ.setdefault("aws_access_key_id", "test")
os.environ.setdefault("aws_secret_access_key", "test")
os.environ.setdefault("aws_s3_bucket_name", "test-bucket")
os.environ.setdefault("aws_region", "us-east-1")
os.environ.setdefault("sms_provider_enabled", "false")
os.environ.setdefault("paylink_api_key", "")
os.environ.setdefault("paylink_test_mode", "true")
os.environ.setdefault(
    "paylink_callback_url", "http://localhost/payments/paylink-callback"
)
os.environ.setdefault("paylink_return_url", "http://localhost/return")
os.environ.setdefault("redis_url", "redis://localhost:6379")
os.environ.setdefault("debug", "true")

from utils.auth.auth import create_tokens
from utils.database.database import Base, get_db

from models import (
    City,
    Conversation,
    CourierProfile,
    CustomerProfile,
    Invoice,
    Order,
    Promocode,
    User,
    Wallet,
)
from models import enums

# ---------------------------------------------------------------------------
# Async test engine (SQLite in-memory)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    """Async session that rolls back after each test."""
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# FastAPI app wired to the test DB
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app(engine):
    """Return FastAPI app with get_db overridden to use in-memory SQLite."""
    try:
        from main import app as _app
    except (AttributeError, ImportError):
        from fastapi import FastAPI

        _app = FastAPI(title="Giftly API")

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_db_override():
        async with factory() as session:
            yield session

    from utils.database.database import get_db
    from unittest.mock import patch

    _app.dependency_overrides[get_db] = _get_db_override

    with (
        patch("utils.database.database.AsyncSessionLocal", factory),
        patch("utils.websocket.websocket_events.AsyncSessionLocal", factory),
        patch("middleware.activity.AsyncSessionLocal", factory),
        patch("main.AsyncSessionLocal", factory),
    ):
        yield _app

    _app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Seed data helpers
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def city(db: AsyncSession) -> City:
    c = City(name="Riyadh", icon="riyadh.png", active=True)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def customer(db: AsyncSession) -> User:
    u = User(
        phone_number="500000001",
        email="customer@test.com",
        name="Test Customer",
        date_of_birth=date(1990, 1, 1),
        is_verified=True,
        role=enums.UserRole.CUSTOMER,
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
    u = User(
        phone_number="500000002",
        email="courier@test.com",
        name="Test Courier",
        date_of_birth=date(1985, 5, 15),
        is_verified=True,
        role=enums.UserRole.COURIER,
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
    u = User(
        phone_number="500000003",
        email="unapproved@test.com",
        name="Unapproved Courier",
        date_of_birth=date(1990, 6, 1),
        is_verified=True,
        role=enums.UserRole.COURIER,
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


# ---------------------------------------------------------------------------
# Auth token helpers
# ---------------------------------------------------------------------------


async def make_tokens(db: AsyncSession, user: User):
    """Generate access + refresh tokens for a user."""
    return await create_tokens(db, user, device_id="test-device")


@pytest_asyncio.fixture
async def customer_headers(db: AsyncSession, customer: User):
    access, _ = await make_tokens(db, customer)
    return {"Authorization": f"Bearer {access}"}


@pytest_asyncio.fixture
async def courier_headers(db: AsyncSession, courier: User):
    access, _ = await make_tokens(db, courier)
    return {"Authorization": f"Bearer {access}"}


@pytest_asyncio.fixture
async def unapproved_courier_headers(db: AsyncSession, unapproved_courier: User):
    access, _ = await make_tokens(db, unapproved_courier)
    return {"Authorization": f"Bearer {access}"}


# ---------------------------------------------------------------------------
# Common domain objects
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def order(db: AsyncSession, customer: User, city: City) -> Order:
    o = Order(
        order_id="ORDR-100001",
        created_by_user_id=customer.id,
        description="Test order",
        city_id=city.id,
        delivery_date=datetime(2026, 12, 31),
        status=enums.OrderStatus.NEW,
        customer_confirmed=False,
    )
    db.add(o)
    await db.commit()
    await db.refresh(o)
    # create conversation
    db.add(
        Conversation(
            customer_id=customer.id,
            courier_id=None,
            order_id=o.id,
            status=enums.ConversationStatus.ACTIVE,
        )
    )
    await db.commit()
    return o


@pytest_asyncio.fixture
async def accepted_order(db: AsyncSession, order: Order, courier: User) -> Order:
    """Order already accepted by a courier."""
    order.assigned_to_user_id = courier.id
    order.status = enums.OrderStatus.RECEIVED_BY_COURIER
    await db.commit()
    await db.refresh(order)
    return order


@pytest_asyncio.fixture
async def invoice(db: AsyncSession, order: Order, customer: User) -> Invoice:
    inv = Invoice(
        invoice_id="INV-001",
        order_id=order.id,
        created_by_user_id=customer.id,
        full_amount=10_000,  # 100 SAR
        service_fee=1_000,  # 10 SAR
        courier_fee=2_000,  # 20 SAR
        order_only_price=9_000,
        status=enums.InvoiceStatus.NEW,
        description="Test invoice",
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv


@pytest_asyncio.fixture
async def paid_invoice(db: AsyncSession, order: Order, invoice: Invoice) -> Invoice:
    invoice.status = enums.InvoiceStatus.PAID
    order.status = enums.OrderStatus.PAID
    await db.commit()
    return invoice


@pytest_asyncio.fixture
async def promocode(db: AsyncSession) -> Promocode:
    p = Promocode(
        name="10% Off",
        code="SAVE10",
        description="10% discount",
        percentage=10,
        max_value=2_000,
        minimum_order_value=5_000,
        usage_limit=100,
        usage_count=0,
        valid_until=datetime.now(timezone.utc) + timedelta(days=30),
        active=True,
        applicable_to="order_total",
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p
