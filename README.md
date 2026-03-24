# Hadiyati — Deep Technical Reference (Backend)

A FastAPI-based delivery and gifting platform backend for the Saudi Arabian market. It handles OTP phone authentication, order lifecycle management, real-time courier matching via WebSockets, invoice generation, multi-method payment processing, and media storage on Cloudflare R2.

---

## Table of Contents

1. [Tech Stack](#1-tech-stack)
2. [Project Structure](#2-project-structure)
3. [Environment Configuration](#3-environment-configuration)
4. [Database Architecture](#4-database-architecture)
5. [Authentication & Authorization Flow](#5-authentication--authorization-flow)
6. [API Endpoints Reference](#6-api-endpoints-reference)
7. [Router Business Logic](#7-router-business-logic)
8. [WebSocket Architecture](#8-websocket-architecture)
9. [Storage — Cloudflare R2](#9-storage--cloudflare-r2)
10. [Admin Dashboard](#10-admin-dashboard)
11. [Background Tasks & Email](#11-background-tasks--email)
12. [Enums & Domain Constants](#12-enums--domain-constants)
13. [Performance & Indexing Strategy](#13-performance--indexing-strategy)
14. [Error Handling & Validation](#14-error-handling--validation)
15. [Database Migration Scripts](#15-database-migration-scripts)
16. [Suggestions & Improvements](#16-suggestions--improvements)

---

## 1. Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Web Framework | FastAPI | 0.128.5 |
| ORM | SQLAlchemy (async) | 2.0.46 |
| Database Driver | asyncpg | latest |
| Database | PostgreSQL | 14+ |
| Validation | Pydantic v2 | 2.12.5 |
| Auth / JWT | python-jose | 3.5.0 |
| Password Hashing | passlib + bcrypt | 1.7.4 / 3.2.2 |
| Media Storage | boto3 (Cloudflare R2 / S3-compat) | 1.35.0 |
| HTTP Client | httpx | 0.28.1 |
| PDF Generation | reportlab | 4.3.0 |
| Admin Dashboard | sqladmin | 0.23.0 |
| WebSockets | websockets | 12.0 |
| Testing | pytest + pytest-asyncio | 8.4.1 |
| Config Management | pydantic-settings | 2.x |

---

## 2. Project Structure

```
backend/
├── main.py                          # App factory, middleware, WebSocket endpoint, SQLAdmin mount
├── database.py                      # Async engine, AsyncSessionLocal, Base
├── models.py                        # All 18 SQLAlchemy ORM models
├── schemas.py                       # All Pydantic request/response models
├── enums.py                         # Domain enumerations
├── auth.py                          # JWT utilities, OTP, password hashing, FastAPI dependencies
├── admin.py                         # SQLAdmin model view registrations
├── config.py                        # pydantic-settings Settings class
├── websocket_manager.py             # Room-based WebSocket connection manager
├── websocket_events.py              # Typed event emitters (orders, chat, invoices)
├── storage_client.py                # Cloudflare R2 / S3 upload client
├── paylink_client.py                # Paylink.sa gateway client (prepared, not yet active)
├── reset_admin.py                   # CLI utility to reset admin password
├── routers/
│   ├── auth.py                      # OTP login, profile completion, token refresh, logout
│   ├── orders.py                    # Order CRUD, image upload, courier broadcast
│   ├── invoices.py                  # Invoice creation (admin + courier paths), PDF
│   ├── payments.py                  # Payment processing, wallet pay, coupon application
│   ├── wallets.py                   # Wallet balance, charge, deposit requests
│   ├── chat.py                      # Conversations, messages, media upload
│   ├── promocodes.py                # Promo code validation and public listing
│   ├── cities.py                    # Active city listing
│   ├── events.py                    # Customer important events CRUD
│   └── admin.py                     # Admin info endpoint (Basic auth protected)
├── utils/
│   ├── email_utils.py               # SMTP send functions
│   ├── background_email.py          # BackgroundTask wrappers for routers
│   └── templates.py                 # Jinja2 email templates
├── tests/
│   ├── conftest.py                  # Pytest fixtures, async DB test setup
│   └── test_*.py                    # Router-level integration tests
└── test_scripts_for_admin_dashboard/
    └── *.py                         # 37+ one-shot migration and seed scripts
```

---

## 3. Environment Configuration

All configuration is loaded via `config.py` using `pydantic-settings.BaseSettings`. The `.env` file must define:

```dotenv
# JWT signing
SECRET_KEY=your-256-bit-secret
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# PostgreSQL (asyncpg driver)
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname

# Cloudflare R2 / AWS S3
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_S3_BUCKET_NAME=xxx
STORAGE_ENDPOINT_URL=https://xxx.r2.cloudflarestorage.com
```

The `Settings` object is instantiated once at import time and used as a singleton everywhere. There are no runtime config mutations.

---

## 4. Database Architecture

### 4.1 Currency Convention

All monetary amounts are stored as **integers in halaym** (smallest SAR unit: 1 SAR = 100 halaym). This avoids floating-point precision errors entirely. Conversion is handled at the API input/output layer.

### 4.2 Soft Delete Convention

Models that must preserve an audit trail use `deleted_at: DateTime | None`. All read queries filter `WHERE deleted_at IS NULL`. Hard deletes are never performed on these models.

Affected models: `Order`, `Invoice`, `Message`, `Conversation`, `Payment`, `Promocode`, `CourierReview`

### 4.3 Unique ID Formats

| Model | Column | Format | Example |
|---|---|---|---|
| Order | `order_id` | `ORDR-{100000 + id}` | `ORDR-100042` |
| Invoice | `invoice_id` | `INV-{id:06d}` | `INV-000001` |

---

### 4.4 Model Reference

#### User

Central identity model. Customers and couriers share this table, distinguished by `role`.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| phone_number | String UNIQUE | Normalized to `5XXXXXXXXX` |
| email | String UNIQUE nullable | |
| name | String | Arabic/English only |
| date_of_birth | Date nullable | Min age 16 |
| is_verified | Boolean | `False` until OTP confirmed |
| otp | String nullable | 6-digit, expires after 90s |
| otp_created_at | DateTime nullable | Used for expiry check |
| role | Enum(UserRole) | CUSTOMER / COURIER |
| last_activity | DateTime nullable | Updated on activity |

Relationships: `refresh_tokens`, `created_orders`, `assigned_orders`, `wallet`, `payments`, `created_invoices`, `courier_profile`, `customer_profile`

---

#### Admin

Separate model from User. Used exclusively for dashboard access. Not a JWT-based user.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| username | String UNIQUE | |
| password_hash | String | bcrypt |
| name | String | |
| email | String UNIQUE nullable | |
| is_active | Boolean | Checked on every admin request |
| created_at / updated_at | DateTime | |

---

#### CourierProfile

Extended data for couriers. Created when a user completes profile with the COURIER role.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| user_id | FK → User UNIQUE | |
| national_id | String nullable | |
| passport_id | String nullable | |
| city_id | FK → City | Courier's operating city |
| iban | String | For payout deposits |
| vehicle | String nullable | |
| license | String nullable | |
| rate | Integer | Stored as `avg_rating * 10` (e.g., 4.5 → 45) |

Indexes: `user_id`, `city_id`

---

#### CustomerProfile

Lightweight extension for customer-specific data.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| user_id | FK → User UNIQUE | |
| timezone | String nullable | IANA timezone string (e.g., `Asia/Riyadh`) |

Index: `user_id`

---

#### Order

Core transactional entity. Follows a defined status lifecycle.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| order_id | String UNIQUE | `ORDR-{100000+id}` |
| created_by_user_id | FK → User | Customer |
| assigned_to_user_id | FK → User nullable | Assigned courier |
| description | Text nullable | |
| creation_date | DateTime | Server default now |
| delivery_date | DateTime(tz) nullable | |
| status | Enum(OrderStatus) | See lifecycle below |
| comments | Text nullable | |
| updated_at | DateTime | |
| deleted_at | DateTime nullable | Soft delete |
| city_id | FK → City | |

**Order Status Lifecycle:**

```
NEW
 └──(courier accepts)──► RECEIVED_BY_COURIER
                               └──(invoice paid)──► PAID
                                                     └──(work starts)──► IN_PROGRESS_TO_DO
                                                                          └──(en route)──► IN_PROGRESS_TO_DELIVER
                                                                                             └──(complete)──► DONE
(any non-terminal stage) ──► CANCELLED
```

Relationships: `created_by_user`, `assigned_to_user`, `city`, `invoice`, `conversation`, `images`

Indexes (6):
- `idx_order_created_by`: `(created_by_user_id, creation_date DESC)` — customer order history
- `idx_order_assigned_to`: `(assigned_to_user_id, status)` — courier's active orders
- `idx_order_status`: `(status, updated_at DESC)` — admin dashboard status filter
- `idx_order_city`: `(city_id, status)` — broadcast targeting by city
- `idx_order_delivery`: `delivery_date` partial, `WHERE delivery_date IS NOT NULL`
- `idx_order_admin`: `(status, city_id, creation_date DESC)` — composite admin filter

---

#### OrderImage

Up to 3 image URLs per order, stored after R2 upload.

| Column | Type |
|---|---|
| id | Integer PK |
| order_id | FK → Order |
| image1_url / image2_url / image3_url | String nullable |
| created_at | DateTime |

Index: `order_id`

---

#### Invoice

Financial document attached 1:1 to an order. Created by courier or admin.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| invoice_id | String UNIQUE | `INV-000001` |
| order_id | FK → Order | |
| created_by_user_id | FK → User | Courier or admin |
| full_amount | Integer | Total in halaym |
| service_fee | Integer | Default 0 |
| order_only_price | Integer | Subtotal before fees |
| courier_fee | Integer | Default 0 |
| status | Enum(InvoiceStatus) | NEW → PAID / CANCELLED / REFUNDED / OTHER |
| description / comment | Text nullable | |
| sent_to_user_via_email | Boolean | |
| sent_at | DateTime nullable | |
| due_date | DateTime nullable | |
| tax_amount | Integer | Default 0 |
| discount_amount | Integer | Default 0 |
| promocode_id | FK → Promocode nullable | Applied discount code |
| deleted_at | DateTime nullable | |

Indexes (3):
- `idx_invoice_order`: `order_id`
- `idx_invoice_status`: `(status, due_date)`
- `idx_invoice_paid`: `(status, sent_to_user_via_email)`

---

#### Conversation

One conversation per order. Always between one Customer and one Courier.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| customer_id | FK → User | |
| courier_id | FK → User nullable | Set when courier is assigned |
| order_id | FK → Order | |
| status | String | `active` / `inactive` / `closed` |
| created_at | DateTime(tz) | |
| deleted_at | DateTime nullable | |

Unique constraint: `(customer_id, order_id)` — prevents duplicate conversations per order.

Indexes (4):
- `idx_conversation_customer`: `(customer_id, created_at DESC)`
- `idx_conversation_courier`: `(courier_id, created_at DESC)`
- `idx_conversation_order`: `(order_id, created_at DESC)`
- `idx_conversation_status`: `(status, created_at DESC)`

---

#### Message

All chat messages. Carries invoice pricing inline for `invoice`-type messages.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| conversation_id | FK → Conversation | |
| sender_id | FK → User nullable | `NULL` for system messages |
| content | Text | Main message body |
| sent_at | DateTime(tz) | Server default |
| message_type | String | `text` / `invoice` / `image` / `video` / `system` |
| media_type | String nullable | `image` / `video` |
| invoice_description | Text nullable | |
| invoice_gift_price | Integer nullable | In halaym |
| invoice_service_fee | Integer nullable | In halaym |
| invoice_delivery_fee | Integer nullable | In halaym |
| invoice_total | Integer nullable | In halaym |
| media_url | String nullable | R2 CDN URL |
| deleted_at | DateTime nullable | |

Indexes (4):
- `idx_message_conversation`: `(conversation_id, sent_at DESC)` — paginated message fetch
- `idx_message_sender`: `(sender_id, sent_at DESC)`
- `idx_message_type`: `(message_type, sent_at DESC)`
- `idx_message_media_type`: `media_type`

---

#### Wallet

One wallet per user. Holds balance in halaym.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| user_id | FK → User UNIQUE | |
| balance | Integer | Default 0, in halaym |
| created_at / updated_at | DateTime | |

Indexes: `user_id`, `balance`

---

#### Payment

One payment record per transaction. Multiple payments can exist per invoice.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| invoice_id | FK → Invoice | |
| user_id | FK → User | Payer |
| amount | Integer | In halaym |
| payment_method | Enum(PaymentMethod) | WALLET / CREDIT_CARD / APPLE_PAY / MADA |
| status | Enum(PaymentStatus) | PENDING / COMPLETED / FAILED / REFUNDED |
| transaction_id | String nullable | From payment processor |
| payment_date | DateTime nullable | |
| payment_details | Text nullable | JSON string for gateway metadata |
| wallet_balance_before | Integer nullable | Balance snapshot before deduction |
| deleted_at | DateTime nullable | |

Indexes (4):
- `idx_payment_invoice`: `invoice_id`
- `idx_payment_user`: `(user_id, created_at)`
- `idx_payment_status`: `(status, payment_date)`
- `idx_payment_method`: `(payment_method, status)`

---

#### DepositRequest

Courier requests a cash payout from their wallet. Admin approves or rejects.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| courier_id | FK → User | |
| status | Enum(DepositRequestStatus) | PENDING / APPROVED / REJECTED |
| amount | Integer | In halaym |
| wallet_balance_before | Integer | Balance snapshot at request time |

Indexes: `(courier_id, created_at)`, `(status, created_at)`

---

#### CourierBalanceAddition

Audit log of every credit applied to a courier's wallet after a customer payment.

| Column | Type |
|---|---|
| id | Integer PK |
| invoice_id | FK → Invoice |
| order_id | FK → Order |
| user_id | FK → User (payer) |
| payment_method | Enum(PaymentMethod) |
| balance_before | Integer |
| amount_to_add | Integer |
| created_at | DateTime |

Indexes: `invoice_id`, `order_id`, `(user_id, created_at)`, `created_at`

---

#### RefreshToken

Hashed refresh tokens. Supports per-device sessions and full token rotation.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| user_id | FK → User | |
| token_hash | String | bcrypt hash, 72-byte truncation applied before hashing |
| device_id | String nullable | For per-device token tracking |
| expires_at | DateTime | |
| revoked | Boolean | Default False |
| created_at | DateTime | |

Indexes:
- `idx_refresh_user`: `(user_id, revoked, expires_at)` — fast token validation
- `idx_refresh_device`: `(user_id, device_id)` — device-specific revocation

---

#### Promocode

Discount codes configurable per target (total, service fee, or delivery fee).

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| name / code | String | `code` is UNIQUE |
| description | Text nullable | |
| percentage | Integer | 0–100 |
| max_value | Integer | 0 = no cap on discount |
| minimum_order_value | Integer | 0 = no minimum |
| usage_limit | Integer | 0 = unlimited uses |
| usage_count | Integer | Auto-incremented on invoice payment |
| valid_until | DateTime | |
| active | Boolean | |
| applicable_to | String | `order_total` / `service_fee` / `delivery_fee` |
| deleted_at | DateTime nullable | |

Indexes:
- `code`
- `(active, valid_until)`
- `(active, valid_until, usage_limit, usage_count)` — composite for validation query

---

#### City

Reference data for available delivery cities.

| Column | Type |
|---|---|
| id | Integer PK |
| name | String |
| icon | String nullable |
| active | Boolean |

---

#### CourierReview

Customer ratings for couriers. Includes SQLAlchemy event listeners that maintain a denormalized rating.

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| reviewed_by | FK → User | Customer who left the review |
| reviewed | FK → User | Courier being reviewed |
| rate | Integer | 0–5 |
| comment | Text nullable | |
| deleted_at | DateTime nullable | |

**Event Listener Pattern:** After any INSERT, UPDATE, or DELETE on `CourierReview`, a SQLAlchemy `after_flush` listener recalculates `AVG(rate) * 10` across all non-deleted reviews for that courier and writes it back to `CourierProfile.rate`. This keeps the denormalized field always current without a separate job.

Indexes: `(reviewed_by, created_at)`, `(reviewed, created_at)`, `rate`

---

#### ImportantEvent

Customer-maintained calendar events for gift-giving reminders (birthdays, anniversaries, etc.).

| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| user_id | FK → User | |
| title | String | |
| event_date | DateTime | Must be in the future at creation time |
| recurring | Boolean | Default False |

Indexes: `(user_id, event_date)`, `event_date`

---

## 5. Authentication & Authorization Flow

### 5.1 OTP Authentication Sequence

```
Client                                  Server
  │                                        │
  ├── POST /auth/send-otp ───────────────► │
  │   { phone_number }                     │  1. Regex validate Saudi format (+966/0-5XX)
  │                                        │  2. Normalize → "5XXXXXXXXX"
  │                                        │  3. Generate random 6-digit OTP
  │                                        │  4. Store OTP + otp_created_at on User
  │ ◄── { message, otp } ─────────────── │  5. Return OTP (prod: deliver via SMS only)
  │                                        │
  ├── POST /auth/verify-otp ────────────► │
  │   { phone_number, otp, device_id? }    │  1. Fetch User by phone
  │                                        │  2. Check: now - otp_created_at < 90s
  │                                        │  3. Compare submitted OTP
  │                                        │  ─── Branch A: existing verified user ───
  │                                        │  4a. Create access token (15 min)
  │                                        │  4b. Create refresh token (30 days)
  │                                        │  4c. bcrypt-hash token, store in RefreshToken
  │ ◄── { access_token, refresh_token,    │
  │        needs_profile: false } ─────── │
  │                                        │  ─── Branch B: new / unverified user ────
  │                                        │  4d. Issue temp access token (30 min)
  │ ◄── { access_token,                   │
  │        needs_profile: true } ──────── │
  │                                        │
  ├── POST /auth/complete-profile ──────► │  (Only if needs_profile was true)
  │   { name, email, DOB, role, tz }       │  1. Validate all fields
  │                                        │  2. Set user.is_verified = True
  │                                        │  3. Create CourierProfile or CustomerProfile
  │                                        │  4. Create Wallet (balance = 0)
  │                                        │  5. Issue full access + refresh token pair
  │ ◄── { access_token, refresh_token } ─ │  6. Send welcome email (background task)
```

---

### 5.2 JWT Token Structure

**Access Token** — HS256, expires in `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 15):

```json
{
  "sub": "42",
  "phone_number": "559xxxxxxx",
  "role": "Customer",
  "name": "Ahmed",
  "is_verified": true,
  "city_id": 3,
  "timezone": "Asia/Riyadh",
  "exp": 1234567890
}
```

> `city_id` is populated only for Couriers. `timezone` is populated only for Customers.

**Refresh Token** — HS256, expires in `REFRESH_TOKEN_EXPIRE_DAYS` (default: 30):

```json
{
  "sub": "42",
  "type": "refresh",
  "exp": 1234567890
}
```

---

### 5.3 Token Rotation Flow

```
Client                                  Server
  │                                        │
  ├── POST /auth/refresh ───────────────► │
  │   { refresh_token }                    │  1. Decode JWT, check expiry
  │                                        │  2. Query RefreshToken WHERE
  │                                        │     user_id=sub AND revoked=False
  │                                        │     AND expires_at > now
  │                                        │  3. bcrypt.verify(token[:72], stored_hash)
  │                                        │  4. Mark old token revoked = True
  │                                        │  5. Issue new access + refresh token pair
  │ ◄── { access_token, refresh_token } ─ │  6. Store new hash in RefreshToken
```

> **72-byte truncation:** bcrypt silently ignores bytes beyond 72. Without explicit truncation, two tokens differing only in characters after position 72 would produce identical hashes. The code truncates to 72 bytes before every `hash()` and `verify()` call.

---

### 5.4 Authorization Layers

| Scope | Mechanism | Where applied |
|---|---|---|
| Any authenticated user | `Depends(get_current_user)` — decodes Bearer JWT, fetches User | Most endpoints |
| Customer only | `Depends(get_current_customer)` — wraps above, asserts `role == CUSTOMER` | Events, wallet deposit |
| Courier only | `Depends(get_current_courier)` — wraps above, asserts `role == COURIER` | Courier invoice creation |
| Admin dashboard | Basic auth middleware in `main.py` | All `/admin/*` routes |

---

### 5.5 Admin Middleware

Every request to `/admin/*` is intercepted before reaching any router:

1. Extract `Authorization: Basic <base64>` header → 401 if absent
2. Base64-decode → `username:password`
3. Query `Admin` by username → 401 if not found
4. Assert `Admin.is_active == True` → 401 if inactive
5. `bcrypt.verify(password, admin.password_hash)` → 401 if mismatch

---

## 6. API Endpoints Reference

### Auth — `/auth`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/send-otp` | None | Generate and store 6-digit OTP |
| POST | `/auth/verify-otp` | None | Verify OTP, issue tokens |
| POST | `/auth/complete-profile` | None | Finish registration, issue full token pair |
| POST | `/auth/refresh` | None | Rotate refresh token |
| GET | `/auth/me` | Bearer | Get current user's profile |
| PUT | `/auth/me` | Bearer | Update profile fields |
| PUT | `/auth/timezone` | Bearer | Update customer timezone |
| POST | `/auth/logout` | None | Revoke refresh token |

---

### Orders — `/orders`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/orders/` | Bearer | Create order with up to 3 images (multipart/form-data) |
| GET | `/orders/` | Bearer | List own orders (paginated: `skip`, `limit`) |
| GET | `/orders/{order_id}` | Bearer | Get single order with embedded invoice |
| POST | `/orders/{order_id}/assign` | Bearer (admin) | Assign courier to order |
| POST | `/orders/{order_id}/cancel` | Bearer | Cancel order with reason |

**Order creation sequence:**
1. Validate `city_id` exists and is active
2. Insert `Order` row
3. Upload up to 3 images to R2 → insert `OrderImage`
4. Auto-create `Conversation` for the customer
5. Emit WebSocket event `new_order` to room `couriers_city_{city_id}` — all online couriers in that city receive real-time notification

---

### Invoices — `/invoices`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/invoices/` | Admin middleware | Admin creates invoice for an order |
| POST | `/invoices/courier/create` | Bearer (Courier) | Courier creates invoice for their assigned order |
| GET | `/invoices/{invoice_id}` | Bearer | Get invoice by ID |
| GET | `/invoices/order/{order_id}` | Bearer | All invoices for an order |

**Invoice creation sequence:**
1. Validate the courier is assigned to the order (for courier path)
2. Generate sequential `invoice_id` (`INV-000001`)
3. Insert `Invoice`
4. Emit `invoice_created` WebSocket event to conversation room
5. Optionally send PDF via email in background

---

### Payments — `/payments`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/payments/` | Bearer | Create raw payment record |
| POST | `/payments/pay-with-wallet/{invoice_id}` | Bearer | Pay invoice from wallet with optional promo code |
| GET | `/payments/{payment_id}` | Bearer | Get payment by ID |
| GET | `/payments/invoice/{invoice_id}` | Bearer | All payments for an invoice |
| GET | `/payments/my-payments` | Bearer | Current user's payment history |

**Wallet payment sequence:**
1. Verify the caller owns the order linked to the invoice
2. If promo code provided: validate, calculate discount
3. Snapshot `wallet.balance` → `wallet_balance_before`
4. Deduct `final_amount` from `Wallet.balance`
5. Insert `Payment` (status = COMPLETED)
6. Update `Invoice.status` → PAID
7. Insert `CourierBalanceAddition` to credit courier wallet
8. Send system message to conversation: "Payment confirmed"
9. Emit WebSocket events to both customer and courier user rooms

---

### Wallets — `/wallets`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/wallets/my-wallet` | Bearer | Get current balance |
| POST | `/wallets/charge-wallet` | Bearer | Add funds directly (no payment gateway — dev only) |
| POST | `/wallets/request-deposit` | Bearer (Courier) | Create a PENDING DepositRequest for payout |

**Amount constraints:**
- Minimum charge/deposit: 10 SAR (1000 halaym)
- Deposit request: Input float with max 2 decimal places

---

### Chat — `/chat`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/chat/conversations` | Bearer | Create or retrieve existing conversation |
| GET | `/chat/conversations/{id}/messages` | Bearer | Paginated message history (`skip`, `limit`) |
| POST | `/chat/conversations/{id}/messages` | Bearer | Send message (text, invoice, image, video, system) |

**Conversation creation rules:**
- Exactly one participant must be Customer, the other must be Courier
- Unique constraint `(customer_id, order_id)` prevents duplicate conversations

**Message send sequence:**
1. Assert caller is a conversation participant (403 otherwise)
2. If `media_file` attached: validate type/size, upload to R2, store CDN URL
3. Insert `Message`
4. Emit `chat_message` WebSocket event to room `chat_{conversation_id}`

**Media limits:**
- Images: 15 MB — `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `image/svg+xml`
- Videos: 100 MB — `video/mp4`, `video/avi`, `video/mov`, `video/mkv`, `video/webm`

---

### Promocodes — `/promocodes`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/promocodes/apply` | None | Validate code and preview discount amount |
| GET | `/promocodes/active/list` | None | List all currently active codes |

**Discount calculation logic:**
```
discount = floor(order_total × percentage / 100)
if max_value > 0:
    discount = min(discount, max_value)
final_amount = order_total − discount
```

> `apply` only **previews** the discount. `usage_count` is only incremented when the invoice is actually paid.

---

### Cities — `/cities`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/cities/` | None | List all cities where `active = True` |

---

### Events — `/events`

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/events/` | Bearer (Customer) | Create an important event |
| GET | `/events/` | Bearer (Customer) | List own events |
| GET | `/events/{id}` | Bearer (Customer) | Get single event |
| PUT | `/events/{id}` | Bearer (Customer) | Update event fields |
| DELETE | `/events/{id}` | Bearer (Customer) | Delete event |

Validation: `event_date` must be in the future at creation time.

---

### Admin — `/admin`

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/admin/me` | Basic auth | Get current admin's info |

The full SQLAdmin dashboard is at `/admin/` — protected by Basic auth middleware.

---

## 7. Router Business Logic

### Dependency Chain

```python
# Any protected endpoint:
current_user = Depends(get_current_user)
#  → extracts Bearer token from Authorization header
#  → decodes JWT with python-jose (HS256)
#  → queries User by token.sub
#  → raises HTTP 401 if token is invalid or expired

current_customer = Depends(get_current_customer)
#  → calls get_current_user internally
#  → raises HTTP 403 if user.role != CUSTOMER

current_courier = Depends(get_current_courier)
#  → calls get_current_user internally
#  → raises HTTP 403 if user.role != COURIER
```

### Database Session Pattern

Every endpoint receives a fresh `AsyncSession` via dependency injection:

```python
# database.py
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

All queries within one request share one transaction. Rollback happens automatically on unhandled exceptions via the async context manager. Explicit `await db.commit()` is called only on success.

### Ownership Checks

Before any mutating operation on a resource (invoice, order, message), the router explicitly checks that the requesting user is the owner or a participant. Returning 403 if not. No implicit trust from the token alone.

---

## 8. WebSocket Architecture

### Connection Endpoint

```
WS /ws/{user_id}
```

**On connect:**
1. Add `WebSocket` to `ConnectionManager.active_connections[user_id]`
2. Auto-join room `user_{user_id}`

**On disconnect:**
- Remove from all joined rooms
- Remove from `active_connections`

---

### Room System

| Room Name | Who joins | When | Purpose |
|---|---|---|---|
| `user_{user_id}` | Every user | On WebSocket connect | Direct messages to one user |
| `chat_{conversation_id}` | Customer + Courier | On first message in conversation | Real-time chat delivery |
| `couriers_city_{city_id}` | Couriers | On connect, uses city_id from JWT | New order broadcasts by city |

Rooms are managed by `ConnectionManager` in `websocket_manager.py`. A user can be in multiple rooms simultaneously.

---

### WebSocket Events

| Event type | Emitted by | Target room | Payload |
|---|---|---|---|
| `new_order` | orders router | `couriers_city_{city_id}` | order_id, city_id, description |
| `order_status_change` | orders router | `user_{customer_id}` | order_id, new_status |
| `invoice_created` | invoices router | `chat_{conversation_id}` | invoice_id, amount |
| `chat_message` | chat router | `chat_{conversation_id}` | message_id, content, sender_id, type |
| `payment_confirmed` | payments router | `user_{customer_id}`, `user_{courier_id}` | invoice_id, amount |

All event emitters in `websocket_events.py` open their **own independent** `AsyncSessionLocal` session — completely isolated from the HTTP request session that triggered them. This prevents transaction interference.

---

## 9. Storage — Cloudflare R2

`storage_client.py` wraps `boto3` with the R2 endpoint URL. R2 is S3-API-compatible so no custom SDK is needed.

### Upload Path Structure

```
{8-char-random}-{user_id}-{username}/
├── order_creation_images/{uuid}.jpg
├── chat_images/{uuid}.png
└── chat_videos/{uuid}.mp4
```

### Functions

```python
upload_image(file_bytes, filename, user_id, username, subfolder) -> str  # CDN URL
upload_media(file_bytes, filename, media_type, user_id, username) -> str  # CDN URL
```

CDN Base URL: `https://storage-giftly-storage.cranl.net/`

### File Validation (before upload)

- MIME type is checked against an explicit allowlist
- File extension is extracted from `filename`, falling back to derivation from MIME type if unavailable
- Size limit is enforced at the `UploadFile.read()` level by FastAPI before the upload function is called

---

## 10. Admin Dashboard

SQLAdmin is mounted at `/admin/` in `main.py`. All 12 models are registered in `admin.py`:

`User`, `Admin`, `City`, `Order`, `Invoice`, `Conversation`, `Message`, `Wallet`, `Payment`, `Promocode`, `CourierReview`, `ImportantEvent`

Each view configures:
- **Searchable columns** — e.g., User: phone_number, name, email
- **Filterable columns** — e.g., Order: status, city_id, creation_date
- **Form exclusions** — auto-generated fields (id, created_at) excluded from create/edit forms
- **Enum choices** — rendered as human-readable dropdowns, not raw strings

Every request to any path under `/admin/` is intercepted by `AdminAuthMiddleware` (defined in `main.py`) before SQLAdmin handles it.

---

## 11. Background Tasks & Email

Email sending never blocks the HTTP response. FastAPI `BackgroundTasks` is used in routers:

```python
background_tasks.add_task(send_welcome_email_background, user.email, user.name)
background_tasks.add_task(send_invoice_email_background, invoice_id, user.email)
```

- **`utils/templates.py`** — Jinja2 template rendering for HTML email bodies
- **`utils/email_utils.py`** — SMTP connection and `send()` implementation
- **`utils/background_email.py`** — Thin wrapper functions called by routers to decouple router logic from SMTP concerns

Background tasks run in the same process after the HTTP response is returned. They are not retried on failure.

---

## 12. Enums & Domain Constants

All enums inherit from `str` so they serialize transparently in JSON and store as readable strings in PostgreSQL (no integer codes).

```python
class UserRole(str, Enum):
    CUSTOMER = "Customer"
    COURIER  = "Courier"

class OrderStatus(str, Enum):
    NEW                    = "New"
    RECEIVED_BY_COURIER    = "ReceivedByCourier"
    PAID                   = "Paid"
    IN_PROGRESS_TO_DO      = "InProgressToDo"
    CANCELLED              = "Cancelled"
    DONE                   = "Done"
    IN_PROGRESS_TO_DELIVER = "InProgressToDeliver"

class InvoiceStatus(str, Enum):
    NEW       = "New"
    PAID      = "Paid"
    CANCELLED = "Cancelled"
    REFUNDED  = "Refunded"
    OTHER     = "Other"

class PaymentMethod(str, Enum):
    WALLET      = "Wallet"
    CREDIT_CARD = "CreditCard"
    APPLE_PAY   = "ApplePay"
    MADA        = "Mada"

class PaymentStatus(str, Enum):
    PENDING   = "Pending"
    COMPLETED = "Completed"
    FAILED    = "Failed"
    REFUNDED  = "Refunded"

class DepositRequestStatus(str, Enum):
    PENDING  = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"

class ImageType(str, Enum):
    CHAT    = "Chat"
    ORDER   = "Order"
    GALLERY = "Gallery"
```

---

## 13. Performance & Indexing Strategy

### Index Count: 40+

The strategy is query-driven — every index maps to at least one production query pattern.

**High-frequency list reads → compound indexes, DESC ordering:**
- `(created_by_user_id, creation_date DESC)` — customer's order history, always newest first
- `(conversation_id, sent_at DESC)` — paginated message fetch

**Status-filtered queries → status in compound index:**
- `(assigned_to_user_id, status)` — courier's active orders list
- `(status, city_id, creation_date DESC)` — admin dashboard multi-filter

**Partial index for sparse columns:**
- `delivery_date WHERE delivery_date IS NOT NULL` — skips the majority of orders that have no delivery date, keeping the index small

**Token lookup — three conditions always applied together:**
- `(user_id, revoked, expires_at)` — single index scan covers the entire WHERE clause

**Unique constraints double as indexes:**
- `User.phone_number`, `User.email`, `Promocode.code`, `Wallet.user_id`

### Async I/O

All database operations use `AsyncSession` + `await`. There are no synchronous blocking calls on the hot request path. S3 uploads use `asyncio.to_thread` or non-blocking boto3 calls. Email is deferred to background tasks.

### No N+1 Queries

Relationships are loaded with explicit `selectinload()` or `joinedload()` in the same query. Lazy loading is not used in any endpoint.

---

## 14. Error Handling & Validation

### Input Validation

| Field | Rule |
|---|---|
| Phone number | Regex `^(\+966\|0)?[5][0-9]{8}$` → normalized to `5XXXXXXXXX` |
| Name | Arabic + English letters + spaces only, minimum 2 chars |
| Email | Pydantic `EmailStr`, uniqueness verified against DB |
| Date of birth | Must be ≥ 16 years ago and not in the future |
| Event date | Must be in the future at creation time |
| OTP | Exactly 6 digits, expires 90 seconds after generation |
| Wallet amount | Minimum 1000 halaym (10 SAR) |
| Deposit amount | Minimum 1000 halaym, max 2 decimal places on input |

### HTTP Status Codes

| Code | Condition |
|---|---|
| 200 | Success |
| 400 | Input validation failure, business rule violation |
| 401 | Missing/invalid token, wrong OTP, expired OTP, bad admin credentials |
| 403 | Valid token but wrong role, or caller does not own the resource |
| 404 | Requested resource does not exist (or is soft-deleted) |
| 500 | Unhandled server error (DB failure, S3 timeout) |

### Transaction Safety

Each endpoint opens one `AsyncSession`. On any `HTTPException` or unhandled exception, the context manager automatically calls `session.rollback()`. No partial writes can be committed.

---

## 15. Database Migration Scripts

Located in `test_scripts_for_admin_dashboard/`. These are **one-shot** scripts executed manually in order as the schema evolved. They are not a migration framework (no Alembic, no version tracking).

| Script | Purpose |
|---|---|
| `create_admin.py` | Create first admin user |
| `check_and_create_admin.py` | Idempotent admin creation |
| `add_database_indexes.py` | Apply all model indexes to existing DB |
| `add_timezone_to_users.py` | Add timezone column to users |
| `drop_timezone_from_users.py` | Revert above |
| `migrate_timezone_to_customer_profiles.py` | Move timezone from User to CustomerProfile |
| `add_device_id_to_refresh_tokens.py` | Add device_id column to refresh_tokens |
| `add_revoked_tokens_table.py` | Token revocation infrastructure |
| `add_courier_reviews_table.py` | CourierReview table |
| `create_customer_profiles_table.py` | CustomerProfile table |
| `create_important_events_table.py` | ImportantEvent table |
| `add_wallets.py` / `add_missing_wallets.py` | Wallet table setup and backfill for existing users |
| `add_payments.py` | Payment table |
| `add_promocodes.py` | Promo code seed data |
| `add_deposit_requests_table.py` | DepositRequest table |
| `add_courier_balance_and_user_fields.py` | CourierBalanceAddition table |
| `add_wallet_balance_before_to_payments.py` | Snapshot column on Payment |
| `add_last_activity_to_users.py` | last_activity column on User |
| `add_image_data_to_messages.py` | Media fields on Message |
| `create_courier_token.py` | Generate a test JWT for couriers |
| `send_courier_message.py` | Send a test WebSocket message |

---

## 16. Suggestions & Improvements

### Critical Security Fixes

**1. OTP returned in HTTP response**

`POST /auth/send-otp` currently returns the OTP value in the response body. This is a security hole — any party observing the response can impersonate any phone number.

*Fix:* Integrate an SMS provider (e.g., Unifonic, MSGSaudi, or Twilio). The OTP must only be delivered to the registered phone number and must **never** appear in the API response.

---

**2. No rate limiting on OTP endpoint**

There is no rate limiting on `POST /auth/send-otp`. Anyone can trigger unlimited OTP requests for any phone number.

*Fix:* Apply rate limiting per IP and per phone number (e.g., max 5 requests per 10 minutes). Use `slowapi` with a Redis backend, or a reverse-proxy-level rate limiter (nginx, Cloudflare).

---

**3. `POST /wallets/charge-wallet` adds balance with no payment verification**

This endpoint directly increments any user's wallet balance without going through a payment gateway. Any authenticated user can give themselves unlimited funds.

*Fix:* Wire this endpoint to a real payment gateway. `paylink_client.py` is already prepared and available. This endpoint should be removed or restricted to admin-only use until the integration is complete.

---

**4. `paylink_client.py` is never called**

`CREDIT_CARD`, `APPLE_PAY`, and `MADA` are valid enum values and can be set on a `Payment` record, but no code ever processes them through a gateway. Payments with these methods are created but never actually charged.

*Fix:* Wire `paylink_client.py` to the payments router. `CREDIT_CARD`, `APPLE_PAY`, and `MADA` payment flows must call the Paylink API before marking a payment `COMPLETED`.

---

### Architecture Improvements

**5. Replace one-shot migration scripts with Alembic**

37+ hand-written scripts cannot be reliably replayed on a fresh database in the correct order. There is no way to know the exact current schema version.

*Fix:* Adopt [Alembic](https://alembic.sqlalchemy.org/). It generates versioned, reversible migration files and tracks what has been applied. This is the standard migration tool for SQLAlchemy projects.

---

**6. Token refresh is O(n) per user**

Token refresh queries all non-revoked tokens for a user and bcrypt-verifies each one until a match is found. With multiple active sessions, this becomes slow.

*Fix:* Store a non-sensitive token `jti` (JWT ID — a UUID) in both the JWT payload and the `RefreshToken` table. Use `jti` as a direct lookup key, then bcrypt-verify only the single matching record.

---

**7. Add structured request logging**

There is no logging middleware. Debugging production issues requires guessing.

*Fix:* Add a middleware that emits a structured JSON log line for every request: `request_id`, method, path, status code, response time in ms, and user_id (if authenticated). Use `structlog` or Python's `logging` with a JSON formatter.

---

**8. Add a health check endpoint**

There is no `GET /health` or `GET /readiness` endpoint. Container orchestrators (Kubernetes, ECS) require this for liveness and readiness probes.

*Fix:* Add a lightweight endpoint that checks DB connectivity (e.g., `SELECT 1`) and returns `{ "status": "ok", "version": "x.y.z" }` with HTTP 200, or HTTP 503 if the DB is unreachable.

---

**9. Background tasks are not durable**

`BackgroundTasks` runs in the same process. If the server restarts mid-task (during email sending or PDF generation), the task is silently lost with no retry.

*Fix:* Move heavy background work (email, PDF, invoice delivery) to a proper task queue such as [ARQ](https://arq-docs.helpmanual.io/) (async, Redis-based) or Celery + Redis.

---

**10. `Conversation.status` uses raw strings, not an Enum**

The values `active`, `inactive`, `closed` are stored as plain strings. There is no enforced type, and transition rules (who can close a conversation, and when) are not defined anywhere.

*Fix:* Define a `ConversationStatus` enum in `enums.py`. Add explicit status transition logic in the router (e.g., only admin or both parties can close a conversation).

---

### Feature Suggestions

**11. Courier availability toggle**

Couriers receive broadcasts for all new orders in their city permanently, even when they are busy or offline. There is no way to stop receiving orders without deactivating the account.

*Fix:* Add `is_available: Boolean` to `CourierProfile`. WebSocket room join (`couriers_city_{city_id}`) should only happen when `is_available = True`. Add a toggle endpoint for couriers.

---

**12. Admin approval for courier registration**

Any user who selects the COURIER role can immediately appear in city rooms and receive orders. There is no vetting step.

*Fix:* Add `is_approved: Boolean` (default False) to `CourierProfile`. Couriers are excluded from city rooms until an admin approves them. Add an admin endpoint to approve/reject courier applications.

---

**13. Order completion confirmation by customer**

Orders can be moved to `DONE` status without the customer confirming receipt. A courier could mark their own order as done prematurely.

*Fix:* Add a customer-confirmation step. Courier moves to `IN_PROGRESS_TO_DELIVER`, customer confirms → `DONE`. Trigger `CourierReview` creation prompt at this point.

---

**14. Push notifications**

WebSockets only deliver events when the app is in the foreground. Order status changes, new invoices, and payment confirmations are silently missed when the app is closed.

*Fix:* Integrate APNs (iOS) and FCM (Android). Store a `push_token` on `CustomerProfile` and `CourierProfile`. Send push notifications for all high-priority WebSocket events as a fallback.

---

**15. Per-user promo code usage limit**

The same user can apply the same promo code to unlimited invoices (as long as the global `usage_limit` is not reached).

*Fix:* Add a `PromocodeUsage` table with `(user_id, promocode_id, used_at)`. Check for an existing row before applying. This enforces one-use-per-user without changing the existing `usage_limit` global cap.

---

**16. Soft-deleted record accumulation**

Records with `deleted_at` set accumulate indefinitely with no cleanup mechanism. On a high-volume platform, this will degrade query performance over time even with partial indexes.

*Fix:* Add a periodic cleanup job (Celery beat or a cron) that hard-deletes or archives records older than a configurable retention window (e.g., 90 days after `deleted_at`).

---

**17. `last_activity` is not consistently updated**

The `User.last_activity` column exists but is only updated in some flows, not on every authenticated request.

*Fix:* Add a middleware that updates `last_activity = now()` on every successful `get_current_user()` call. Debounce to once per minute per user to avoid excessive DB writes (use a short-lived in-process cache keyed on `user_id`).

---

**18. Paginate all list endpoints**

Some list endpoints (`GET /events/`, `GET /promocodes/active/list`) return all records with no limit. As data grows, these will become slow and return unbounded payloads.

*Fix:* Add `skip: int = 0` and `limit: int = 50` query parameters to every list endpoint, with a server-enforced maximum (`limit = min(limit, 100)`).

---

*This document covers the backend in its current state as of the last commit. All monetary values in this document are expressed in SAR/halaym units as used internally by the system.*
