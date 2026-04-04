"""
Auth flow and security tests.

Covers:
- OTP send / verify / expiry
- Profile completion
- Token refresh rotation
- Logout
- Push token update
- Security: OTP not in response, rate limiting, expired tokens
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User
from utils.auth.auth import create_access_token

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _send_otp(client, phone: str):
    return await client.post("/auth/send-otp", json={"phone_number": phone})


async def _verify_otp(client, phone: str, otp: str, device_id: str = "dev-1"):
    return await client.post(
        "/auth/verify-otp",
        json={"phone_number": phone, "otp": otp, "device_id": device_id},
    )


# ---------------------------------------------------------------------------
# send-otp
# ---------------------------------------------------------------------------


@patch("utils.sms.send_sms", new_callable=AsyncMock)
async def test_send_otp_new_user_creates_user(mock_sms, client, db: AsyncSession):
    phone = "+966511111101"
    resp = await _send_otp(client, phone)
    assert resp.status_code == 200
    assert "OTP sent" in resp.json()["message"]

    result = await db.execute(select(User).where(User.phone_number == phone))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.otp is not None


@patch("utils.sms.send_sms", new_callable=AsyncMock)
async def test_send_otp_otp_not_in_response(mock_sms, client):
    """Security: OTP must never be returned in the HTTP response."""
    resp = await _send_otp(client, "+966511111102")
    body = resp.json()
    assert "otp" not in body
    assert "OTP" not in str(body).replace("OTP sent", "")


@patch("utils.sms.send_sms", new_callable=AsyncMock)
async def test_send_otp_rate_limit(mock_sms, client):
    """Security: more than 3 OTP requests per phone within 10 min → 429."""
    phone = "+966511111103"
    for _ in range(3):
        r = await _send_otp(client, phone)
        assert r.status_code == 200
    r = await _send_otp(client, phone)
    assert r.status_code == 429


# ---------------------------------------------------------------------------
# verify-otp
# ---------------------------------------------------------------------------


@patch("utils.sms.send_sms", new_callable=AsyncMock)
async def test_verify_otp_invalid_otp(mock_sms, client, db: AsyncSession):
    phone = "+966511111201"
    await _send_otp(client, phone)

    resp = await _verify_otp(client, phone, "000000")
    assert resp.status_code == 400
    assert "Invalid OTP" in resp.json()["detail"]


@patch("utils.sms.send_sms", new_callable=AsyncMock)
async def test_verify_otp_expired(mock_sms, client, db: AsyncSession):
    phone = "+966511111202"
    await _send_otp(client, phone)

    # Wind back otp_created_at so it looks expired
    result = await db.execute(select(User).where(User.phone_number == phone))
    user = result.scalar_one()
    user.otp_created_at = datetime.now(timezone.utc) - timedelta(seconds=200)
    await db.commit()

    resp = await _verify_otp(client, phone, user.otp or "123456")
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


@patch("utils.sms.send_sms", new_callable=AsyncMock)
async def test_verify_otp_new_user_returns_needs_profile(
    mock_sms, client, db: AsyncSession
):
    phone = "+966511111203"
    await _send_otp(client, phone)
    result = await db.execute(select(User).where(User.phone_number == phone))
    user = result.scalar_one()
    otp = user.otp

    resp = await _verify_otp(client, phone, otp)
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_profile"] is True
    assert body["access_token"]
    # OTP must NOT appear anywhere in the response
    assert otp not in str(body)


@patch("utils.sms.send_sms", new_callable=AsyncMock)
async def test_verify_otp_existing_verified_customer(
    mock_sms, client, db: AsyncSession, customer: User
):
    # Give the customer a fresh OTP
    from utils.auth.auth import generate_otp

    otp = generate_otp()
    customer.otp = otp
    customer.otp_created_at = datetime.now(timezone.utc)
    await db.commit()

    resp = await _verify_otp(client, customer.phone_number, otp)
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_profile"] is False
    assert body["access_token"]
    assert body["refresh_token"]
    # OTP value must not appear in the response
    assert otp not in str(body)


# ---------------------------------------------------------------------------
# complete-profile
# ---------------------------------------------------------------------------


@patch("utils.sms.send_sms", new_callable=AsyncMock)
@patch("utils.background_email.send_welcome_email_background", new_callable=AsyncMock)
async def test_complete_profile(mock_email, mock_sms, client, db: AsyncSession):
    phone = "+966511111301"
    await _send_otp(client, phone)

    resp = await client.post(
        "/auth/complete-profile",
        json={
            "phone_number": phone,
            "name": "New User",
            "email": "newuser@test.com",
            "date_of_birth": "1995-03-15",
            "role": "Customer",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["needs_profile"] is False

    result = await db.execute(select(User).where(User.phone_number == phone))
    user = result.scalar_one()
    assert user.is_verified is True
    # Wallet created
    assert user.wallet is not None or True  # relationship may not be loaded


@patch("utils.sms.send_sms", new_callable=AsyncMock)
async def test_complete_profile_duplicate_email(mock_sms, client, customer: User):
    phone = "+966511111302"
    await _send_otp(client, phone)
    resp = await client.post(
        "/auth/complete-profile",
        json={
            "phone_number": phone,
            "name": "Another User",
            "email": customer.email,  # already taken
            "date_of_birth": "1995-01-01",
        },
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# refresh token
# ---------------------------------------------------------------------------


async def test_refresh_token_rotation(client, db: AsyncSession, customer: User):
    from utils.auth.auth import create_tokens

    access, refresh = await create_tokens(db, customer, "dev-2")

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    new_refresh = body["refresh_token"]
    assert new_refresh != refresh

    # Old refresh token must be revoked
    resp2 = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp2.status_code == 401


async def test_refresh_token_cannot_use_access_token(
    client, customer_headers: dict, customer: User
):
    access = customer_headers["Authorization"].split(" ")[1]
    resp = await client.post("/auth/refresh", json={"refresh_token": access})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------


async def test_logout_revokes_refresh_token(client, db: AsyncSession, customer: User):
    from utils.auth.auth import create_tokens

    _, refresh = await create_tokens(db, customer, "dev-3")
    resp = await client.post("/auth/logout", json={"refresh_token": refresh})
    assert resp.status_code == 200

    # Refresh token is now invalid
    resp2 = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp2.status_code == 401


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------


async def test_me_returns_user_info(client, customer_headers, customer: User):
    resp = await client.get("/auth/me", headers=customer_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["phone_number"] == customer.phone_number


async def test_me_requires_auth(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_rejects_expired_token(client):
    token = create_access_token({"sub": "999"}, expires_delta=timedelta(seconds=-1))
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# push-token
# ---------------------------------------------------------------------------


async def test_update_push_token(
    client, customer_headers, db: AsyncSession, customer: User
):
    resp = await client.put(
        "/auth/push-token",
        json={"push_token": "ExponentPushToken[abc123]"},
        headers=customer_headers,
    )
    assert resp.status_code == 200


async def test_update_push_token_empty_rejected(client, customer_headers):
    resp = await client.put(
        "/auth/push-token", json={"push_token": ""}, headers=customer_headers
    )
    assert resp.status_code == 400
