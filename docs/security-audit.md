# Security Audit
> Scope: `src/` — routers, models, schemas, middleware, utils.  
> Reviewed: 2026-04-24. All findings from the previous audit have been resolved.

---

## CRITICAL

_None identified._

---

## HIGH

_None identified._

---

## MEDIUM

_None identified._

---

## LOW

### L-01 — Conversations can be created without an associated order
**File:** `src/routers/chat.py` — `create_or_get_conversation`  
**Issue:** Any authenticated customer can open a conversation with any courier directly, without an existing assigned order linking the two parties. The intended flow is order → assignment → conversation. Free-form contact creates couriers being solicited outside the platform's payment and dispute mechanisms.  
**Recommendation:** Enforce that a new conversation must reference a `RECEIVED_BY_COURIER` or later order where the customer is the creator and the courier is the assignee. Alternatively, document that direct conversations are an intentional feature (e.g., for price negotiation before order placement).  
**Severity rationale:** No financial loss or data exposure is possible; it is a business logic concern.

---

## Resolved Findings (previous audit)

| ID | Description | Resolution |
|----|-------------|------------|
| H-01 | Wallet balance race condition in `pay_with_wallet` | Replaced two-step check with atomic `UPDATE … WHERE balance >= amount RETURNING balance` |
| M-01 | Paylink webhook signature silently skipped when secret unset | Returns `503` in production when `PAYLINK_WEBHOOK_SECRET` is not set |
| M-02 | WebSocket `send_message` had no per-user rate limit | Added sliding-window rate limiter keyed by `user.id`, limit from `WS_MSG_RATE_LIMIT_PER_MINUTE` |
| M-03 | Invoice amounts had no upper bound | Both create and update endpoints cap `full_amount` against `INVOICE_MAX_AMOUNT_SAR × 100` halalas |
| M-04 | Order `delivery_date` not validated against the present | Raises `400` when `delivery_date ≤ now` |
| M-05 | Courier city check not atomic at order acceptance | Added `Order.city_id == profile.city_id` to the atomic UPDATE WHERE clause |
| M-06 | Promocode `usage_count` not decremented on cancellation | `cancel_order` decrements `usage_count` and deletes the `PromocodeUsage` row when an invoice with a promo is cancelled |
| M-07 | WebSocket `send_message` stored arbitrary `message_type` | Whitelist `{"text", "invoice", "image", "video"}` enforced; unknown values fall back to `"text"` |
| L-01 | OTP not invalidated after N failed attempts | In-memory failure counter (`_otp_failures`) invalidates OTP and locks attempts after 3 failures |
| L-02 | Temporary token expiry hardcoded | Reads from `settings.temp_token_expire_minutes` (`TEMP_TOKEN_EXPIRE_MINUTES` env var) |
| L-03 | Admin could approve couriers with incomplete profiles | `approve_courier` checks `national_id`/`passport_id`, `iban`, and `city_id` before setting `is_approved` |
| L-04 (previous) | Promo description not HTML-escaped in list endpoint | `html.escape()` applied to `name` and `description` in `get_active_promocodes` |
| L-05 (previous) | Admin auth cache keyed on raw `Authorization` header | Cache key is now `sha256(username + ":" + sha256(password))` to bind entry to specific credentials |
