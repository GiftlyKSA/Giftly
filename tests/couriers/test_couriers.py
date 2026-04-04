"""
Courier availability and listing tests.

Covers:
- PUT /couriers/availability (toggle, requires approved courier)
- GET /couriers/available/{city_id} (pagination)
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import CourierProfile

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# PUT /couriers/availability
# ---------------------------------------------------------------------------


async def test_toggle_availability_approved_courier(
    client, courier_headers, courier, db: AsyncSession
):
    result = await db.execute(
        select(CourierProfile).where(CourierProfile.user_id == courier.id)
    )
    profile = result.scalar_one()
    initial = profile.is_available

    resp = await client.put("/couriers/availability", headers=courier_headers)
    assert resp.status_code == 200
    assert resp.json()["is_available"] == (not initial)


async def test_toggle_availability_unapproved_courier_rejected(
    client, unapproved_courier_headers
):
    resp = await client.put(
        "/couriers/availability", headers=unapproved_courier_headers
    )
    assert resp.status_code == 403


async def test_toggle_availability_customer_rejected(client, customer_headers):
    resp = await client.put("/couriers/availability", headers=customer_headers)
    assert resp.status_code == 403


async def test_toggle_availability_requires_auth(client):
    resp = await client.put("/couriers/availability")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /couriers/available/{city_id}
# ---------------------------------------------------------------------------


async def test_list_available_couriers(client, city, courier):
    resp = await client.get(f"/couriers/available/{city.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    user_ids = [c["user_id"] for c in data]
    assert courier.id in user_ids


async def test_list_available_couriers_pagination(client, city):
    resp = await client.get(f"/couriers/available/{city.id}?skip=0&limit=5")
    assert resp.status_code == 200


async def test_list_available_couriers_empty_city(client):
    resp = await client.get("/couriers/available/99999")
    assert resp.status_code == 200
    assert resp.json() == []
