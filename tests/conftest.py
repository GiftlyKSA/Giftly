"""
Shared fixtures for the test suite.

Database: async SQLite (aiosqlite) in-memory — no real PostgreSQL needed.
HTTP client: httpx AsyncClient.
External services (SMS, Paylink, S3) are mocked.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pytest_asyncio
from datetime import date, datetime, timezone, timedelta
from typing import AsyncGenerator

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# ── must set env vars BEFORE importing app modules ──────────────────────────
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_S3_BUCKET_NAME", "test-bucket")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("SMS_PROVIDER_ENABLED", "false")
os.environ.setdefault("PAYLINK_API_KEY", "")
os.environ.setdefault("PAYLINK_TEST_MODE", "true")
os.environ.setdefault("PAYLINK_CALLBACK_URL", "http://localhost/payments/paylink-callback")
os.environ.setdefault("PAYLINK_RETURN_URL", "http://localhost/return")

from database import Base, get_db
from models import (
    User, City, Order, OrderStatus, Invoice, InvoiceStatus,
    Conversation, Message, Wallet, Payment, PaymentMethod, PaymentStatus,
    Promocode, PromocodeUsage, CourierProfile, CustomerProfile, RefreshToken,
    ImportantEvent,
)
from enums import UserRole, ConversationStatus
from auth import get_password_hash, create_tokens

# ---------------------------------------------------------------------------
# Async test engine (SQLite in-memory)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
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
    from main import app as _app

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _get_db_override():
        async with factory() as session:
            yield session

    _app.dependency_overrides[get_db] = _get_db_override
    yield _app
    _app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
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
    db.add(CourierProfile(
        user_id=u.id,
        national_id="1234567890",
        city_id=city.id,
        iban="SA1234567890123456789012",
        is_approved=True,
        is_available=True,
    ))
    await db.commit()
    return u


@pytest_asyncio.fixture
async def unapproved_courier(db: AsyncSession, city: City) -> User:
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
    db.add(CourierProfile(
        user_id=u.id,
        national_id="0987654321",
        city_id=city.id,
        iban="SA9876543210123456789012",
        is_approved=False,
        is_available=False,
    ))
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
        status=OrderStatus.NEW,
        customer_confirmed=False,
    )
    db.add(o)
    await db.commit()
    await db.refresh(o)
    # create conversation
    db.add(Conversation(
        customer_id=customer.id,
        courier_id=None,
        order_id=o.id,
        status=ConversationStatus.ACTIVE,
    ))
    await db.commit()
    return o


@pytest_asyncio.fixture
async def accepted_order(db: AsyncSession, order: Order, courier: User) -> Order:
    """Order already accepted by a courier."""
    order.assigned_to_user_id = courier.id
    order.status = OrderStatus.RECEIVED_BY_COURIER
    await db.commit()
    await db.refresh(order)
    return order


@pytest_asyncio.fixture
async def invoice(db: AsyncSession, order: Order, customer: User) -> Invoice:
    inv = Invoice(
        invoice_id="INV-001",
        order_id=order.id,
        created_by_user_id=customer.id,
        full_amount=10_000,   # 100 SAR
        service_fee=1_000,    # 10 SAR
        courier_fee=2_000,    # 20 SAR
        order_only_price=9_000,
        status=InvoiceStatus.NEW,
        description="Test invoice",
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv


@pytest_asyncio.fixture
async def paid_invoice(db: AsyncSession, order: Order, invoice: Invoice) -> Invoice:
    invoice.status = InvoiceStatus.PAID
    order.status = OrderStatus.PAID
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
