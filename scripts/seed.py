"""
One-shot seed script for local development.

Populates the database with a minimum set of usable data:
  • 2 cities (Riyadh, Jeddah)
  • 1 admin (username: admin, password: admin)
  • 2 couriers (one per city, both approved + available)
  • 3 customers
  • Each user (customer + courier) gets a wallet with a non-zero balance
  • Each customer gets 3 orders, each with its own invoice

Usage:
    uv run --directory src python -m scripts.seed
or simply:
    uv run python scripts/seed.py

Idempotent — re-running skips records that already exist (matched by phone/username).
"""

import asyncio
import os
import sys
from datetime import date, datetime, timedelta, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Make `src/` importable when run from anywhere in the repo.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))

from utils.database.config import settings  # noqa: E402
from models import (  # noqa: E402
    Admin,
    City,
    CourierProfile,
    CustomerProfile,
    Invoice,
    Order,
    User,
    Wallet,
    enums,
)


CITIES = [
    {"name": "Riyadh", "icon": "riyadh.png"},
    {"name": "Jeddah", "icon": "jeddah.png"},
]

CUSTOMERS = [
    {"phone_number": "+966500000101", "email": "alice@example.com", "name": "Alice"},
    {"phone_number": "+966500000102", "email": "bashar@example.com", "name": "Bashar"},
    {"phone_number": "+966500000103", "email": "chadi@example.com", "name": "Chadi"},
]

COURIERS = [
    {
        "phone_number": "+966500000201",
        "email": "khaled@example.com",
        "name": "Khaled",
        "national_id": "1100000001",
        "iban": "SA0000000000000000000001",
        "city_index": 0,  # Riyadh
    },
    {
        "phone_number": "+966500000202",
        "email": "mona@example.com",
        "name": "Mona",
        "national_id": "1100000002",
        "iban": "SA0000000000000000000002",
        "city_index": 1,  # Jeddah
    },
]


async def _get_or_create_city(db: AsyncSession, payload: dict) -> City:
    existing = (await db.execute(select(City).where(City.name == payload["name"]))).scalar_one_or_none()
    if existing:
        return existing
    city = City(name=payload["name"], icon=payload["icon"], active=True)
    db.add(city)
    await db.flush()
    return city


async def _get_or_create_admin(db: AsyncSession) -> Admin:
    existing = (await db.execute(select(Admin).where(Admin.username == "admin"))).scalar_one_or_none()
    if existing:
        return existing
    pw_hash = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode("utf-8")
    admin = Admin(
        username="admin",
        password_hash=pw_hash,
        name="Root Admin",
        email="admin@example.com",
        is_active=True,
    )
    db.add(admin)
    await db.flush()
    return admin


async def _get_or_create_customer(db: AsyncSession, payload: dict, balance: int) -> User:
    existing = (
        await db.execute(select(User).where(User.phone_number == payload["phone_number"]))
    ).scalar_one_or_none()
    if existing:
        return existing
    user = User(
        phone_number=payload["phone_number"],
        email=payload["email"],
        name=payload["name"],
        date_of_birth=date(1990, 1, 1),
        is_verified=True,
        role=enums.UserRole.CUSTOMER,
    )
    db.add(user)
    await db.flush()
    db.add(Wallet(user_id=user.id, balance=balance))
    db.add(CustomerProfile(user_id=user.id, timezone="Asia/Riyadh"))
    await db.flush()
    return user


async def _get_or_create_courier(
    db: AsyncSession, payload: dict, city: City, balance: int
) -> User:
    existing = (
        await db.execute(select(User).where(User.phone_number == payload["phone_number"]))
    ).scalar_one_or_none()
    if existing:
        return existing
    user = User(
        phone_number=payload["phone_number"],
        email=payload["email"],
        name=payload["name"],
        date_of_birth=date(1988, 6, 15),
        is_verified=True,
        role=enums.UserRole.COURIER,
    )
    db.add(user)
    await db.flush()
    db.add(Wallet(user_id=user.id, balance=balance))
    db.add(
        CourierProfile(
            user_id=user.id,
            national_id=payload["national_id"],
            city_id=city.id,
            iban=payload["iban"],
            is_approved=True,
            is_available=True,
        )
    )
    await db.flush()
    return user


async def _seed_orders_for_customer(
    db: AsyncSession, customer: User, city: City, courier: User, start_index: int
) -> None:
    """Create 3 orders + matching invoices for a customer if they don't already exist."""
    for i in range(3):
        order_code = f"ORDR-{customer.id:03d}-{i + 1:02d}"
        existing = (
            await db.execute(select(Order).where(Order.order_id == order_code))
        ).scalar_one_or_none()
        if existing:
            continue

        order = Order(
            order_id=order_code,
            created_by_user_id=customer.id,
            assigned_to_user_id=courier.id,
            description=f"Sample order #{i + 1} for {customer.name}",
            city_id=city.id,
            delivery_date=datetime.now(timezone.utc) + timedelta(days=i + 1),
            status=enums.OrderStatus.NEW,
            customer_confirmed=False,
        )
        db.add(order)
        await db.flush()

        # Amounts in halalas (1 SAR = 100). Sample values: 90 SAR gift, 10 SAR fee, 20 SAR delivery.
        order_only_price = 9_000
        service_fee = 1_000
        courier_fee = 2_000
        full_amount = order_only_price + service_fee + courier_fee

        db.add(
            Invoice(
                invoice_id=f"INV-{customer.id:03d}-{i + 1:02d}",
                order_id=order.id,
                created_by_user_id=customer.id,
                full_amount=full_amount,
                service_fee=service_fee,
                courier_fee=courier_fee,
                order_only_price=order_only_price,
                status=enums.InvoiceStatus.NEW,
                description=f"Invoice for {order_code}",
            )
        )
    await db.flush()


async def main() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with sessionmaker() as db:
        cities = [await _get_or_create_city(db, c) for c in CITIES]
        admin = await _get_or_create_admin(db)

        couriers = [
            await _get_or_create_courier(db, payload, cities[payload["city_index"]], balance=0)
            for payload in COURIERS
        ]

        customers = []
        for idx, payload in enumerate(CUSTOMERS):
            # Different starting balances so wallet behavior is visible: 100 / 250 / 500 SAR
            balance = (idx + 1) * 10_000 + 90_000  # 100_000, 110_000, 120_000 halalas
            customer = await _get_or_create_customer(db, payload, balance=balance)
            customers.append(customer)

        # Distribute orders: customer 0 → courier 0, customer 1 → courier 1, customer 2 → courier 0
        for idx, customer in enumerate(customers):
            assigned_courier = couriers[idx % len(couriers)]
            assigned_city = cities[idx % len(cities)]
            await _seed_orders_for_customer(db, customer, assigned_city, assigned_courier, idx)

        await db.commit()

        print(f"Seed complete:")
        print(f"  cities    = {len(cities)} ({', '.join(c.name for c in cities)})")
        print(f"  admin     = {admin.username} (password: admin)")
        print(f"  couriers  = {len(couriers)}")
        print(f"  customers = {len(customers)}")
        print(f"  orders    = {len(customers) * 3} (3 per customer, each with an invoice)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
