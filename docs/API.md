# Giftly API

REST + WebSocket reference for the FastAPI backend in `src/`.

**Base URL**: app server (e.g. `http://localhost:3000`).
**Money**: every monetary amount is an integer in **halalas** (1 SAR = 100), unless an endpoint explicitly takes/returns SAR (noted inline).
**Auth scheme**: `Authorization: Bearer <access_token>` for user endpoints; HTTP Basic for `/admin/*`. The interactive SQLAdmin dashboard is mounted at `/admin` (separate from the JSON `/admin` endpoints listed below — same prefix, the JSON router is matched first).
**Errors**: all error responses are `{"detail": "<message>"}` with the HTTP status code as listed. 401/403/404/400 are common across endpoints; only endpoint-specific cases are noted.

## Conventions

| Symbol | Meaning |
|---|---|
| 🔓 | Public — no auth |
| 🔑 | Bearer JWT (any verified user) |
| 🛒 | Bearer JWT, customer role |
| 🛵 | Bearer JWT, courier role |
| 🛡️ | HTTP Basic, admin |

---

## Root

### `GET /` 🔓
Returns: `{"message": "Welcome to the API"}`

### `GET /health` 🔓
Returns: `{"status": "ok"}`

---

## /auth

OTP-based phone login. SMS delivery is provider-pluggable; in DEBUG mode the OTP is also retrievable via `GET /auth/dev/otp` for tests.

### `POST /auth/send-otp` 🔓
Generates a 6-digit OTP, persists it on the user (creating one if the phone is new), and dispatches it via SMS. Per-phone rate limit: `RATE_LIMIT_OTP_MAX` requests per `RATE_LIMIT_OTP_WINDOW_SECONDS`.

**Body** `application/json`:
```json
{ "phone_number": "+966500000001" }
```
Phone must match `^(\+966|0)?[5][0-9]{8}$`; the `+966`/leading `0` is stripped server-side.

**Response 200**: `{ "message": "OTP sent successfully" }`
**Errors**: 429 (rate limited).

### `POST /auth/verify-otp` 🔓
Consumes the pending OTP. If the user is verified, returns a token pair. If the user is an unverified Customer, returns a temporary access token and `needs_profile=true` so the client can call `/auth/complete-profile`. Unverified Couriers cannot log in (admin must approve first).

**Body**:
```json
{
  "phone_number": "+966500000001",
  "otp": "123456",
  "device_id": "optional-device-uuid"
}
```

**Response 200** (verified user):
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "needs_profile": false,
  "user": {
    "id": 1, "phone_number": "...", "email": "...", "name": "...",
    "date_of_birth": "1990-01-01", "is_verified": true, "role": "Customer"
  },
  "profile": { "timezone": "Asia/Riyadh" }
}
```
For couriers, `profile` includes `national_id`, `passport_id`, `city_id`, `iban`, `vehicle`, `license`, `rate`, `is_approved`, `is_available`.

**Response 200** (unverified customer): `needs_profile: true`, `refresh_token: ""`, `access_token` is a 30-min temp JWT.

**Errors**: 400 (no OTP, expired, invalid, or unverified courier).

### `POST /auth/complete-profile` 🔓
Finalizes a new customer profile after OTP verification. Creates a `CustomerProfile` and a zero-balance `Wallet`, marks the user verified, and triggers a welcome email.

**Body** (`application/json`, all required except `timezone`):
```json
{
  "phone_number": "+966500000001",
  "name": "Alice",
  "email": "alice@example.com",
  "date_of_birth": "1990-01-01",
  "timezone": "Asia/Riyadh",
  "role": "Customer"
}
```

**Response 200**: `Token` (access + refresh, `needs_profile: false`).
**Errors**: 400 (missing field, bad date, user not found, already verified, email taken).

### `POST /auth/refresh` 🔓
Rotates refresh tokens — the old token is revoked, a new pair is issued.

**Body**: `{ "refresh_token": "..." }`
**Response 200**: `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }`
**Errors**: 401 (invalid/revoked/expired), 404 (user removed).

### `POST /auth/logout` 🔓
Revokes the supplied refresh token and disconnects the user from all WebSocket rooms.

**Body**: `{ "refresh_token": "..." }`
**Response 200**: `{ "message": "Successfully logged out" }`

### `GET /auth/me` 🔑
**Response 200**: `{ id, phone_number, email, name, date_of_birth, is_verified, role, timezone }`

### `PUT /auth/me` 🔑
Updates name, email, date of birth, and (optionally) timezone. Validates Arabic/Latin name (≥2 chars), email format + uniqueness, age ≥16.

**Body**: `UpdateUserProfile` — `{ name?, email?, date_of_birth?, national_id?, passport_id?, timezone? }`
**Response 200**: same shape as `GET /auth/me`.
**Errors**: 400 with `detail` as a `{field: message_arabic}` dict.

### `PUT /auth/timezone` 🔑
**Body**: `{ "timezone": "Asia/Riyadh" }`
**Response 200**: `{ "message": "...", "timezone": "Asia/Riyadh" }`

### `PUT /auth/push-token` 🔑
Stores an FCM/APNs token on the user's `CustomerProfile` or `CourierProfile`.

**Body**: `{ "push_token": "fcm-or-apns-token" }`
**Response 200**: `{ "message": "Push token updated" }`

### `GET /auth/dev/otp?phone_number=...` 🔓 (DEBUG only)
Returns the pending OTP for a phone number. Disabled when `DEBUG=false`. Used by integration tests.
**Response 200**: `{ "phone_number": "...", "otp": "123456" }` — **404 in production**.

---

## /orders

### `POST /orders/` 🔑
Creates an order with up to 3 image attachments. Auto-creates a `Conversation` for the order and broadcasts a `new_order` event to `couriers_city_<city_id>`.

**Body** `multipart/form-data`:
| Field | Type | Required | Notes |
|---|---|---|---|
| `description` | str | no | optional gift description, also posted as the first chat message |
| `city_id` | int | yes | must reference an existing city |
| `delivery_date` | datetime | yes | ISO 8601 |
| `image1`, `image2`, `image3` | file | no | each ≤15MB; JPEG/PNG/GIF/WebP/SVG |

**Response 200**: `OrderResponse` (see schema below).
**Errors**: 400 (invalid city, image too large, bad mime type), 500 (image upload failed — order is rolled back).

### `GET /orders/?skip=0&limit=50` 🔑
Lists the caller's own orders, newest first.
**Response 200**: `OrderResponse[]` (each includes nested invoice if present).

### `GET /orders/{order_id}` 🔑
Returns a single order. Caller must be the creator or the assigned courier.
**Response 200**: `OrderResponse`. **Errors**: 404, 403.

### `PUT /orders/{order_id}/cancel` 🔑
**Body**: `{ "reason": "string" }`
Only the creator can cancel. Disallowed if status is `CANCELLED`/`DONE`, or if the invoice is already `PAID`.
**Response 200**: `OrderResponse`.

### `PUT /orders/{order_id}/assign` 🛡️ (admin)
Assign an unassigned order to a specific courier.
**Body**: `{ "assigned_to_user_id": 42 }`
**Response 200**: `OrderResponse` (status becomes `RECEIVED_BY_COURIER`).
**Errors**: 400 (not a courier, terminal status), 404.

### `GET /orders/courier/available?skip=&limit=` 🛵
Lists `NEW`/unassigned orders in the courier's city. Requires approved profile.
**Response 200**: `OrderResponse[]`.

### `PUT /orders/{order_id}/accept` 🛵
Approved + available courier claims an unassigned order in their city. Posts an Arabic welcome message into the conversation and notifies the customer that chat is available.
**Response 200**: `OrderResponse`.
**Errors**: 400 (not `NEW`, wrong city), 403 (not approved/available), 404.

### `POST /orders/{order_id}/confirm-delivery` 🛒
Customer marks the order as delivered, unlocking `complete-order` for the courier.
**Response 200**: `{ "message": "Delivery confirmed. The courier can now mark the order as done." }`

### `GET /orders/courier/active?skip=&limit=` 🛵
Orders assigned to the courier that are not `CANCELLED`/`DONE`.
**Response 200**: `OrderResponse[]`.

### `GET /orders/courier/all?skip=&limit=` 🛵
Every order ever assigned to the courier.

### `GET /orders/courier/stats` 🛵
**Response 200**: `{ "active_orders_count": int, "todays_earnings": int_in_halalas }`

### `PUT /orders/{order_id}/complete` 🛵
Marks the order `DONE` and credits the courier's wallet with `invoice.courier_fee`. Requires the customer to have called `confirm-delivery` first and the invoice to be `PAID`.
**Response 200**: `OrderResponse`. **Errors**: 400 (no confirm, invoice not paid), 403, 404, 500.

### `PUT /orders/{order_id}/status?status=...` 🛵
Updates the assigned order's status to one of `received by courier`, `in_progress`, `ready_for_delivery`, `out_for_delivery`.
**Response 200**: `OrderResponse`.

### `OrderResponse` shape
```json
{
  "id": 1,
  "order_id": "ORDR-100001",
  "created_by_user_id": 1,
  "assigned_to_user_id": null,
  "description": "...",
  "creation_date": "2026-04-19T12:00:00",
  "delivery_date": "2026-04-21T18:00:00",
  "status": "new",
  "comments": null,
  "updated_at": "2026-04-19T12:00:00",
  "city_id": 1,
  "invoice": null
}
```

---

## /invoices

### `POST /invoices/` 🛡️
Admin creates an invoice for an existing order.
**Body** (`CreateInvoice`):
```json
{
  "order_id": 1,
  "full_amount": 120.00,
  "service_fee": 10.00,
  "order_only_price": 90.00,
  "courier_fee": 20.00,
  "description": "...",
  "comment": null,
  "due_date": null,
  "tax_amount": 0.0,
  "discount_amount": 0.0
}
```
Amounts are floats with at most 3 decimals; non-negative.
**Response 200**: `InvoiceResponse`. **Errors**: 400 (order missing, invoice already exists).

### `POST /invoices/courier/create` 🛵
Same body as above; only the courier assigned to the order can create.
**Response 200**: `InvoiceResponse`.

### `PUT /invoices/courier/update/{invoice_id}` 🛵
Replaces all editable invoice fields. Same body as `CreateInvoice`. Posts an Arabic chat update.
**Response 200**: `InvoiceResponse`.

### `GET /invoices/{invoice_id}` 🔓
Look up by invoice code (`INV-000001`). Public.
**Response 200**: `InvoiceResponse`. **404** if missing.

### `GET /invoices/id/{invoice_db_id}` 🔑
Look up by primary key; only accessible by the order's creator.
**Response 200**: `InvoiceResponse`.

### `GET /invoices/order/{order_id}` 🔑
Get the invoice attached to one of the caller's orders.
**Response 200**: `InvoiceResponse`.

### `GET /invoices/order/{order_id}/pdf` 🔑
Generates a PDF (ReportLab) and streams it back; the temp file is deleted ~10 minutes later.
**Response 200**: `application/pdf`, `Content-Disposition: attachment; filename=INV-XXXXXX.pdf`.

### `GET /invoices/id/{invoice_db_id}/pdf` 🔑
Same as above, addressed by primary key.

### `POST /invoices/verify-coupon` 🔑
Calculates a discount preview without applying it.
**Body** `application/x-www-form-urlencoded`: `coupon_code=SAVE10&invoice_id=42`
**Response 200**: `{ "coupon_id": int, "discount_amount": int, "final_amount": int, "description": str }`
**Errors**: 400 (invalid/expired/exceeded usage/min order not met, invoice already paid).

### `InvoiceResponse` shape
```json
{
  "id": 1,
  "invoice_id": "INV-000001",
  "order_id": 1,
  "full_amount": 12000,
  "service_fee": 1000,
  "order_only_price": 9000,
  "courier_fee": 2000,
  "status": "new",
  "description": "...",
  "comment": null,
  "sent_to_user_via_email": false,
  "sent_at": null,
  "due_date": null,
  "tax_amount": 0,
  "discount_amount": 0,
  "created_at": "...",
  "updated_at": "..."
}
```

---

## /payments

### `POST /payments/` 🔑
Initiates a Paylink-brokered payment for `CREDIT_CARD`, `APPLE_PAY`, or `MADA`. Returns a `Payment` row with `transaction_id` set; the client should also read the `payment_url` field returned by Paylink (echoed in the response body) and open it. Wallet payments are rejected here — use `/payments/pay-with-wallet/{invoice_id}` instead.

**Body** (`CreatePayment`):
```json
{
  "invoice_id": 1,
  "user_id": 1,
  "amount": 12000,
  "payment_method": "credit_card",
  "transaction_id": null,
  "payment_details": null
}
```
`user_id` must equal the caller; `amount` is in halalas.

**Response 200**: `PaymentResponse`. **Errors**: 400 (wrong user, wallet method), 403 (invoice not owned), 404, 502 (gateway error), 503 (gateway not configured).

### `POST /payments/paylink-callback` 🔓
Webhook from Paylink. Marks the matching `Payment` `COMPLETED` or `FAILED`. If the payment ties to an invoice and the cumulative completed amount ≥ `invoice.full_amount`, marks the invoice + order `PAID` and emits chat/order WS events. If the payment has no `invoice_id` (wallet top-up), credits the wallet by `payment.amount`.

**Body**: arbitrary Paylink JSON; reads `transactionNo`/`orderNumber` and `orderStatus`/`status`.
**Response 200**: `{ "message": "Callback processed" }` or `{ "message": "Already processed" }`.

### `GET /payments/{payment_id}` 🔑
Returns the payment if it belongs to the caller. **Response 200**: `PaymentResponse`.

### `GET /payments/invoice/{invoice_id}?skip=&limit=` 🔑
Lists payments against one of the caller's invoices.
**Response 200**: `PaymentResponse[]`.

### `GET /payments/my-payments?skip=&limit=` 🔑
All non-deleted payments by the caller, newest first.

### `POST /payments/pay-with-wallet/{invoice_id}?coupon_code=...` 🔑
Settles an invoice from wallet balance. Optional promo code is validated (active, not expired, limit not reached, min order met, not previously used by this user). Records the discount, decrements the wallet, marks invoice + order `PAID`, posts a chat message, queues the email-receipt task.

**Response 200**:
```json
{
  "message": "Payment successful. Discount: 5.00 SAR",
  "payment_id": 7,
  "remaining_balance": 38000,
  "final_amount": 11500,
  "discount_amount": 500
}
```
**Errors**: 400 (insufficient balance, coupon issue, already paid), 403, 404, 500.

### `PaymentResponse` shape
```json
{
  "id": 7,
  "invoice_id": 1,
  "user_id": 1,
  "amount": 12000,
  "payment_method": "wallet",
  "status": "completed",
  "transaction_id": null,
  "payment_date": "...",
  "payment_details": null,
  "wallet_balance_before": 50000,
  "created_at": "...",
  "updated_at": "..."
}
```

---

## /wallets

### `GET /wallets/my-wallet` 🔑
**Response 200**: `WalletResponse` — `{ id, user_id, balance, created_at, updated_at }`. `balance` is halalas.

### `POST /wallets/initiate-charge` 🔑
Wallet top-up via Paylink. Creates a PENDING `Payment` (no invoice) and asks Paylink for an `orderNumber=<payment.id>`. The callback later credits the wallet.

**Body**: `{ "amount_sar": 100 }` — minimum 10 SAR.
**Response 200**: `{ "payment_url": "...", "payment_id": 12, "amount_sar": 100, "status": "pending" }`
**Errors**: 400 (<10 SAR), 404 (no wallet), 502/503 (gateway).

### `POST /wallets/request-deposit` 🛵
Courier requests a payout from their wallet balance. Creates a `DepositRequest` for admin review; balance is **not** deducted yet.

**Body** (`RequestWalletDeposit`): `{ "amount": 50.00 }` — SAR with exactly 2 decimals, min 10.
**Response 200**:
```json
{
  "message": "تم إرسال طلب شحن المحفظة. سيتم مراجعة الطلب من قبل الإدارة.",
  "requested_amount": 50.0,
  "current_balance": 380.0,
  "request_id": 4
}
```

---

## /promocodes

### `POST /promocodes/apply` 🔓
Calculates the discount a code would produce against a given order total (halalas). Does not consume the code.

**Body**: `{ "code": "SAVE10", "order_total": 10000 }`
**Response 200**:
```json
{
  "promocode_id": 1, "code": "SAVE10", "name": "10% off",
  "percentage": 10, "max_value": 2000,
  "discount_amount": 1000, "final_amount": 9000
}
```
**Errors**: 404 (invalid/expired), 400 (min order, usage limit).

### `GET /promocodes/active/list?skip=&limit=` 🔓
Lists currently-valid promocodes (no usage counts in payload).
**Response 200**: array of `{ id, name, code, description, percentage, max_value, minimum_order_value, applicable_to, valid_until }`.

---

## /chat

REST companion to the `/ws` channel — useful for history, file uploads, and out-of-band conversation management.

### `POST /chat/conversations` 🔑
Creates (or returns existing) conversation between the caller and another user, where one is `Customer` and the other is `Courier`.
**Body**: `{ "other_user_id": 42 }`
**Response 200**: `ConversationResponse`.

### `GET /chat/conversations/{conversation_id}/messages?skip=&limit=` 🔑
Paginated message history (chronological — oldest first after pagination).
**Response 200**: `MessageResponse[]`.

### `POST /chat/conversations/{conversation_id}/messages` 🔑
Sends a message with optional media upload. `multipart/form-data`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `content` | str | yes | message body |
| `message_type` | str | no | `text` (default), `invoice`, `image`, `video`, `system` |
| `media_type` | str | no | `image` or `video` |
| `invoice_*` (description, gift_price, service_fee, delivery_fee, total) | str/int | required when `message_type=invoice` | |
| `media_file` | file | required for `image`/`video` | image ≤15MB, video ≤100MB |

**Response 200**: `MessageResponse`.

### `GET /chat/conversations` 🔑
All conversations the caller is part of.
**Response 200**: `ConversationResponse[]`.

### `GET /chat/conversations/by-order/{order_id}` 🔑
The conversation attached to a given order.

### `PUT /chat/conversations/{conversation_id}?status=active|inactive` 🔑
Toggle conversation status.
**Response 200**: `ConversationResponse`.

### `GET /chat/messages/{message_id}/media` 🔑
**Response 200**: `{ "media_url": "...", "media_type": "image|video" }`.

### `GET /chat/orders/{order_id}/images/{image_number}` 🔑
`image_number ∈ {1,2,3}`. Order creator only.
**Response 200**: `{ "image_url": "..." }`.

### `MessageResponse` shape
```json
{
  "id": 100,
  "conversation_id": 1,
  "sender_id": 1,
  "content": "...",
  "sent_at": "...",
  "message_type": "text",
  "media_type": null,
  "invoice_description": null,
  "invoice_gift_price": null,
  "invoice_service_fee": null,
  "invoice_delivery_fee": null,
  "invoice_total": null,
  "media_url": null
}
```

---

## /cities

### `GET /cities/` 🔓
Active cities only.
**Response 200**: `CityResponse[]` — `{ id, name, icon, active }`.

---

## /couriers

### `PUT /couriers/availability` 🛵
Toggles `is_available` on the courier's profile (requires approved).
**Response 200**: `{ "is_available": bool }`.

### `GET /couriers/available/{city_id}?skip=&limit=` 🔓
Lists approved + available couriers in a city.
**Response 200**: `[{ "user_id", "name", "vehicle", "rate" }]` (`rate` is the average rating as float).

---

## /events

Important reminders saved by a customer (birthdays, anniversaries) — used by the gifting reminder flow.

### `POST /events/` 🛒
**Body**: `{ "title": str, "event_date": datetime, "recurring": bool? }` — title ≤200 chars, event date in the future.
**Response 200**: `ImportantEventResponse`.

### `GET /events/?skip=&limit=` 🛒
Caller's events ordered by `event_date`.
**Response 200**: `ImportantEventResponse[]`.

### `GET /events/{event_id}` 🛒
**Response 200**: `ImportantEventResponse`. **404** if not owned.

### `PUT /events/{event_id}` 🛒
**Body** (`UpdateImportantEventRequest`): any subset of `title`, `event_date`, `recurring`.
**Response 200**: `ImportantEventResponse`.

### `DELETE /events/{event_id}` 🛒
**Response 200**: `{ "message": "Event deleted successfully" }`.

### `ImportantEventResponse` shape
```json
{
  "id": 1, "user_id": 1, "title": "Mom's birthday",
  "event_date": "2026-09-12T00:00:00", "recurring": true,
  "created_at": "...", "updated_at": "..."
}
```

---

## /admin (JSON endpoints)

All endpoints below require **HTTP Basic** auth. The credentials are checked against the `Admin` table (bcrypt). The interactive SQLAdmin dashboard is also mounted under `/admin/*` for browser use.

### `GET /admin/me` 🛡️
**Response 200**: `{ id, username, name, email }`.

### `POST /admin/couriers/{user_id}/approve` 🛡️
Sets `is_approved=true` on the courier's profile.
**Response 200**: `{ "message": "Courier approved", "user_id": int }`.

### `POST /admin/couriers/{user_id}/reject` 🛡️
Sets `is_approved=false`.
**Response 200**: `{ "message": "Courier rejected", "user_id": int }`.

### `POST /admin/wallets/{user_id}/charge` 🛡️
Credits a user's wallet.
**Body**: `{ "amount": 10000 }` — positive integer halalas.
**Response 200**: `{ "message": "Charged 10000 halaym to user 5", "new_balance": 60000 }`.

### `POST /admin/cleanup/soft-deleted?retention_days=90` 🛡️
Hard-deletes soft-deleted rows (across orders, invoices, payments, conversations, messages, courier_reviews, promocodes) older than `retention_days`.
**Response 200**: `{ "deleted": { "orders": 0, "invoices": 0, ... }, "cutoff_date": "..." }`.

---

## WebSocket

### `WS /ws?token=<access_token>`
JWT in the query string (refresh tokens are rejected). On connect:
- the user joins room `user_<id>`
- approved + available couriers also join `couriers_city_<city_id>`

#### Client → server (JSON frames)

| Action | Payload | Effect |
|---|---|---|
| `join_room` | `{ "action": "join_room", "room": "chat_42" }` | Joins the named room. Echo: `{ "action": "joined_room", "room": "chat_42" }` |
| `leave_room` | `{ "action": "leave_room", "room": "chat_42" }` | Echo: `{ "action": "left_room", "room": "chat_42" }` |
| `leave_all_rooms` | `{ "action": "leave_all_rooms" }` | Disconnects the user. Echo: `{ "action": "left_all_rooms" }` |
| `send_message` | `{ "action": "send_message", "room": "chat_<conversation_id>", "content": "...", "message_type": "text", "invoice_*": ... }` | Persists a `Message` and broadcasts to the room as `event: chat_message`. Caller must be a participant of the conversation. `content` is truncated to 1000 chars; control characters stripped. |

#### Server → client events

| Event | Triggered by | Payload `data` |
|---|---|---|
| `new_order` | `POST /orders/` | `{ order_id, id, description, city_id, delivery_date, created_by_user_id }` to `couriers_city_<city_id>` |
| `chat_available` | `PUT /orders/{id}/accept` | `{ order_id, conversation_id, courier_id, courier_name }` to the customer |
| `chat_message` | WS `send_message`, server-side message inserts | `{ id, conversation_id, sender_id, content, message_type, sent_at, ... }` |
| `order_status_change` | order state transitions | `{ order_id, status }` |
| `invoice_created` | `POST /invoices/courier/create` etc. | `{ invoice_id, order_id }` |

---

## Reference: enums

**OrderStatus**: `new`, `received by courier`, `invoice created`, `payment pending`, `payment authorized`, `awaiting pickup`, `paid`, `in progress to do`, `cancelled`, `done`, `in progress to deliver`, `out for delivery`, `awaiting confirmation`.
**InvoiceStatus**: `new`, `draft`, `pending approval`, `approved`, `paid`, `cancelled`, `refunded`, `other`.
**PaymentMethod**: `wallet`, `credit_card`, `apple_pay`, `mada`.
**PaymentStatus**: `pending`, `completed`, `failed`, `refunded`.
**UserRole**: `Customer`, `Courier`.
**ConversationStatus**: `active`, `inactive`, `closed`.
**DepositRequestStatus**: `pending`, `approved`, `rejected`.
