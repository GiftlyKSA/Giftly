"""
Important Events (calendar) tests.

Covers:
- CRUD operations
- Pagination
- Access control (can only see own events)
"""

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models import ImportantEvent

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# POST /events/
# ---------------------------------------------------------------------------


async def test_create_event(client, customer_headers):
    resp = await client.post(
        "/events/",
        json={
            "title": "Birthday",
            "event_date": "2026-07-04",
            "recurring": True,
        },
        headers=customer_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Birthday"


async def test_create_event_requires_auth(client):
    resp = await client.post(
        "/events/",
        json={
            "title": "Birthday",
            "event_date": "2026-07-04",
            "recurring": False,
        },
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /events/
# ---------------------------------------------------------------------------


async def test_list_events_pagination(
    client, customer_headers, db: AsyncSession, customer
):
    for i in range(5):
        db.add(
            ImportantEvent(
                user_id=customer.id,
                title=f"Event {i}",
                event_date=date(2026, 1, i + 1),
                recurring=False,
            )
        )
    await db.commit()

    resp = await client.get("/events/?skip=0&limit=3", headers=customer_headers)
    assert resp.status_code == 200
    assert len(resp.json()) <= 3


async def test_list_events_courier_forbidden(
    client, courier_headers, db: AsyncSession, customer
):
    """Couriers are not allowed to access the events endpoint."""
    db.add(
        ImportantEvent(
            user_id=customer.id,
            title="Customer Event",
            event_date=date(2026, 6, 1),
            recurring=False,
        )
    )
    await db.commit()

    resp = await client.get("/events/", headers=courier_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /events/{event_id}
# ---------------------------------------------------------------------------


async def test_get_event_by_owner(client, customer_headers, db: AsyncSession, customer):
    event = ImportantEvent(
        user_id=customer.id,
        title="My Event",
        event_date=date(2026, 9, 9),
        recurring=False,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    resp = await client.get(f"/events/{event.id}", headers=customer_headers)
    assert resp.status_code == 200


async def test_get_event_not_own_returns_404(
    client, courier_headers, db: AsyncSession, customer
):
    event = ImportantEvent(
        user_id=customer.id,
        title="Private",
        event_date=date(2026, 10, 1),
        recurring=False,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    resp = await client.get(f"/events/{event.id}", headers=courier_headers)
    assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# PUT /events/{event_id}
# ---------------------------------------------------------------------------


async def test_update_event(client, customer_headers, db: AsyncSession, customer):
    event = ImportantEvent(
        user_id=customer.id,
        title="Old Title",
        event_date=date(2026, 11, 1),
        recurring=False,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    resp = await client.put(
        f"/events/{event.id}", json={"title": "New Title"}, headers=customer_headers
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"


# ---------------------------------------------------------------------------
# DELETE /events/{event_id}
# ---------------------------------------------------------------------------


async def test_delete_event(client, customer_headers, db: AsyncSession, customer):
    event = ImportantEvent(
        user_id=customer.id,
        title="To Delete",
        event_date=date(2026, 12, 1),
        recurring=False,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    resp = await client.delete(f"/events/{event.id}", headers=customer_headers)
    assert resp.status_code == 200
