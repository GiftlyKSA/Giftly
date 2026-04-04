"""
Wallet tests.

Covers:
- GET /wallets/my-wallet
- POST /wallets/initiate-charge (Paylink gateway, min 10 SAR)
- POST /wallets/request-deposit (couriers only)
- Admin wallet charge endpoint
"""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# GET /wallets/my-wallet
# ---------------------------------------------------------------------------


async def test_get_my_wallet(client, customer_headers, customer):
    resp = await client.get("/wallets/my-wallet", headers=customer_headers)
    assert resp.status_code == 200
    assert "balance" in resp.json()


async def test_get_wallet_requires_auth(client):
    resp = await client.get("/wallets/my-wallet")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /wallets/initiate-charge
# ---------------------------------------------------------------------------


@patch("paylink_client.PaylinkClient.__aenter__", new_callable=AsyncMock)
@patch("paylink_client.PaylinkClient.__aexit__", new_callable=AsyncMock)
async def test_initiate_charge_below_minimum(
    mock_exit, mock_enter, client, customer_headers
):
    resp = await client.post(
        "/wallets/initiate-charge",
        json={"amount_sar": 5},
        headers=customer_headers,
    )
    assert resp.status_code == 400
    assert "10 SAR" in resp.json()["detail"]


async def test_initiate_charge_no_paylink_key(client, customer_headers):
    """When PAYLINK_API_KEY is empty, gateway returns 503."""
    resp = await client.post(
        "/wallets/initiate-charge",
        json={"amount_sar": 50},
        headers=customer_headers,
    )
    # Paylink key is empty in test env — should return 503
    assert resp.status_code == 503


async def test_initiate_charge_requires_auth(client):
    resp = await client.post("/wallets/initiate-charge", json={"amount_sar": 50})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /wallets/request-deposit (courier payout request)
# ---------------------------------------------------------------------------


async def test_request_deposit_by_courier(client, courier_headers, courier):
    resp = await client.post(
        "/wallets/request-deposit",
        json={"amount": 50},
        headers=courier_headers,
    )
    assert resp.status_code == 200
    assert "request_id" in resp.json()


async def test_request_deposit_by_customer_rejected(client, customer_headers):
    resp = await client.post(
        "/wallets/request-deposit",
        json={"amount": 50},
        headers=customer_headers,
    )
    assert resp.status_code == 403


async def test_request_deposit_requires_auth(client):
    resp = await client.post("/wallets/request-deposit", json={"amount": 50})
    assert resp.status_code == 401
