# Backend — Technical Reference

FastAPI + async SQLAlchemy 2.0 on PostgreSQL.
All amounts are stored as **integers (halaym, 1/100 of a SAR)** and divided by 100 only in display strings.

---

## Table of Contents

1. [Tech Stack](#1-tech-stack)
2. [Data Models](#2-data-models)
3. [API Endpoints](#3-api-endpoints)
4. [Authentication Flow](#4-authentication-flow)
5. [WebSocket Architecture](#5-websocket-architecture)
6. [Payment Gateway (Paylink.sa)](#6-payment-gateway-paylinksa)
7. [Storage (Cloudflare R2 / S3)](#7-storage-cloudflare-r2--s3)
8. [Middleware Stack](#8-middleware-stack)
9. [Security Flows & Fixes](#9-security-flows--fixes)
10. [Performance & Indexing](#10-performance--indexing)
11. [Configuration (ENV VARS)](#11-configuration-env-vars)
12. [Testing](#12-testing)
13. [Implemented Improvements](#13-implemented-improvements)

---

## 1. Tech Stack

| Component | Library | Notes |
|-----------|---------|-------|
| Web framework | FastAPI 0.128+ | Starlette under the hood |
| ORM | SQLAlchemy 2.0 async | `asyncpg` driver for PostgreSQL |
| Validation | Pydantic v2 | Config via `pydantic-settings` |
| Auth | `python-jose` (HS256) + `passlib[bcrypt]` | JWT access + rotating refresh tokens |
| Migrations | Alembic | `alembic upgrade head` |
| Admin UI | SQLAdmin | Basic-auth protected |
| Payments | Paylink.sa REST API | Card, Apple Pay, Mada, wallet top-up |
| Storage | Cloudflare R2 / AWS S3 | boto3 |
| WebSockets | Starlette WebSocket | Room-based fan-out |
| Email | Jinja2 + boto3 SES | Background task |
| SMS | Configurable stub | Replace `utils/sms.py` |

---

## 2. Data Models

### User
Primary identity. Roles: `Customer`, `Courier`.
- `phone_number` — unique, used as login identity
- `otp`, `otp_created_at` — one-time password for phone verification
- `is_verified` — false until profile is completed
- `last_activity` — updated by `LastActivityMiddleware` (debounced 60 s)
- Related: `wallet`, `courier_profile`, `customer_profile`, `refresh_tokens`

### Admin
Separate model from `User`. Basic-auth credentials for the SQLAdmin dashboard and REST admin endpoints. Never a JWT user.

### CourierProfile
- `is_approved` — set by admin; couriers cannot accept orders or join city rooms until approved
- `is_available` — self-toggled; toggling blocked when unapproved
- `push_token` — FCM/APNs token
- `get_average_rate()` — computes mean from related `CourierReview` records

### CustomerProfile
- `timezone` — IANA timezone string (e.g. `Asia/Riyadh`)
- `push_token` — FCM/APNs token

### Order
Status flow: `NEW → RECEIVED_BY_COURIER → IN_PROGRESS → READY → OUT_FOR_DELIVERY → PAID → DONE | CANCELLED`
- `customer_confirmed` — customer must call `POST /orders/{id}/confirm-delivery` before courier can mark DONE
- `city_id` — used to broadcast to `couriers_city_{id}` WebSocket room

### Invoice
- `full_amount`, `service_fee`, `courier_fee`, `order_only_price` — all in halaym
- `discount_amount`, `promocode_id` — filled in on wallet payment with promo code
- Status: `NEW → PAID`

### Payment
- `payment_method`: `WALLET`, `CREDIT_CARD`, `APPLE_PAY`, `MADA`
- `transaction_id` — Paylink transaction number (for callback matching)
- `wallet_balance_before` — snapshot for audit trail
- `invoice_id = NULL` → wallet top-up payment (no linked invoice)

### RefreshToken
- `jti` — UUID embedded in JWT, indexed for O(1) lookup
- `token_hash` — bcrypt hash of first 72 bytes of the raw token
- `revoked`, `expires_at` — validation fields
- `device_id` — per-device token management

### Wallet
- `balance` — integer halaym
- One wallet per user (customer and courier both have wallets)

### Promocode + PromocodeUsage
- `PromocodeUsage` has `UNIQUE(user_id, promocode_id)` — prevents replay attacks
- `applicable_to`: `order_total | service_fee | delivery_fee`

### Conversation + Message
- One conversation per order
- `status`: `active | inactive | closed` (VARCHAR, no DB enum migration needed)
- Message types: `text | image | invoice`

### CourierReview
- Rating 1–5 per order; aggregated by `get_average_rate()`

### ImportantEvent
- Customer-only calendar entries; `recurring` flag for yearly events

### DepositRequest
- Courier payout request awaiting admin approval

---

## 3. API Endpoints

### Auth — `/auth`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/send-otp` | public | Send OTP via SMS (rate-limited: 3/10 min per phone) |
| POST | `/verify-otp` | public | Verify OTP → access + refresh tokens |
| POST | `/complete-profile` | temp token | Set name/email/DOB, creates wallet |
| GET | `/me` | JWT | Current user info |
| PUT | `/me` | JWT | Update profile (name, email, DOB, timezone) |
| PUT | `/timezone` | JWT | Update timezone only |
| PUT | `/push-token` | JWT | Store FCM/APNs push token |
| POST | `/refresh` | — | Rotate refresh token (old token consumed) |
| POST | `/logout` | — | Revoke refresh token |

### Orders — `/orders`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | JWT | Create order (multipart, up to 3 images, max 15 MB each) |
| GET | `/` | JWT | List own orders (paginated) |
| GET | `/{order_id}` | JWT | Get order (creator or assigned courier) |
| PUT | `/{order_id}/cancel` | JWT customer | Cancel (blocked if invoice is PAID) |
| PUT | `/{order_id}/assign` | JWT admin-level | Admin assigns courier |
| PUT | `/{order_id}/accept` | JWT courier | Accept order (must be approved + available) |
| POST | `/{order_id}/confirm-delivery` | JWT customer | Customer confirms receipt |
| PUT | `/{order_id}/complete` | JWT courier | Mark DONE (requires customer_confirmed + paid invoice) |
| PUT | `/{order_id}/status` | JWT courier | Update intermediate status |
| GET | `/courier/available` | JWT courier | New orders in courier's city (paginated) |
| GET | `/courier/active` | JWT courier | Active orders assigned to courier (paginated) |
| GET | `/courier/all` | JWT courier | All courier orders (paginated) |
| GET | `/courier/stats` | JWT courier | Active count + today's earnings |

### Payments — `/payments`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | JWT | Create payment (CREDIT_CARD/APPLE_PAY/MADA → Paylink URL returned) |
| POST | `/paylink-callback` | public | Paylink webhook: marks payment + invoice PAID, credits wallet |
| POST | `/pay-with-wallet/{invoice_id}` | JWT | Pay with wallet balance (+ optional promo code) |
| GET | `/{payment_id}` | JWT | Get own payment |
| GET | `/invoice/{invoice_id}` | JWT | Payments for an invoice (paginated) |
| GET | `/my-payments` | JWT | Caller's payment history (paginated) |

### Wallets — `/wallets`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/my-wallet` | JWT | Current wallet balance |
| POST | `/initiate-charge` | JWT | Start Paylink top-up (min 10 SAR) → payment URL |
| POST | `/request-deposit` | JWT courier | Request payout (admin approval required) |

### Couriers — `/couriers`
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| PUT | `/availability` | JWT courier | Toggle is_available (requires is_approved) |
| GET | `/available/{city_id}` | public | List approved + available couriers in city (paginated) |

### Admin — `/admin`
All endpoints require HTTP Basic auth.
| Method | Path | Description |
|--------|------|-------------|
| GET | `/me` | Admin info |
| POST | `/couriers/{user_id}/approve` | Approve courier |
| POST | `/couriers/{user_id}/reject` | Revoke courier approval |
| POST | `/wallets/{user_id}/charge` | Direct wallet credit (halaym) |
| POST | `/cleanup/soft-deleted` | Hard-delete soft-deleted records older than N days |

### Other routers
- `/cities` — list/get cities
- `/invoices` — create/get invoices (courier creates invoices for orders)
- `/chat` — conversation list, message history (paginated)
- `/promocodes` — apply code, list active codes (paginated)
- `/events` — customer calendar events CRUD (paginated)

---

## 4. Authentication Flow

### OTP Login
```
Client                         Server
  |--- POST /auth/send-otp --->|  rate-limit check (3/10 min per phone)
  |                            |  generate 6-digit OTP
  |                            |  store OTP + created_at in User
  |                            |  send OTP via SMS (utils/sms.py)
  |<-- {"message": "OTP sent"} |  OTP NEVER in response body

  |--- POST /auth/verify-otp ->|  check expiry (default 90 s, OTP_EXPIRY_SECONDS)
  |                            |  compare plain OTP
  |                            |  if new user → temp token (needs_profile=true)
  |                            |  if existing verified user → full token pair
  |<-- {access_token, refresh_token, needs_profile} |
```

### Token Structure
- **Access token** — HS256 JWT, 30 min default, contains: `sub` (user_id), `phone_number`, `role`, `name`, `is_verified`, `type: access`
- **Refresh token** — HS256 JWT, 7 days default, contains: `sub`, `jti` (UUID), `type: refresh`; stored hashed in `RefreshToken` table

### Refresh Token Rotation (O(1))
```
Client                         Server
  |--- POST /auth/refresh ----> |  decode JWT, extract jti
  |    {refresh_token}          |  SELECT RefreshToken WHERE jti=? AND revoked=false
  |                             |  bcrypt.verify(token[:72], rt.token_hash)
  |                             |  mark old token revoked
  |                             |  issue new access + refresh token pair
  |<-- {new_access, new_refresh}|
```

The `jti` (JWT ID) is a UUID embedded in the token payload and stored on the `RefreshToken` row. This gives O(1) DB lookup vs the previous O(n) full-table scan.

### Profile Completion Flow
```
POST /auth/verify-otp  →  needs_profile: true  →  temp token (30 min)
POST /auth/complete-profile  →  sets name/email/DOB, is_verified=true, creates Wallet
                              →  full token pair returned
```

---

## 5. WebSocket Architecture

Single endpoint: `GET /ws?token=<access_token>`

### Room naming
| Room | Members | Purpose |
|------|---------|---------|
| `user_{id}` | One user | Personal notifications |
| `chat_{conversation_id}` | Customer + Courier | Real-time chat |
| `couriers_city_{city_id}` | Approved + available couriers in city | New order broadcasts |

### Connection flow
1. Authenticate via JWT (same token as REST)
2. Auto-join `user_{id}` room
3. If courier + approved + available: auto-join `couriers_city_{city_id}`
4. Client sends `{"action": "join_room", "room": "chat_123"}` to join chat
5. Server echoes `{"action": "joined_room", "room": "chat_123"}`

### Client actions
- `join_room` / `leave_room` / `leave_all_rooms`
- `send_message` — persisted to DB + broadcast to room (chat rooms only)

### Emitted server events
- `order_status_change` — whenever an order status changes
- `chat_message` — new chat message
- `chat_available` — sent to customer when courier accepts their order
- `new_order` — broadcast to `couriers_city_{id}` when a new order is created

---

## 6. Payment Gateway (Paylink.sa)

### Invoice payment (card/Apple Pay/Mada)
```
POST /payments/  →  create PENDING Payment record
                 →  PaylinkClient.create_invoice(...)  →  returns payment_url
                 →  store transactionNo in Payment.transaction_id
                 →  return {payment_url} to client

POST /payments/paylink-callback  (Paylink calls this)
                 →  find Payment by transaction_id
                 →  if status == "paid": mark Payment COMPLETED
                    → sum completed payments for invoice
                    → if total >= invoice.full_amount: mark invoice + order PAID
                 →  else: mark Payment FAILED
```

### Wallet top-up
```
POST /wallets/initiate-charge  →  create PENDING Payment (invoice_id=NULL)
                               →  PaylinkClient.create_order(...)  →  payment_url
                               →  store payment.id as orderNumber in Paylink

POST /payments/paylink-callback
                               →  find Payment by transactionNo OR by id (fallback)
                               →  if paid AND invoice_id IS NULL: credit Wallet.balance
```

---

## 7. Storage (Cloudflare R2 / S3)

`storage_client.py` wraps boto3 with a `custom_endpoint_url` for R2. Images are stored as:
```
{user_id}/{username}/{image_type}/{uuid}.{ext}
```

Supported: JPEG, PNG, GIF, WebP, SVG. Max 15 MB per image, 3 images per order.

---

## 8. Middleware Stack

Execution order (outermost → innermost):

1. **`ForceHTTPSBaseURL`** — rewrites `request.scope["scheme"]` to `https` for correct SQLAdmin redirect URLs behind a reverse proxy
2. **`RequestLoggingMiddleware`** (`middleware/logging.py`) — logs one JSON line per request: `request_id`, `method`, `path`, `status_code`, `duration_ms`, `user_id` (extracted from JWT if present)
3. **`LastActivityMiddleware`** (`middleware/activity.py`) — updates `User.last_activity` on authenticated requests, debounced to once per 60 s per user using an in-process dict
4. **`admin_auth_middleware`** (`@app.middleware("http")`) — HTTP Basic auth gate for all `/admin/*` routes; blocks before routers run

---

## 9. Security Flows & Fixes

### 9.1 OTP Exposure (Fixed)
**Issue**: OTP was returned in the API response body AND exposed in error message detail strings.
**Fix**: OTP is now only sent via `utils/sms.py` (SMS stub/real provider). It is never in the HTTP response. Error messages say "Invalid OTP" without revealing the expected value.

### 9.2 OTP Rate Limiting (Implemented)
**Issue**: No limit on OTP send requests — allowed phone enumeration and SMS bombing.
**Fix**: In-process sliding-window counter per phone number. Default: 3 requests per 10 minutes. Configurable via `RATE_LIMIT_OTP_MAX` and `RATE_LIMIT_OTP_WINDOW_SECONDS`. Returns `HTTP 429` on violation.
> For multi-server deployments replace `_phone_timestamps` dict with a Redis-backed counter (e.g. slowapi with Redis backend).

### 9.3 OTP Expiry (Hardcoded → ENV VAR)
**Issue**: 90-second OTP expiry was hardcoded.
**Fix**: `OTP_EXPIRY_SECONDS` env var (default 90). Expired OTPs are immediately nulled on detection.

### 9.4 Refresh Token O(1) Lookup + jti (Implemented)
**Issue**: Token refresh did a full-table bcrypt scan — O(n) and slow under load.
**Fix**: Each refresh token embeds a `jti` UUID in the JWT payload, stored in `RefreshToken.jti` (unique, indexed). Refresh now does a direct `WHERE jti=?` lookup then one bcrypt verify. Legacy tokens (no jti) fall back to the old scan gracefully.

### 9.5 bcrypt 72-byte Truncation (Documented)
**Risk**: bcrypt silently ignores bytes beyond 72. Refresh tokens are base64-encoded JWTs which can exceed 72 bytes, making two different tokens hash to the same value.
**Mitigation**: `token[:72]` is consistently used for both hashing and verification. This is documented and acceptable for refresh tokens as long as tokens are long random strings.

### 9.6 Wallet Charge — Direct Balance Add Removed (Fixed)
**Issue**: `POST /wallets/charge-wallet` allowed any authenticated user to add arbitrary amounts to their wallet — a critical financial vulnerability.
**Fix**: Endpoint removed. Users charge wallets via `POST /wallets/initiate-charge` → Paylink payment flow. Only admins can directly credit balances via `POST /admin/wallets/{user_id}/charge` (Basic auth protected).

### 9.7 Promocode One-Use-Per-User Enforcement (Implemented)
**Issue**: A user could apply the same promo code multiple times.
**Fix**: `PromocodeUsage` table with `UNIQUE(user_id, promocode_id)` constraint. Before applying a code, the handler checks for an existing row. After a successful payment, a new row is inserted.

### 9.8 Courier Approval Guard (Implemented)
**Issue**: Any courier could accept orders and join city broadcast rooms regardless of admin approval.
**Fix**:
- `accept_order` checks `profile.is_approved` and `profile.is_available`; returns `403` otherwise
- `GET /orders/courier/available` checks `is_approved`
- WebSocket courier room join checks `profile.is_approved AND profile.is_available`
- Availability toggle (`PUT /couriers/availability`) checks `is_approved` first

### 9.9 Customer Confirmation Before Completion (Implemented)
**Issue**: A courier could mark an order as DONE without the customer confirming receipt, enabling fraudulent payment extraction.
**Fix**: `Order.customer_confirmed` boolean. Customer calls `POST /orders/{id}/confirm-delivery` to set it. The `complete_order` endpoint checks this flag and returns `400` if not set.

### 9.10 Cross-User Access Control
All resource-access endpoints verify ownership:
- `GET /payments/{id}` — checks `payment.user_id == current_user.id`
- `POST /payments/pay-with-wallet/{invoice_id}` — checks `invoice.order.created_by_user_id == current_user.id`
- `GET /events/{id}` — checks `event.user_id == current_user.id`
- Order endpoints — checks creator or assigned courier

### 9.11 Deprecated datetime.utcnow() (Fixed)
**Issue**: `datetime.utcnow()` is deprecated in Python 3.12+ and produces naive datetimes (no timezone info), causing comparison bugs with timezone-aware datetimes from the database.
**Fix**: Replaced all occurrences with `datetime.now(timezone.utc)` throughout `auth.py`, `routers/orders.py`, `routers/payments.py`, `routers/wallets.py`, `routers/promocodes.py`.

### 9.12 WebSocket Race Condition (Fixed)
**Issue**: `broadcast_to_room` iterated over `self.rooms[room]` (a mutable `set`) while the error handler modified it inside the same loop — `RuntimeError: Set changed size during iteration`.
**Fix**: Snapshot the set with `list(self.rooms.get(room, []))` before iterating. Error handler uses `.pop()` / `.discard()` instead of `del`.

### 9.13 All Config Values in ENV VARS
No values are hardcoded. The full list is in §11 below.

---

## 10. Performance & Indexing

### DB Indexes
All foreign keys have explicit `Index(...)` declarations. Key compound indexes:
- `idx_courier_balance_addition_user` — `(user_id, created_at)` for earnings queries
- `idx_user_role` — `(role)` for role-based filtering
- `RefreshToken.jti` — unique index for O(1) token lookup

### Pagination
All list endpoints accept `?skip=N&limit=M` (max 100). Default limit: 50.
Endpoints paginated: `GET /orders/`, all courier order lists, `GET /payments/my-payments`, `GET /payments/invoice/{id}`, `GET /events/`, `GET /promocodes/active/list`, `GET /orders/courier/available|active|all`, `GET /couriers/available/{city_id}`.

### Async throughout
All DB operations use `AsyncSession` + `await`. SQLAdmin is configured on the async `engine`. `asyncpg` is used as the PostgreSQL driver (vs `psycopg2` which would block the event loop).

### Eager loading
`selectinload(Order.invoice)` and similar are applied on all endpoints that return nested objects to avoid N+1 queries.

### `last_activity` Debounce
`LastActivityMiddleware` updates `User.last_activity` at most once per 60 seconds per user to avoid a DB write on every request.

---

## 11. Configuration (ENV VARS)

All settings are in `config.py` (`pydantic-settings`); loaded from `.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | required | JWT signing key (≥ 32 chars recommended) |
| `DATABASE_URL` | required | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | required | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | required | Refresh token TTL |
| `AWS_ACCESS_KEY_ID` | required | S3 / R2 key |
| `AWS_SECRET_ACCESS_KEY` | required | S3 / R2 secret |
| `AWS_S3_BUCKET_NAME` | required | Bucket name |
| `AWS_REGION` | `auto` | AWS region or `auto` for R2 |
| `STORAGE_ENDPOINT_URL` | `""` | Cloudflare R2 endpoint URL |
| `OTP_EXPIRY_SECONDS` | `90` | OTP validity window |
| `RATE_LIMIT_OTP_MAX` | `3` | Max OTP requests per phone per window |
| `RATE_LIMIT_OTP_WINDOW_SECONDS` | `600` | Rate limit window (10 min) |
| `SMS_PROVIDER_ENABLED` | `false` | Set to `true` and implement `utils/sms.py` |
| `PAYLINK_API_KEY` | `""` | Paylink.sa API key |
| `PAYLINK_TEST_MODE` | `true` | Use Paylink sandbox |
| `PAYLINK_CALLBACK_URL` | `""` | Public URL Paylink calls after payment |
| `PAYLINK_RETURN_URL` | `""` | URL user is redirected to after payment |

---

## 12. Testing

```bash
cd backend
pip install -r requirements.txt
pytest
```

Tests use **async SQLite in-memory** (`aiosqlite`) + **httpx AsyncClient**. No real database or external services required. External services (SMS, Paylink, S3) are mocked via `unittest.mock.patch`.

### Test coverage
| File | What it covers |
|------|---------------|
| `test_auth.py` | OTP send/verify, rate limiting, profile completion, refresh rotation, logout, push token, expired/malformed tokens |
| `test_orders.py` | Create, list/paginate, accept (approval guards), confirm-delivery, complete (confirmation + invoice guards), cancel, cross-user access |
| `test_payments.py` | Wallet payment, promo codes, duplicate promo use blocked, Paylink callback (paid/failed/idempotent/wallet top-up), access control |
| `test_wallets.py` | Get wallet, initiate-charge (min amount, no key), request-deposit (courier only) |
| `test_couriers.py` | Availability toggle (approved/unapproved), list available couriers |
| `test_events.py` | CRUD, pagination, access isolation |
| `test_promocodes.py` | Apply (valid/expired/min order/exhausted), list (pagination, expired excluded, usage count hidden) |
| `test_security.py` | Expired/malformed JWT, cross-user access, promo replay (DB constraint), SQL injection safety, XSS safety, unapproved courier guards |

---

## 13. Implemented Improvements

The following were implemented from the initial suggestions list:

1. **OTP never in HTTP response** — `send_sms()` abstraction; `send-otp` returns only `{"message": "OTP sent successfully"}`
2. **OTP rate limiting** — sliding window per phone; configurable via `RATE_LIMIT_OTP_MAX` / `RATE_LIMIT_OTP_WINDOW_SECONDS`
3. **OTP expiry as ENV VAR** — `OTP_EXPIRY_SECONDS` (default 90 s)
4. **Refresh token O(1) lookup via jti** — UUID in JWT + unique index on `RefreshToken.jti`
5. **Wallet charge gate** — removed direct-add endpoint; users go through Paylink; admin retains direct credit endpoint
6. **Paylink gateway wired** — `POST /payments/` for card/Apple Pay/Mada; `POST /wallets/initiate-charge` for top-up; `POST /payments/paylink-callback` webhook
7. **Promocode one-use-per-user** — `PromocodeUsage` table with `UNIQUE(user_id, promocode_id)` constraint
8. **Pagination** — all list endpoints accept `skip` + `limit` (max 100)
9. **Courier approval guard** — `accept_order`, `GET /courier/available`, WebSocket join all check `is_approved` + `is_available`
10. **Customer delivery confirmation** — `POST /orders/{id}/confirm-delivery` sets `customer_confirmed`; `complete_order` enforces it
11. **`ConversationStatus` enum** — `active | inactive | closed` stored as VARCHAR
12. **`datetime.utcnow()` replaced** — all occurrences use `datetime.now(timezone.utc)`
13. **WebSocket race condition fixed** — snapshot set before iteration in `broadcast_to_room` and `send_to_user`
14. **Push token storage** — `PUT /auth/push-token` stores FCM/APNs token on `CustomerProfile` or `CourierProfile`
15. **Request logging middleware** — JSON log per request with `request_id`, `method`, `path`, `status_code`, `duration_ms`
16. **Last-activity tracking** — `LastActivityMiddleware` debounced to 1 write per 60 s per user
17. **Health endpoint** — `GET /health` returns `{"status": "ok"}`
18. **Comprehensive test suite** — async, covers all flows and security scenarios; no real DB or external services needed
