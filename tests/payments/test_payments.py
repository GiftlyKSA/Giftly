"""
Payment flow tests.

Covers:
- Wallet payment (success, insufficient balance, double pay)
- Promo code (valid, expired, duplicate use per user, usage limit)
- Paylink callback (paid → marks invoice paid, failed → marks failed, already processed idempotency)
- Access control (wrong user cannot pay another user's invoice)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Invoice,
    InvoiceStatus,
    OrderStatus,
    Payment,
    PaymentStatus,
    Promocode,
    Wallet,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# POST /payments/pay-with-wallet/{invoice_id}
# ---------------------------------------------------------------------------


@patch("utils.websocket.websocket_events.emit_order_status_change", new_callable=AsyncMock)
@patch("utils.websocket.websocket_events.emit_chat_message", new_callable=AsyncMock)
async def test_wallet_payment_success(
    mock_chat,
    mock_status,
    client,
    customer_headers,
    invoice: Invoice,
    db: AsyncSession,
    customer,
):
    resp = await client.post(
        f"/payments/pay-with-wallet/{invoice.id}",
        headers=customer_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_id"]
    assert body["final_amount"] == invoice.full_amount

    await db.refresh(invoice)
    assert invoice.status == InvoiceStatus.PAID


@patch("utils.websocket.websocket_events.emit_order_status_change", new_callable=AsyncMock)
@patch("utils.websocket.websocket_events.emit_chat_message", new_callable=AsyncMock)
async def test_wallet_payment_with_valid_coupon(
    mock_chat,
    mock_status,
    client,
    customer_headers,
    invoice: Invoice,
    promocode: Promocode,
    db: AsyncSession,
):
    resp = await client.post(
        f"/payments/pay-with-wallet/{invoice.id}?coupon_code=SAVE10",
        headers=customer_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["discount_amount"] > 0
    assert body["final_amount"] < invoice.full_amount


async def test_wallet_payment_expired_coupon(
    client, customer_headers, invoice: Invoice, db: AsyncSession
):
    expired = Promocode(
        name="Expired",
        code="EXPIRED",
        description="",
        percentage=10,
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
        f"/payments/pay-with-wallet/{invoice.id}?coupon_code=EXPIRED",
        headers=customer_headers,
    )
    assert resp.status_code == 400


@patch("utils.websocket.websocket_events.emit_order_status_change", new_callable=AsyncMock)
@patch("utils.websocket.websocket_events.emit_chat_message", new_callable=AsyncMock)
async def test_wallet_payment_duplicate_coupon_use_rejected(
    mock_chat,
    mock_status,
    client,
    customer_headers,
    db: AsyncSession,
    customer,
    order,
    invoice: Invoice,
    promocode: Promocode,
):
    # First use (should succeed)
    resp1 = await client.post(
        f"/payments/pay-with-wallet/{invoice.id}?coupon_code=SAVE10",
        headers=customer_headers,
    )
    assert resp1.status_code == 200

    # Mark invoice as NEW again for second attempt
    invoice.status = InvoiceStatus.NEW
    order.status = OrderStatus.RECEIVED_BY_COURIER
    wallet_result = await db.execute(
        select(Wallet).where(Wallet.user_id == customer.id)
    )
    w = wallet_result.scalar_one()
    w.balance = 50_000
    await db.commit()

    # Build new invoice for same customer
    inv2 = Invoice(
        invoice_id="INV-002",
        order_id=order.id,
        created_by_user_id=customer.id,
        full_amount=10_000,
        service_fee=1_000,
        courier_fee=2_000,
        order_only_price=9_000,
        status=InvoiceStatus.NEW,
        description="Second invoice",
    )
    db.add(inv2)
    await db.commit()
    await db.refresh(inv2)

    resp2 = await client.post(
        f"/payments/pay-with-wallet/{inv2.id}?coupon_code=SAVE10",
        headers=customer_headers,
    )
    assert resp2.status_code == 400
    assert "already used" in resp2.json()["detail"].lower()


async def test_wallet_payment_insufficient_balance(
    client, customer_headers, invoice: Invoice, db: AsyncSession, customer
):
    wallet_result = await db.execute(
        select(Wallet).where(Wallet.user_id == customer.id)
    )
    w = wallet_result.scalar_one()
    w.balance = 100  # only 1 SAR
    await db.commit()

    resp = await client.post(
        f"/payments/pay-with-wallet/{invoice.id}",
        headers=customer_headers,
    )
    assert resp.status_code == 400
    assert "balance" in resp.json()["detail"].lower()


async def test_wallet_payment_already_paid_invoice(
    client, customer_headers, paid_invoice: Invoice
):
    resp = await client.post(
        f"/payments/pay-with-wallet/{paid_invoice.id}",
        headers=customer_headers,
    )
    assert resp.status_code == 400
    assert "already paid" in resp.json()["detail"].lower()


async def test_wallet_payment_wrong_user_rejected(
    client, courier_headers, invoice: Invoice
):
    """Security: a user cannot pay another user's invoice."""
    resp = await client.post(
        f"/payments/pay-with-wallet/{invoice.id}",
        headers=courier_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /payments/paylink-callback
# ---------------------------------------------------------------------------


@patch("utils.websocket.websocket_events.emit_order_status_change", new_callable=AsyncMock)
@patch("utils.websocket.websocket_events.emit_chat_message", new_callable=AsyncMock)
async def test_paylink_callback_paid_marks_invoice(
    mock_chat, mock_status, client, db: AsyncSession, invoice: Invoice, customer
):
    # Create a PENDING payment linked to the invoice
    pmt = Payment(
        invoice_id=invoice.id,
        user_id=customer.id,
        amount=invoice.full_amount,
        payment_method="CREDIT_CARD",
        status=PaymentStatus.PENDING,
        transaction_id="TXN-12345",
    )
    db.add(pmt)
    await db.commit()

    resp = await client.post(
        "/payments/paylink-callback",
        json={
            "transactionNo": "TXN-12345",
            "orderStatus": "paid",
        },
    )
    assert resp.status_code == 200

    await db.refresh(pmt)
    assert pmt.status == PaymentStatus.COMPLETED
    await db.refresh(invoice)
    assert invoice.status == InvoiceStatus.PAID


async def test_paylink_callback_failed_marks_payment_failed(
    client, db: AsyncSession, invoice: Invoice, customer
):
    pmt = Payment(
        invoice_id=invoice.id,
        user_id=customer.id,
        amount=invoice.full_amount,
        payment_method="CREDIT_CARD",
        status=PaymentStatus.PENDING,
        transaction_id="TXN-FAIL",
    )
    db.add(pmt)
    await db.commit()

    resp = await client.post(
        "/payments/paylink-callback",
        json={
            "transactionNo": "TXN-FAIL",
            "orderStatus": "failed",
        },
    )
    assert resp.status_code == 200

    await db.refresh(pmt)
    assert pmt.status == PaymentStatus.FAILED


async def test_paylink_callback_already_processed_idempotent(
    client, db: AsyncSession, invoice: Invoice, customer
):
    pmt = Payment(
        invoice_id=invoice.id,
        user_id=customer.id,
        amount=invoice.full_amount,
        payment_method="CREDIT_CARD",
        status=PaymentStatus.COMPLETED,
        transaction_id="TXN-DONE",
    )
    db.add(pmt)
    await db.commit()

    resp = await client.post(
        "/payments/paylink-callback",
        json={
            "transactionNo": "TXN-DONE",
            "orderStatus": "paid",
        },
    )
    assert resp.status_code == 200
    assert "Already processed" in resp.json()["message"]


async def test_paylink_callback_wallet_topup(client, db: AsyncSession, customer):
    """Callback for wallet top-up (no invoice_id) should credit the wallet."""
    wallet_result = await db.execute(
        select(Wallet).where(Wallet.user_id == customer.id)
    )
    w = wallet_result.scalar_one()
    before = w.balance

    pmt = Payment(
        invoice_id=None,
        user_id=customer.id,
        amount=5_000,
        payment_method="CREDIT_CARD",
        status=PaymentStatus.PENDING,
        transaction_id="TXN-TOPUP",
    )
    db.add(pmt)
    await db.commit()

    resp = await client.post(
        "/payments/paylink-callback",
        json={
            "transactionNo": "TXN-TOPUP",
            "orderStatus": "paid",
        },
    )
    assert resp.status_code == 200

    await db.refresh(w)
    assert w.balance == before + 5_000


# ---------------------------------------------------------------------------
# GET /payments/my-payments
# ---------------------------------------------------------------------------


async def test_my_payments_pagination(client, customer_headers):
    resp = await client.get(
        "/payments/my-payments?skip=0&limit=10", headers=customer_headers
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_my_payments_requires_auth(client):
    resp = await client.get("/payments/my-payments")
    assert resp.status_code == 401
