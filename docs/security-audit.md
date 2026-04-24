# Security Audit
> Scope: `src/` — routers, models, schemas, middleware, utils.  
> Generated: 2026-04-24.

---

## CRITICAL

_None identified._

---

## HIGH

### H-01 — Wallet balance race condition in `pay_with_wallet`
**File:** `src/routers/payments.py` — `pay_with_wallet`  
**Issue:** Balance sufficiency is checked in Python (`wallet.balance < payment_amount`), then decremented in a separate SQL statement. Two concurrent requests for the same wallet can both pass the Python check and both execute the decrement, resulting in a negative balance.  
**Fix:** Replace the two-step check-then-update with a single atomic conditional UPDATE:
```sql
UPDATE wallets SET balance = balance - :amount
WHERE user_id = :uid AND balance >= :amount
```
Check `rowcount == 0` and return 402 if zero rows were updated.

---

## MEDIUM

### M-01 — Paylink webhook signature silently skipped when secret is unset
**File:** `src/routers/payments.py` — `paylink_callback`  
**Issue:** HMAC verification only runs when `settings.paylink_webhook_secret` is non-empty. If a deployment omits the env var, the endpoint accepts every unsigned POST — an attacker can spoof payment completions and credit wallets or mark invoices paid for free.  
**Fix:** In production (`settings.debug == False`), enforce that `paylink_webhook_secret` is set. Raise a startup error or return 501 from the callback if it is missing.

### M-02 — WebSocket `send_message` has no per-user rate limit
**File:** `src/main.py` — WebSocket handler, `send_message` action  
**Issue:** An authenticated user can send WebSocket messages at unlimited frequency. The `ws_max_payload_bytes` guard only rejects oversized frames, not volume. This allows message-flooding that could affect other clients in the same room or strain the DB (each message is persisted).  
**Fix:** Track per-user message timestamps in memory (same pattern as `_check_callback_rate_limit`) and reject messages beyond a configurable threshold (e.g., 30/min).

### M-03 — Invoice amounts have no upper bound
**File:** `src/schemas/shared/__init__.py` — `CreateInvoice`, `src/routers/invoices.py`  
**Issue:** `full_amount`, `service_fee`, `courier_fee` accept any non-negative float. A malicious or mistaken courier could create an invoice for an arbitrarily large amount (e.g., 10,000,000 SAR). No server-side cap exists.  
**Fix:** Add a configurable `INVOICE_MAX_AMOUNT_SAR` setting and validate in the schema or router. A reasonable default is 50,000 SAR.

### M-04 — Order `delivery_date` not validated against the present
**File:** `src/routers/orders.py` — `create_order`  
**Issue:** `delivery_date` is accepted from the form with no check that it is in the future. Customers can create orders with past delivery dates, creating incorrect records and confusing couriers.  
**Fix:** Validate `delivery_date > datetime.now(timezone.utc)` in the router or in the `CreateOrderWithImages` schema.

### M-05 — Courier city check is not atomic at order acceptance
**File:** `src/routers/orders.py` — `accept_order`  
**Issue:** The check `order.city_id != profile.city_id` runs on data loaded before the atomic UPDATE. If an admin reassigns a courier to a different city between the read and the atomic write, the courier could accept an out-of-city order. The atomic UPDATE only guards against concurrent acceptance, not against a concurrent city change.  
**Fix:** Include `city_id = :courier_city_id` in the atomic UPDATE WHERE clause so the DB enforces it in one statement.

### M-06 — Promocode `usage_count` not decremented on order cancellation or refund
**File:** `src/routers/orders.py`, `src/routers/payments.py`  
**Issue:** When a customer cancels an order that was paid with a promo code, or when a payment is refunded, the `Promocode.usage_count` is not decremented and the `PromocodeUsage` row is not removed. This permanently locks out the user's one-use entitlement and inflates global usage counts, reducing the promo's remaining capacity unfairly.  
**Fix:** On order cancellation (when status transitions to `CANCELLED`) and on refund, reverse the `PromocodeUsage` row deletion and decrement `usage_count`.

### M-07 — WebSocket `send_message` stores arbitrary `message_type`
**File:** `src/main.py` — WebSocket handler, `send_message` action  
**Issue:** `message_type` is taken from the client payload with no whitelist: `data.get("message_type", "text")`. A client can persist messages with any string type (e.g., `"admin"`, `"system"`, `"invoice"`). Client applications that filter by type may expose unexpected messages.  
**Fix:** Validate `message_type` against the same allowed list used in the REST endpoint: `{"text", "invoice", "image", "video"}`.

---

## LOW

### L-01 — OTP not invalidated on failed verification attempt
**File:** `src/routers/auth.py` — `verify_otp`  
**Issue:** A wrong OTP does not clear or consume the stored OTP. The per-IP rate limit reduces brute-force risk, but if the attacker's IP changes (VPN) or the rate limit window resets, they can continue guessing. A 6-digit OTP with a 90-second window has 1-in-1,000,000 odds per guess.  
**Fix:** After `N` (e.g., 3) consecutive failed attempts for a phone number, invalidate the OTP and require a new one. Track the failure count on the User row or in Redis.

### L-02 — Temporary token expiry is hardcoded, not configurable
**File:** `src/routers/auth.py` — `verify_otp` (line creating the temp token)  
**Issue:** The temporary access token issued to new customers pending profile completion uses a hardcoded 30-minute lifetime. If the security policy changes, this requires a code change.  
**Fix:** Add `TEMP_TOKEN_EXPIRE_MINUTES` to Settings with a sensible default (e.g., 30).

### L-03 — Admin can approve couriers with incomplete profiles
**File:** `src/routers/admin.py` — `approve_courier`  
**Issue:** The approval endpoint sets `is_approved = True` without checking that required profile fields (`national_id` or `passport_id`, `iban`, `city_id`) are populated. An admin could accidentally approve an incomplete profile.  
**Fix:** Before setting `is_approved`, verify that at least one of `national_id`/`passport_id`, `iban`, and `city_id` are non-null.

### L-04 — Conversations can be created without an associated order
**File:** `src/routers/chat.py` — `create_or_get_conversation`  
**Issue:** Any customer can open a conversation with any courier directly, without an order being assigned. The intended flow is order → assignment → conversation. Free-form courier selection could lead to couriers being solicited outside the platform.  
**Fix:** Either enforce that a conversation requires a linked `order_id`, or document and accept this as a deliberate feature.

### L-05 — Promotional code description not HTML-escaped in list endpoint
**File:** `src/routers/promocodes.py` — `get_active_promocodes`  
**Issue:** Promo code `description` and `name` fields are returned as-is. If a malicious admin creates a promo code with HTML/script content, clients that render descriptions as HTML would be vulnerable to stored XSS.  
**Fix:** HTML-escape `description` and `name` in the response, or enforce plain-text in the `CreatePromocode` schema.

### L-06 — Admin auth cache does not distinguish between different admin users sharing a credential hash collision
**File:** `src/main.py` — `admin_auth_middleware`  
**Issue:** The cache key is `sha256(Authorization_header)`. Two admins with different usernames but identically formatted credentials that hash to the same key (theoretical SHA256 collision) would share a cache entry. Practically impossible but worth noting. A more robust key would include the username explicitly.  
**Fix:** Cache key: `sha256(f"{username}:{password}")` where username is extracted first — or simply use `f"{username}:{sha256(password)}"`.
