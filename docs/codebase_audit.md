# Giftly Backend — Codebase Audit

> Updated: 2026-04-21
> Scope: all files under `src/`
> Reflects state after commit 18a40b2 + current uncommitted changes (email/paylink/sms refactor).
> Sorted by severity within each section (Critical → High → Medium → Low)

---

## 1. Security & Vulnerability Flaws

### [CRITICAL] Paylink webhook has no server-side verification
**File:** `src/routers/payments.py:189–284`

The `/paylink-callback` endpoint accepts any POST body with a matching `transactionNo`. Paylink's official docs confirm there is no HMAC signature header, but the endpoint is fully unauthenticated with no rate limiting. An attacker who discovers the callback URL can:
- Enumerate pending payments by brute-forcing `transactionNo` values.
- Trigger repeated callback processing attempts.

**Fix:** Add IP allowlisting for Paylink's server IP ranges (published in their docs). At minimum, add rate limiting (`slowapi`) to this endpoint.

---

### [HIGH] In-memory rate limiting does not work on multi-worker deployments
**File:** `src/routers/auth.py:34–63`

```python
_phone_timestamps: dict[str, list[float]] = defaultdict(list)
_verify_timestamps: dict[str, list[float]] = defaultdict(list)
```

These are process-local dicts. With 4 uvicorn workers, each worker has its own copy, making the effective limit `4 × 3 = 12` OTP requests per 10 minutes — not 3.

**Fix:** Replace with a Redis-backed counter using `INCR` + `EXPIRE`, or use `slowapi` with a Redis storage backend.

---

### [HIGH] `complete-profile` bypasses Pydantic — no input validation
**File:** `src/routers/auth.py:348–413`

```python
async def complete_profile(profile_data: dict, ...):
    name = profile_data.get("name")
    email = profile_data.get("email")
```

No type coercion, no length limits, no email format validation, no age check on `date_of_birth`. Attackers can send arbitrary data.

**Fix:** Create a `CompleteProfileRequest` Pydantic model with validators matching `UpdateUserProfile`.

---

### [HIGH] `complete-profile` has no authentication — any caller can set another user's profile
**File:** `src/routers/auth.py:358–413`

The endpoint only queries by `phone_number` from the request body — no JWT check. Any caller who knows a phone number can complete another user's profile while their account is in `is_verified=False` state.

**Fix:** Require the temp token issued by `verify_otp` via a `Depends` guard.

---

### [HIGH] Order acceptance has no concurrency guard — two couriers can accept the same order
**File:** `src/routers/orders.py:442–463`

Two couriers sending `PUT /orders/{id}/accept` simultaneously both pass the `status == NEW` check before either commits, leading to race condition where last commit wins silently.

**Fix:**
```python
result = await db.execute(
    select(Order)
    .where(Order.order_id == order_id, Order.status == OrderStatus.NEW)
    .with_for_update(skip_locked=True)
)
```

---

### [MEDIUM] `order.comments` stores user PII in plaintext
**File:** `src/routers/orders.py:327, 371, 466, 712`

```python
order.comments = f"{cancel_data.reason} by ID:{current_user.id} and name:{current_user.name}"
```

User names and IDs embedded in a free-text `comments` field visible in admin views and API responses. May conflict with PDPL requirements.

**Fix:** Store structured audit data in a separate `OrderEvent` table with `user_id` FK.

---

### [LOW] `push_token` endpoint accepts unbounded-length string
**File:** `src/routers/auth.py:459`

No max length enforced. FCM/APNs tokens are ~163 chars. Attackers can store megabytes in this column.

**Fix:** `if len(push_token) > 300: raise HTTPException(400, "Invalid token")`

---

### [LOW] `dev/otp` endpoint registered unconditionally
**File:** `src/routers/auth.py:503–512`

The route is registered regardless of `settings.debug`. A misconfigured `DEBUG=true` in production immediately leaks all OTPs.

**Fix:**
```python
if settings.debug:
    router.add_api_route("/dev/otp", dev_get_otp, methods=["GET"])
```

---

## 2. Performance Issues

### [HIGH] `get_current_user` eager-loads both profiles on every authenticated request
**File:** `src/utils/auth/auth.py:130–133`

```python
.options(selectinload(User.courier_profile), selectinload(User.customer_profile))
```

Every authenticated endpoint loads both profiles even when only one (or none) is needed. Adds 1–2 extra SELECT queries per request.

**Fix:** Load lazily or inject role from JWT to skip unused profile selects.

---

### [HIGH] Admin middleware runs a DB query for every `/admin` request including static assets
**File:** `src/main.py:133–172`

The `admin_auth_middleware` opens an `AsyncSessionLocal()` and queries the `Admin` table on **every** request matching `/admin/*` — including CSS, JS, and font files served by SQLAdmin. Tens of DB queries per page load.

**Fix:** Cache successful auth lookups with a short TTL (e.g., 60s) keyed by bcrypt-verified credentials.

---

### [MEDIUM] `_check_phone_rate_limit` rebuilds a new list on every call
**File:** `src/routers/auth.py:41–43`

```python
_phone_timestamps[phone] = [t for t in _phone_timestamps[phone] if now - t < _PHONE_WINDOW]
```

Allocates a new list on every call. Under abuse (many requests), this grows large before eviction.

**Fix:** Use `collections.deque` with `maxlen` and `popleft()` to trim in O(1).

---

### [MEDIUM] Rate-limit dict grows unboundedly in memory
**File:** `src/routers/auth.py:34–35`

`_phone_timestamps` and `_verify_timestamps` keys are never purged. After N distinct phone numbers, N keys remain forever (with empty lists). Leaks memory under sustained traffic.

**Fix:** Use a `cachetools.TTLCache` or move to Redis.

---

### [LOW] `balance_before` in `complete_order` derived after atomic update — wrong under concurrency
**File:** `src/routers/orders.py:694–707`

```python
await db.execute(update(Wallet).values(balance=Wallet.balance + courier_fee, ...))
result = await db.execute(select(Wallet.balance).where(...))
balance_after = result.scalar_one()
balance_before = balance_after - courier_fee   # derived, not actual pre-update value
```

If another transaction modified the wallet between the UPDATE and SELECT, `balance_before` is wrong, corrupting the `CourierBalanceAddition` audit trail.

**Fix:** Capture `balance_before` with `SELECT FOR UPDATE` before the update.

---

## 3. Logic Issues

### [HIGH] `cancel_order` does not cancel the active payment — webhook can override cancellation
**File:** `src/routers/orders.py:316–333`

When a customer cancels an order with a `PAYMENT_PENDING` invoice, the order is cancelled but the associated `Payment` record stays `PENDING`. If the customer completes payment via the Paylink URL after cancellation, the webhook marks the invoice `PAID` and the order `PAID` — silently overriding the cancellation.

**Fix:** On order cancellation, set any `PENDING` payment records to `FAILED` and mark the invoice `CANCELLED`.

---

### [HIGH] `CourierBalanceAddition` silently skipped when payment status comparison uses wrong type
**File:** `src/routers/orders.py:716–732`

```python
result = await db.execute(select(Payment).where(..., Payment.status == "completed"))
```

`Payment.status` is `PaymentStatus.COMPLETED` (enum), not the string `"completed"`. The comparison always fails silently — no audit record is created when the courier receives payment.

**Fix:** `Payment.status == PaymentStatus.COMPLETED`

---

### [MEDIUM] OTP rate limit applied to un-normalized phone — different formats bypass limit
**File:** `src/routers/auth.py:107`

`_check_phone_verify_rate_limit(otp_data.phone_number)` uses the raw input. `+9665XXXXXXXX`, `05XXXXXXXX`, and `5XXXXXXXX` all resolve to the same user but each gets its own rate-limit slot (3 × 3 = 9 effective attempts).

**Fix:** Normalize the phone before the rate-limit check.

---

### [MEDIUM] `GET /invoices/{invoice_id}` path collides with `/invoices/order/{order_id}`
**File:** `src/routers/invoices.py:239, 511`

FastAPI matches `GET /invoices/order/5` as `{invoice_id} = "order"` instead of routing to the `/order/{order_id}` endpoint.

**Fix:** Move fixed-segment routes (`/order/...`, `/courier/...`) above the wildcard `/{invoice_id}` route.

---

### [MEDIUM] `assign_order` (admin) does not verify courier is in the same city
**File:** `src/routers/orders.py:336–379`

`accept_order` checks `order.city_id != profile.city_id`, but `assign_order` does not. An admin can assign a Riyadh courier to a Jeddah order.

**Fix:** Add city match check in `assign_order`.

---

### [LOW] `update_invoice_by_courier` uses `datetime.utcnow()` — deprecated in Python 3.12+
**File:** `src/routers/invoices.py:214`

```python
invoice.updated_at = datetime.utcnow()
```

**Fix:** `invoice.updated_at = datetime.now(timezone.utc)`

---

### [LOW] `is_verified` embedded in access token can become stale
**File:** `src/utils/auth/auth.py:70`

If an admin revokes verification after a user obtains a valid token, the token still claims `is_verified=True` until it expires (up to 15 min).

**Fix:** Document this window as acceptable, or re-check `is_verified` from DB in `get_current_user` for sensitive operations.

---

## 4. Improvement Suggestions

### [HIGH] Replace raw-dict endpoint signatures with Pydantic models
**Files:** `src/routers/auth.py:417, 452`, `src/routers/admin.py`

Three endpoints accept `data: dict` — no OpenAPI docs, no validation, no IDE completion. Create typed Pydantic models.

---

### [HIGH] Add Paylink IP allowlisting or request signing to the callback endpoint
**File:** `src/routers/payments.py:189`

There is no way to verify the callback genuinely came from Paylink. Fetch Paylink's published server IPs and validate `request.client.host` against them. This is the only verification method Paylink supports.

---

### [MEDIUM] `CourierProfile.max_concurrent_orders` is never enforced
**File:** `src/models/courier/courier_profile.py`, `src/routers/orders.py`

The field exists but `accept_order` never checks it. A courier can accept unlimited orders.

**Fix:** In `accept_order`, count active orders and compare against `profile.max_concurrent_orders`.

---

### [MEDIUM] Paginate courier broadcast on order creation
**File:** `src/routers/orders.py:206–223`

Broadcasting to `couriers_city_{city_id}` is O(n) where n = connected couriers. 500 couriers = 500 synchronous WebSocket sends in the request handler, adding latency proportional to room size.

**Fix:** Move the broadcast to a background task or use an async broadcast queue.

---

### [MEDIUM] Pydantic V1-style validators throughout schemas — will break in Pydantic V3
**File:** `src/schemas/shared/__init__.py`, `src/schemas/admin/__init__.py`

```python
@validator("phone_number")  # V1 style
class Config: ...            # V1 style
```

These emit deprecation warnings now and will error when Pydantic V3 is released.

**Fix:** Migrate to `@field_validator` and `model_config = ConfigDict(...)`.

---

### [MEDIUM] Admin middleware bcrypt check on every `/admin` static asset
**File:** `src/main.py:133–172`

`bcrypt.checkpw()` is intentionally slow (~100ms). Checking it on every CSS/JS file load makes the admin panel very sluggish. Cache verified credentials in memory with a short TTL.

---

### [LOW] `/health` endpoint does not probe the database
**File:** `src/main.py:204–206`

Returns `{"status": "ok"}` even if the DB is down. Load balancers rely on this for liveness.

**Fix:**
```python
@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
```

---

### [LOW] Structured logging missing `order_id` / `invoice_id` context
**File:** `src/middleware/logging.py`

The request logger records `method`, `path`, `status_code`, `duration_ms`, `user_id` but not resource IDs. Adding them from path params would make log correlation much easier during incidents.

---

### [LOW] Soft-delete cleanup endpoint lacks a dry-run mode
**File:** `src/routers/admin.py`

The hard-delete cleanup permanently destroys records. A `?dry_run=true` param returning counts without deleting would make admin operations safer.

---

*End of audit — 27 open findings across 4 categories.*
