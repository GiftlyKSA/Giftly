"""
Domain object fixtures for the test suite.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
import pytest_asyncio
from datetime import date, datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    City, Order, OrderStatus, Invoice, InvoiceStatus,
    Conversation, ConversationStatus, Message, Wallet, Payment, PaymentStatus,
    Promocode, PromocodeUsage, CourierProfile, CustomerProfile, RefreshToken,
    ImportantEvent,
)
from enums import UserRole, ConversationStatus


@pytest_asyncio.fixture
async def city(db: AsyncSession) -> City:
    """Create a test city."""
    c = City(name="Riyadh", icon="riyadh.png", active=True)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


@pytest_asyncio.fixture
async def order(db: AsyncSession, customer: User, city: City) -> Order:
    """Create a test order."""
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
    """Create a test invoice."""
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
    """Create a paid invoice."""
    invoice.status = InvoiceStatus.PAID
    order.status = OrderStatus.PAID
    await db.commit()
    return invoice


@pytest_asyncio.fixture
async def promocode(db: AsyncSession) -> Promocode:
    """Create a test promocode."""
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