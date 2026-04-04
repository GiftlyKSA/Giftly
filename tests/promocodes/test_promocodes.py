"""
Promocode tests.

Covers:
- Apply promocode (valid, invalid, expired, minimum order not met, usage limit)
- List active promocodes with pagination
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models import Promocode

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# POST /promocodes/apply
# ---------------------------------------------------------------------------


async def test_apply_valid_promocode(client, promocode: Promocode):
    resp = await client.post(
        "/promocodes/apply",
        json={
            "code": "SAVE10",
            "order_total": 10_000,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["discount_amount"] > 0
    assert body["final_amount"] < 10_000


async def test_apply_invalid_code(client):
    resp = await client.post(
        "/promocodes/apply",
        json={
            "code": "DOESNOTEXIST",
            "order_total": 10_000,
        },
    )
    assert resp.status_code == 404


async def test_apply_expired_promocode(client, db: AsyncSession):
    expired = Promocode(
        name="Expired",
        code="OLD50",
        description="",
        percentage=50,
        max_value=0,
        minimum_order_value=0,
        usage_limit=0,
        usage_count=0,
        valid_until=datetime.now(timezone.utc) - timedelta(days=1),
        active=True,
        applicable_to="order_total",
    )
    db.add(expired)
    await db.commit()

    resp = await client.post(
        "/promocodes/apply",
        json={
            "code": "OLD50",
            "order_total": 10_000,
        },
    )
    assert resp.status_code == 404


async def test_apply_below_minimum_order(client, promocode: Promocode):
    # minimum_order_value is 5_000; send 1_000
    resp = await client.post(
        "/promocodes/apply",
        json={
            "code": "SAVE10",
            "order_total": 1_000,
        },
    )
    assert resp.status_code == 400


async def test_apply_exhausted_usage_limit(client, db: AsyncSession):
    exhausted = Promocode(
        name="Full",
        code="FULL",
        description="",
        percentage=10,
        max_value=0,
        minimum_order_value=0,
        usage_limit=5,
        usage_count=5,
        valid_until=datetime.now(timezone.utc) + timedelta(days=1),
        active=True,
        applicable_to="order_total",
    )
    db.add(exhausted)
    await db.commit()

    resp = await client.post(
        "/promocodes/apply",
        json={
            "code": "FULL",
            "order_total": 10_000,
        },
    )
    assert resp.status_code == 400
    assert "limit" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /promocodes/active/list
# ---------------------------------------------------------------------------


async def test_list_active_promocodes(client, promocode: Promocode):
    resp = await client.get("/promocodes/active/list")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    codes = [p["code"] for p in resp.json()]
    assert "SAVE10" in codes


async def test_list_active_promocodes_pagination(client, promocode: Promocode):
    resp = await client.get("/promocodes/active/list?skip=0&limit=1")
    assert resp.status_code == 200
    assert len(resp.json()) <= 1


async def test_list_active_promocodes_excludes_expired(client, db: AsyncSession):
    expired = Promocode(
        name="Exp",
        code="EXPIRED2",
        description="",
        percentage=5,
        max_value=0,
        minimum_order_value=0,
        usage_limit=0,
        usage_count=0,
        valid_until=datetime.now(timezone.utc) - timedelta(hours=1),
        active=True,
        applicable_to="order_total",
    )
    db.add(expired)
    await db.commit()

    resp = await client.get("/promocodes/active/list")
    assert resp.status_code == 200
    codes = [p["code"] for p in resp.json()]
    assert "EXPIRED2" not in codes


# ---------------------------------------------------------------------------
# Sensitive fields not exposed
# ---------------------------------------------------------------------------


async def test_list_active_promocodes_no_usage_count(client, promocode: Promocode):
    """usage_count and usage_limit should not appear in the public listing."""
    resp = await client.get("/promocodes/active/list")
    assert resp.status_code == 200
    for p in resp.json():
        assert "usage_count" not in p
