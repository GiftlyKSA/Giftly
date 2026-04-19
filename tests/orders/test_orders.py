"""
Order flow tests.

Covers:
- Create, list (pagination), get by ID
- Cancel (status checks, paid invoice guard)
- Accept order (approval/availability guards)
- Confirm delivery (customer only)
- Complete order (customer_confirmed guard, paid invoice guard)
- Status update
- Security: access control, cross-user access denied
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models import Invoice, InvoiceStatus, Order, OrderStatus

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# GET /orders/
# ---------------------------------------------------------------------------


async def test_list_orders_requires_auth(client):
    resp = await client.get("/orders/")
    assert resp.status_code == 401


async def test_list_orders_pagination(client, customer_headers, order: Order):
    resp = await client.get("/orders/?skip=0&limit=10", headers=customer_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_list_orders_only_own(client, courier_headers, order: Order):
    """A courier must not see a customer's order via GET /orders/."""
    resp = await client.get("/orders/", headers=courier_headers)
    assert resp.status_code == 200
    order_ids = [o["id"] for o in resp.json()]
    assert order.id not in order_ids


# ---------------------------------------------------------------------------
# GET /orders/{order_id}
# ---------------------------------------------------------------------------


async def test_get_order_by_creator(client, customer_headers, order: Order):
    resp = await client.get(f"/orders/{order.order_id}", headers=customer_headers)
    assert resp.status_code == 200
    assert resp.json()["order_id"] == order.order_id


async def test_get_order_forbidden_for_other_user(
    client, courier_headers, order: Order
):
    """A courier who hasn't accepted the order cannot view it via GET /{id}."""
    resp = await client.get(f"/orders/{order.order_id}", headers=courier_headers)
    assert resp.status_code == 403


async def test_get_order_not_found(client, customer_headers):
    resp = await client.get("/orders/ORDR-999999", headers=customer_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /orders/{order_id}/cancel
# ---------------------------------------------------------------------------


async def test_cancel_order_by_customer(client, customer_headers, order: Order):
    resp = await client.put(
        f"/orders/{order.order_id}/cancel",
        json={"reason": "Changed my mind"},
        headers=customer_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


async def test_cancel_order_forbidden_for_courier(
    client, courier_headers, order: Order
):
    resp = await client.put(
        f"/orders/{order.order_id}/cancel",
        json={"reason": "Not my order"},
        headers=courier_headers,
    )
    assert resp.status_code == 403


async def test_cancel_already_cancelled_order(
    client, customer_headers, order: Order, db: AsyncSession
):
    order.status = OrderStatus.CANCELLED
    await db.commit()
    resp = await client.put(
        f"/orders/{order.order_id}/cancel",
        json={"reason": "Already cancelled"},
        headers=customer_headers,
    )
    assert resp.status_code == 400


async def test_cancel_order_with_paid_invoice_rejected(
    client, customer_headers, order: Order, invoice: Invoice, db: AsyncSession
):
    invoice.status = InvoiceStatus.PAID
    order.status = OrderStatus.PAID
    await db.commit()
    resp = await client.put(
        f"/orders/{order.order_id}/cancel",
        json={"reason": "Want refund"},
        headers=customer_headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PUT /orders/{order_id}/accept
# ---------------------------------------------------------------------------


@patch("utils.websocket.websocket_events.emit_chat_message", new_callable=AsyncMock)
@patch("utils.websocket.websocket_events.emit_order_status_change", new_callable=AsyncMock)
@patch("websocket_manager.manager.send_to_user", new_callable=AsyncMock)
async def test_accept_order_by_approved_courier(
    mock_ws, mock_status, mock_chat, client, courier_headers, order: Order
):
    resp = await client.put(f"/orders/{order.order_id}/accept", headers=courier_headers)
    assert resp.status_code == 200
    assert resp.json()["assigned_to_user_id"] is not None


async def test_accept_order_by_unapproved_courier(
    client, unapproved_courier_headers, order: Order
):
    resp = await client.put(
        f"/orders/{order.order_id}/accept", headers=unapproved_courier_headers
    )
    assert resp.status_code == 403


async def test_accept_order_not_new_fails(
    client, courier_headers, order: Order, db: AsyncSession
):
    order.status = OrderStatus.CANCELLED
    await db.commit()
    resp = await client.put(f"/orders/{order.order_id}/accept", headers=courier_headers)
    assert resp.status_code == 400


async def test_accept_order_requires_courier_role(
    client, customer_headers, order: Order
):
    resp = await client.put(
        f"/orders/{order.order_id}/accept", headers=customer_headers
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /orders/{order_id}/confirm-delivery
# ---------------------------------------------------------------------------


async def test_confirm_delivery_by_customer(
    client, customer_headers, accepted_order: Order, db: AsyncSession
):
    resp = await client.post(
        f"/orders/{accepted_order.order_id}/confirm-delivery",
        headers=customer_headers,
    )
    assert resp.status_code == 200
    await db.refresh(accepted_order)
    assert accepted_order.customer_confirmed is True


async def test_confirm_delivery_by_courier_rejected(
    client, courier_headers, accepted_order: Order
):
    resp = await client.post(
        f"/orders/{accepted_order.order_id}/confirm-delivery",
        headers=courier_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PUT /orders/{order_id}/complete
# ---------------------------------------------------------------------------


@patch("utils.websocket.websocket_events.emit_order_status_change", new_callable=AsyncMock)
async def test_complete_order_success(
    mock_status,
    client,
    courier_headers,
    accepted_order: Order,
    invoice: Invoice,
    db: AsyncSession,
    courier,
):
    # Mark invoice as paid, set customer_confirmed
    invoice.status = InvoiceStatus.PAID
    accepted_order.status = OrderStatus.PAID
    accepted_order.customer_confirmed = True
    await db.commit()

    resp = await client.put(
        f"/orders/{accepted_order.order_id}/complete",
        headers=courier_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "DONE"


@patch("utils.websocket.websocket_events.emit_order_status_change", new_callable=AsyncMock)
async def test_complete_order_without_customer_confirm_fails(
    mock_status,
    client,
    courier_headers,
    accepted_order: Order,
    invoice: Invoice,
    db: AsyncSession,
):
    invoice.status = InvoiceStatus.PAID
    accepted_order.status = OrderStatus.PAID
    accepted_order.customer_confirmed = False
    await db.commit()

    resp = await client.put(
        f"/orders/{accepted_order.order_id}/complete",
        headers=courier_headers,
    )
    assert resp.status_code == 400
    assert (
        "customer" in resp.json()["detail"].lower()
        or "confirm" in resp.json()["detail"].lower()
    )


@patch("utils.websocket.websocket_events.emit_order_status_change", new_callable=AsyncMock)
async def test_complete_order_without_paid_invoice_fails(
    mock_status, client, courier_headers, accepted_order: Order, db: AsyncSession
):
    accepted_order.customer_confirmed = True
    await db.commit()

    resp = await client.put(
        f"/orders/{accepted_order.order_id}/complete",
        headers=courier_headers,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
