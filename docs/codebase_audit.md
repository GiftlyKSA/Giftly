# Giftly Backend — Codebase Audit

> Generated: 2026-04-20  
> Scope: all files under `src/`  
> Sorted by severity within each section (Critical → High → Medium → Low)

---

## 1. Security & Vulnerability Flaws

### [CRITICAL] Paylink webhook has no signature verification
**File:** `src/routers/payments.py:188–282`

The `/paylink-callback` endpoint accepts any POST body with a matching `transactionNo` and marks the corresponding payment as `COMPLETED`. There is no HMAC/signature check against the Paylink API key. An attacker who knows the callback URL (discoverable via a frontend JS bundle or network sniffer) can forge a request and mark any pending payment as paid without actually paying.

```python
# payments.py:188 — no auth, no signature check
@router.post("/paylink-callback")
async def paylink_callback(payload: dict, db: AsyncSession = Depends(get_db)):
    transaction_no = str(payload.get("transactionNo") or ...)
    # ← missing: validate X-Paylink-Signature or equivalent header
    if paylink_status in ("paid", "completed", "success"):
        payment.status = PaymentStatus.COMPLETED
```

**Fix:** Compute `HMAC-SHA256(secret_key, raw_body)` and compare it to the signature Paylink sends in the request header (check Paylink docs for exact header name). Reject the request with 403 if it does not match. Use `hmac.compare_digest` to avoid timing attacks.

---

### [CRITICAL] `POST /invoices/` references `current_user` but has no auth dependency — runtime NameError
**File:** `src/routers/invoices.py:28–107`

The admin invoice creation endpoint has **no `current_user` dependency** in its signature:

```python
# invoices.py:28 — signature has no current_user
async def create_invoice(invoice_data: CreateInvoice, db: AsyncSession = Depends(get_db)):
    ...
    await emit_chat_message(..., sender_id=current_user.id, ...)  # line 95 → NameError
```

Any request to this endpoint will raise `NameError: name 'current_user' is not defined`. It is also **completely unauthenticated** — the docstring says "Admin only" but there is no guard at all.

**Fix:** Add `current_user=Depends(get_current_user)` (and an admin role check) to the function signature.

---

### [CRITICAL] OTP generated with non-cryptographic `random.choices`
**File:** `src/utils/auth/auth.py:96`

```python
def generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))  # NOT cryptographically secure
```

`random` is seeded from system time and is predictable. An attacker who can observe timing can narrow down the OTP search space significantly. For a 6-digit numeric OTP this is a serious risk on a financial platform.

**Fix:**
```python
import secrets
def generate_otp() -> str:
    return "".join(secrets.choice(string.digits) for _ in range(6))
    # or: return str(secrets.randbelow(1_000_000)).zfill(6)
```

---

### [CRITICAL] `emit_chat_message` called unconditionally outside `if image_messages:` block
**File:** `src/routers/orders.py:185–202`

The indentation places `await emit_chat_message(...)` **outside** the `if image_messages:` guard, making it run on every order creation — even when no images were uploaded — referencing the unbound variable `image_message`:

```python
# orders.py:185
if image_messages:
    await db.commit()
    for image_message in image_messages:
        await db.refresh(image_message)
    from utils.websocket.websocket_events import emit_chat_message
await emit_chat_message(   # ← same indent as `if`, runs unconditionally
    new_conversation.id,
    {"image_data": image_message.image_data, ...},  # NameError when no images
    db,
)
```

This is both a security issue (unhandled 500 on every imageless order) and a logic bug.

**Fix:** Indent the `emit_chat_message` call inside the `if image_messages:` block, and loop over all messages rather than only broadcasting the last one.

---

### [HIGH] In-memory rate limiting does not work on multi-worker deployments
**File:** `src/routers/auth.py:34–63`

```python
_phone_timestamps: dict[str, list[float]] = defaultdict(list)
_verify_timestamps: dict[str, list[float]] = defaultdict(list)
```

These are process-local dicts. With 4 uvicorn workers, each worker has its own copy, meaning the effective limit is `4 × 3 = 12` OTP requests per 10 minutes per phone — not 3. An attacker can bypass rate limiting simply by retrying until they hit a different worker process.

**Fix:** Replace with a Redis-backed counter using `INCR` + `EXPIRE`, or use `slowapi`/`limits` library with a Redis storage backend.

---

### [HIGH] No authentication on `GET /invoices/{invoice_id}`
**File:** `src/routers/invoices.py:239–249`

```python
@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    # No current_user dependency — fully public
```

Invoice IDs are sequential (`INV-000001`, `INV-000002`, …), so any unauthenticated user can enumerate all invoices and retrieve customer names, amounts, phone numbers, and order details.

**Fix:** Add `current_user=Depends(get_current_user)` and scope the query to orders owned by that user — or at minimum require authentication.

---

### [HIGH] Sequential, enumerable order IDs and invoice IDs expose business metrics
**File:** `src/routers/orders.py:98–100`, `src/routers/invoices.py:50–52, 143–145`

```python
# orders.py:100
order_id = f"ORDR-{100000 + max_id + 1}"

# invoices.py:52
invoice_id = f"INV-{invoice_count + 1:06d}"
```

These expose the total number of orders/invoices (competitive intelligence), allow enumeration attacks, and — for invoices — have a **race-condition duplicate ID bug**: two concurrent invoice creations can get the same count and generate the same `invoice_id`, violating the unique constraint.

**Fix:**
```python
import secrets
order_id = f"ORDR-{secrets.token_hex(8).upper()}"
invoice_id = f"INV-{secrets.token_hex(6).upper()}"
```

---

### [HIGH] Invoice count uses full table scan — also a race condition
**File:** `src/routers/invoices.py:50–52, 143–145`

```python
result = await db.execute(select(Invoice))           # loads ALL rows into memory
invoice_count = len(result.scalars().all())
invoice_id = f"INV-{invoice_count + 1:06d}"
```

This loads every Invoice object from the database just to count them. At scale this will OOM the worker. Additionally, if two requests run concurrently, both get the same count and generate a duplicate ID.

**Fix:**
```python
from sqlalchemy import func
result = await db.execute(select(func.count()).select_from(Invoice))
invoice_count = result.scalar()
```
But better: switch to `secrets.token_hex` IDs entirely (see above) and remove this pattern.

---

### [HIGH] `complete-profile` endpoint bypasses Pydantic — no input validation
**File:** `src/routers/auth.py:348–413`

```python
@router.post("/complete-profile", response_model=Token)
async def complete_profile(profile_data: dict, db: AsyncSession = Depends(get_db)):
    name = profile_data.get("name")
    email = profile_data.get("email")
```

Using a raw `dict` instead of a Pydantic model means: no type coercion, no length limits, no email format validation, no age check on `date_of_birth`, and no rejection of unexpected fields. Attackers can send arbitrary data.

**Fix:** Create a `CompleteProfileRequest` Pydantic model mirroring the validated fields in `UpdateUserProfile`.

---

### [HIGH] WebSocket allows joining arbitrary rooms — IDOR / eavesdropping
**File:** `src/main.py:279–285`

```python
elif action == "join_room":
    room = data.get("room")
    if room:
        await manager.join_room(user.id, room)  # no validation whatsoever
```

Any authenticated user can join `user_<other_user_id>` or `couriers_city_1` rooms and receive events intended for other users or couriers. No check that the user is authorized to be in the requested room.

**Fix:** Whitelist allowed room patterns and verify ownership:
```python
ALLOWED_ROOM_PATTERNS = [
    (r"^user_(\d+)$", lambda m, uid: int(m.group(1)) == uid),
    (r"^chat_(\d+)$", lambda m, uid: user_is_conversation_participant(uid, int(m.group(1)))),
]
```

---

### [HIGH] `complete-profile` always creates `CustomerProfile` regardless of role
**File:** `src/routers/auth.py:392`

```python
user.role = role  # could be UserRole.COURIER
db.add(CustomerProfile(user_id=user.id, timezone=timezone_val))  # always CustomerProfile
```

If the role is `Courier`, a `CustomerProfile` row is created for a courier, and no `CourierProfile` is created. The courier will have incorrect profile data and encounter `AttributeError` when courier-specific code accesses `courier_profile`.

**Fix:** Branch on `role`:
```python
if role == UserRole.CUSTOMER:
    db.add(CustomerProfile(user_id=user.id, timezone=timezone_val))
# CourierProfile creation should happen via a separate courier onboarding flow
```

---

### [HIGH] Courier role check uses hardcoded string instead of enum
**File:** `src/routers/invoices.py:120, 187`

```python
if current_user.role != "Courier":   # string comparison
```

`UserRole` is an enum. `current_user.role` is `UserRole.COURIER`, not the string `"Courier"`. This check will **always be True** (they are never equal), so the guard never actually blocks non-couriers from creating/updating invoices — any authenticated user can create an invoice.

**Fix:**
```python
from models.enums import UserRole
if current_user.role != UserRole.COURIER:
```

---

### [HIGH] No CORS middleware — legitimate frontend requests blocked
**File:** `src/main.py` (absent)

There is no `CORSMiddleware` configured. Any web frontend calling this API from a different origin will be blocked by the browser's same-origin policy. If someone has added a permissive CORS config elsewhere (e.g., in a reverse proxy), that's also a risk vector.

**Fix:**
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
```
Add `allowed_origins` to `settings` — never use `["*"]` in production with `allow_credentials=True`.

---

### [MEDIUM] `update_order_status` assigns raw string to SQLAlchemy enum column
**File:** `src/routers/orders.py:778–795`

```python
valid_statuses = ["received by courier", "in_progress", "ready_for_delivery", "out_for_delivery"]
order.status = status   # raw string bypasses OrderStatus enum
```

`"received by courier"` (with a space) does not match `OrderStatus.RECEIVED_BY_COURIER`. SQLAlchemy will attempt to store the raw string, which may raise a DB-level constraint violation or silently corrupt the enum column. Other strings like `"in_progress"` may or may not map to enum values.

**Fix:** Validate against `OrderStatus` enum members:
```python
try:
    order.status = OrderStatus(status)
except ValueError:
    raise HTTPException(400, detail="Invalid status")
```

---

### [MEDIUM] Wallet top-up in `paylink_callback` not atomic — double-credit race condition
**File:** `src/routers/payments.py:268–276`

```python
wallet.balance += payment.amount    # read-modify-write, not atomic
wallet.updated_at = datetime.now(timezone.utc)
await db.commit()
```

Two concurrent webhook deliveries for the same transaction (common in payment gateways) can both pass the `payment.status != PENDING` check (line 235) before either commits, leading to double wallet credit. The invoice payment path uses a proper `update()` + arithmetic (atomically on the DB side), but the wallet top-up does not.

**Fix:**
```python
from sqlalchemy import update
await db.execute(
    update(Wallet).where(Wallet.user_id == payment.user_id)
    .values(balance=Wallet.balance + payment.amount, updated_at=datetime.now(timezone.utc))
)
```

---

### [MEDIUM] `verify-coupon` uses timezone-naive `datetime.utcnow()`
**File:** `src/routers/invoices.py:577`

```python
if not coupon.active or coupon.valid_until < datetime.utcnow():  # naive comparison
```

`coupon.valid_until` is a timezone-aware UTC datetime (stored by SQLAlchemy with `timezone=True`). Comparing it to a naive `datetime.utcnow()` raises `TypeError` on Python 3.11 or silently produces wrong results on some DB backends.

**Fix:**
```python
if not coupon.active or coupon.valid_until.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
```

---

### [MEDIUM] Admin middleware runs a DB query for every `/admin` request including static assets
**File:** `src/main.py:133–172`

The `admin_auth_middleware` opens an `AsyncSessionLocal()` and queries the `Admin` table on **every** request matching `/admin/*` — including CSS, JS, and font files served by SQLAdmin. This means tens of DB queries per page load.

**Fix:** Cache successful auth lookups with a short TTL (e.g., 60s) keyed by the bcrypt-verified credentials. Or move auth to a FastAPI `Depends()` on the router level so it only runs on API routes.

---

### [MEDIUM] `order.comments` stores user PII in plaintext
**File:** `src/routers/orders.py:327, 371, 466, 712`

```python
order.comments = f"{cancel_data.reason} by ID:{current_user.id} and name:{current_user.name}"
```

User names and IDs are embedded in a generic comments field that is visible in admin views and included in API responses. This may conflict with PDPL (Saudi personal data protection) requirements.

**Fix:** Store structured audit data in a separate `OrderEvent` table with `user_id` (FK) and `event_type` instead of embedding PII in free-text fields.

---

### [MEDIUM] Missing Content-Security-Policy header
**File:** `src/main.py:76–87`

`SecurityHeadersMiddleware` sets HSTS, X-Frame-Options, X-XSS-Protection, and Referrer-Policy, but omits `Content-Security-Policy`. Without CSP, the admin dashboard is more vulnerable to XSS.

**Fix:** Add to `SecurityHeadersMiddleware`:
```python
response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; object-src 'none';"
```

---

### [LOW] `push_token` endpoint accepts unbounded-length string
**File:** `src/routers/auth.py:459`

```python
push_token = data.get("push_token", "").strip()
```

No maximum length enforced. FCM/APNs tokens are ~163 characters. A malicious actor can store megabytes in this column, bloating the DB.

**Fix:** Add `if len(push_token) > 300: raise HTTPException(400, "Invalid token")` or validate format.

---

### [LOW] `dev/otp` endpoint exists in production code path
**File:** `src/routers/auth.py:503–512`

The endpoint is guarded by `settings.debug`, but the route is **registered** regardless of environment. A misconfigured `DEBUG=true` in production (easy mistake when copying `.env` files) immediately leaks all OTPs. The route should not exist in the production codebase at all.

**Fix:** Register the router conditionally:
```python
if settings.debug:
    router.add_api_route("/dev/otp", dev_get_otp, methods=["GET"])
```

---

## 2. Performance Issues

### [CRITICAL] Full table scan to generate invoice IDs
**File:** `src/routers/invoices.py:50–52, 143–145`

```python
result = await db.execute(select(Invoice))   # SELECT * FROM invoices — all rows
invoice_count = len(result.scalars().all())  # loaded into Python memory
```

At 100k invoices, this loads 100k ORM objects on every invoice creation. This will OOM a typical 512MB container.

**Fix:**
```python
result = await db.execute(select(func.count()).select_from(Invoice))
invoice_count = result.scalar()
```
Or (better) use `SELECT MAX(id)` or switch to `secrets.token_hex` IDs.

---

### [HIGH] Sequential S3 image uploads block the request handler
**File:** `src/routers/orders.py:113–128`

```python
for img_num, img_file in uploaded_images:
    result = await upload_image(...)   # sequential — each blocks
```

Three images = three sequential network round-trips to S3. With 200ms per upload, this adds 600ms of latency to every order creation.

**Fix:**
```python
import asyncio
upload_tasks = [
    upload_image(user_id=..., image_type=..., image=img) for _, img in uploaded_images
]
results = await asyncio.gather(*upload_tasks)
```

---

### [HIGH] Multiple unnecessary DB commits in `create_order`
**File:** `src/routers/orders.py:110–188`

The endpoint commits to the database at least **5 separate times**:
1. After inserting the order (line 111)
2. After inserting `OrderImage` (line 132)
3. After inserting `Conversation` (line 141)
4. After inserting description `Message` (line 155)
5. After inserting image `Message` objects (line 186)

Each commit is a round-trip to PostgreSQL and flushes WAL. All of these can be batched into 1–2 commits.

**Fix:** Accumulate all objects with `db.add()` and call `await db.commit()` once at the end, followed by a single `await db.refresh()`.

---

### [HIGH] `today_start`/`today_end` are timezone-naive — incorrect DB filtering
**File:** `src/routers/orders.py:629–630`

```python
today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min)
today_end   = datetime.combine(datetime.now(timezone.utc).date(), time.max)
```

`datetime.combine` with `time.min` returns a **naive** datetime. PostgreSQL will compare it against UTC-stored timestamps without timezone conversion, giving wrong results for users outside UTC (all Saudi users are UTC+3).

**Fix:**
```python
from datetime import timezone
today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
today_end   = datetime.combine(datetime.now(timezone.utc).date(), time.max, tzinfo=timezone.utc)
```

---

### [HIGH] N+1 queries in `paylink_callback` for invoice payment
**File:** `src/routers/payments.py:244–265`

```python
result2 = await db.execute(select(Invoice).options(...).where(...))    # query 1
result3 = await db.execute(select(User).where(...))                    # query 2
result4 = await db.execute(select(func.sum(...)).where(...))           # query 3
```

Three sequential queries where one joined query would suffice. Under high payment volume (e.g., a flash sale) this triples the DB load.

**Fix:** Join `Invoice`, `User`, and `Payment` in a single query, or at minimum run the user and sum queries concurrently with `asyncio.gather`.

---

### [MEDIUM] `_check_phone_rate_limit` rebuilds a new list on every call
**File:** `src/routers/auth.py:41–43`

```python
_phone_timestamps[phone] = [
    t for t in _phone_timestamps[phone] if now - t < _PHONE_WINDOW
]
```

Under abusive conditions (many requests from one phone), this list can grow large before eviction and rebuilding it allocates a new list object each time. A `collections.deque` with `maxlen` or a sorted structure would be O(1) to trim.

**Fix:**
```python
from collections import deque
_phone_timestamps: dict[str, deque] = defaultdict(lambda: deque(maxlen=_PHONE_MAX))
# evict stale: popleft while oldest > window
```

---

### [MEDIUM] `delete_file_after_delay` uses a blocking `threading.Timer` inside an async app
**File:** `src/routers/invoices.py:279–292`

```python
timer = Timer(delay_seconds, delete_file)   # threads in async app
timer.start()
```

`threading.Timer` spawns a real OS thread (600 per concurrent PDF download in the worst case), which is unnecessary in an async app. The `BackgroundTasks` parameter is already available on the endpoint.

**Fix:** Remove `delete_file_after_delay` and pass the sync `os.remove` directly to FastAPI's `background_tasks`:
```python
background_tasks.add_task(os.remove, temp_filepath)
```
(FastAPI runs sync background tasks in a thread pool automatically.)

---

### [MEDIUM] `get_current_user` eager-loads both profiles on every authenticated request
**File:** `src/utils/auth/auth.py:130–133`

```python
result = await db.execute(
    select(User)
    .options(selectinload(User.courier_profile), selectinload(User.customer_profile))
    .where(User.id == user_id)
)
```

Every authenticated endpoint loads both `courier_profile` and `customer_profile` even if only one is needed. This adds 1–2 extra SELECT queries per request.

**Fix:** Use `lazy="select"` on the relationship and only load explicitly when needed, or pass the user's role from the JWT payload to skip the unnecessary profile load on endpoints that don't use it.

---

### [LOW] Rate-limit dict grows unboundedly in memory
**File:** `src/routers/auth.py:34–35`

`_phone_timestamps` and `_verify_timestamps` are never purged of phone number keys. After receiving requests from N distinct phone numbers, there are N keys in memory forever (just with empty lists after the window expires). Under sustained traffic, this leaks memory.

**Fix:** Use `weakref` values or a TTL-based cache (e.g., `cachetools.TTLCache`), or better, move to Redis.

---

## 3. Logic Issues

### [CRITICAL] Only last image message is broadcast in `create_order` — earlier images silently dropped
**File:** `src/routers/orders.py:171–202`

The loop at line 172 iterates over all uploaded images and adds `Message` objects to `image_messages`. However, the `emit_chat_message` call at line 190 (which is outside the `if` block — see Security section) references `image_message` (the last loop variable), broadcasting only the last image. All previous image messages are saved to the DB but never sent via WebSocket.

**Fix:** Move the emit inside the loop:
```python
if image_messages:
    await db.commit()
    for img_msg in image_messages:
        await db.refresh(img_msg)
        await emit_chat_message(new_conversation.id, {...}, db)
```

---

### [CRITICAL] `create_invoice` (admin endpoint) is permanently broken at runtime
**File:** `src/routers/invoices.py:95`

As noted in Security, `current_user` is referenced on line 95 but is not in scope. Every POST to `/invoices/` raises `NameError` → HTTP 500. The admin invoice workflow is completely non-functional.

**Fix:** Add the dependency and an admin role guard to the function signature.

---

### [HIGH] Courier invoice role check is inverted — any user can create invoices
**File:** `src/routers/invoices.py:120, 187`

```python
if current_user.role != "Courier":   # UserRole.COURIER != "Courier" → always True
    raise HTTPException(403, "Only couriers can create invoices")
```

`UserRole.COURIER` is an enum object; `"Courier"` is a string. They are never equal in Python. The condition is **always True**, so the guard **always raises 403** — no one can create invoices via this endpoint, including actual couriers.

**Fix:** `if current_user.role != UserRole.COURIER:`

---

### [HIGH] Money amounts displayed without halala→SAR conversion in invoice chat messages
**File:** `src/routers/invoices.py:96, 225`

```python
# invoices.py:96
content=f"تم إنشاء فاتورة جديدة بمبلغ {new_invoice.full_amount:.2f} ريال"
# invoices.py:225
content=f"تم تحديث الفاتورة - المبلغ الجديد: {invoice.full_amount:.2f} ريال"
```

Per CLAUDE.md, money is stored as integers in halalas (1 SAR = 100). An invoice for 500 SAR has `full_amount = 50000`. These messages would display `50000.00 ريال` instead of `500.00 ريال`. The payments router correctly divides by 100 (`payments.py:52`) but the invoices router does not.

**Fix:**
```python
content=f"تم إنشاء فاتورة جديدة بمبلغ {new_invoice.full_amount / 100:.2f} ريال"
```

---

### [HIGH] Order acceptance has no concurrency guard — two couriers can accept the same order
**File:** `src/routers/orders.py:442–463`

```python
if order.status != OrderStatus.NEW:
    raise HTTPException(400, "Order is no longer available")
# ... no lock between check and assignment
order.assigned_to_user_id = current_user.id
order.status = OrderStatus.RECEIVED_BY_COURIER
```

Two couriers sending `PUT /orders/{id}/accept` simultaneously both pass the `status == NEW` check, both proceed to assign, and the last commit wins — but the first courier may have sent a welcome message and received a WS notification. The second courier ends up owning the order silently.

**Fix:** Use a database-level optimistic lock or `SELECT FOR UPDATE`:
```python
result = await db.execute(
    select(Order).where(Order.order_id == order_id, Order.status == OrderStatus.NEW)
    .with_for_update(skip_locked=True)
)
```

---

### [HIGH] `balance_before` in `complete_order` calculated after atomic update — potentially wrong under concurrency
**File:** `src/routers/orders.py:694–707`

```python
await db.execute(update(Wallet).values(balance=Wallet.balance + courier_fee, ...))
result = await db.execute(select(Wallet.balance).where(...))
balance_after = result.scalar_one()
balance_before = balance_after - courier_fee   # derived, not read from DB
```

The `balance_after` is read after the update, then `balance_before` is derived by subtracting `courier_fee`. If another concurrent transaction modified the wallet between the `UPDATE` and the `SELECT`, `balance_before` will be wrong. This corrupts the `CourierBalanceAddition` audit trail.

**Fix:** Capture `balance_before` with a `SELECT FOR UPDATE` **before** the update, or use `RETURNING` clause:
```python
result = await db.execute(select(Wallet.balance).where(...).with_for_update())
balance_before = result.scalar_one()
await db.execute(update(Wallet).values(balance=Wallet.balance + courier_fee))
```

---

### [HIGH] `update_invoice_by_courier` allows editing a paid invoice
**File:** `src/routers/invoices.py:176–236`

```python
async def update_invoice_by_courier(...):
    invoice.full_amount = invoice_data.full_amount
    # No check: if invoice.status == InvoiceStatus.PAID: raise 400
```

A courier can update invoice amounts even after the customer has paid. This could be used to retroactively change the amount to anything.

**Fix:** Add a status guard:
```python
if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED):
    raise HTTPException(400, "Cannot update a paid or cancelled invoice")
```

---

### [HIGH] PDF invoice tax line is recalculated from `order_only_price * 0.15` — ignores stored `tax_amount`
**File:** `src/routers/invoices.py:361`

```python
["Tax (15%)", "1", f"{(invoice.order_only_price * 0.15):.2f} SAR"],
```

The invoice model has a `tax_amount` field, but the PDF ignores it and recalculates. If the stored tax differs from 15% of `order_only_price` (e.g., for discounts, different rates, or manual overrides), the PDF will show a wrong figure. The total line shows the actual `full_amount` while the itemization does not add up.

**Fix:** Use `invoice.tax_amount` directly.

---

### [MEDIUM] `cancel_order` does not cancel a PAYMENT_PENDING order's active payment
**File:** `src/routers/orders.py:316–333`

When a customer cancels an order with a `PAYMENT_PENDING` invoice, the order is cancelled but the associated `Payment` record remains `PENDING`. If the customer completes payment via the Paylink URL after cancellation, the webhook will mark the invoice as `PAID` and the order as `PAID` — overriding the cancellation.

**Fix:** On order cancellation, also set any `PENDING` payment records to `FAILED` and mark the invoice as `CANCELLED`.

---

### [MEDIUM] `verify-coupon` endpoint does not check per-user coupon usage
**File:** `src/routers/invoices.py:538–618`

The `pay_with_wallet` endpoint correctly checks `PromocodeUsage` to prevent reuse (`payments.py:402–411`). The `verify-coupon` endpoint does **not**. A user who has already used a coupon will get a valid discount preview from `/invoices/verify-coupon` but will be rejected at payment time — misleading UX.

**Fix:** Add the same `PromocodeUsage` check to `verify-coupon`.

---

### [MEDIUM] OTP rate limit uses pre-normalized phone — different formats bypass limit
**File:** `src/routers/auth.py:107`

```python
_check_phone_verify_rate_limit(otp_data.phone_number)  # raw, un-normalized
user = await get_user_by_phone(db, otp_data.phone_number)  # normalizes internally
```

A user can request OTPs for `+9665XXXXXXXX`, `05XXXXXXXX`, and `5XXXXXXXX` — all resolving to the same user — but each consumes a separate rate-limit slot (3 keys × 3 attempts = 9 effective attempts). The rate limit should be applied after normalization.

**Fix:**
```python
import re
def _normalize_phone(phone: str) -> str:
    return re.sub(r"^(\+966|0)+", "", phone)

phone_normalized = _normalize_phone(otp_data.phone_number)
_check_phone_verify_rate_limit(phone_normalized)
```

---

### [MEDIUM] `GET /invoices/{invoice_id}` route conflicts with `/order/{order_id}` — FastAPI path collision
**File:** `src/routers/invoices.py:239, 511`

FastAPI resolves path parameters greedily. Both `GET /invoices/{invoice_id}` and `GET /invoices/order/{order_id}` are registered. When a request comes in for `/invoices/order/5`, FastAPI will match the first route and pass `"order"` as `invoice_id`, causing a 404 instead of routing to the second endpoint.

**Fix:** Re-order the routes so that fixed-segment routes (`/order/...`, `/id/...`, `/courier/...`) are defined before the wildcard `/{invoice_id}`.

---

### [LOW] `datetime.utcnow()` used in `update_invoice_by_courier` — deprecated in Python 3.12+
**File:** `src/routers/invoices.py:214`

```python
invoice.updated_at = datetime.utcnow()
```

`datetime.utcnow()` returns a naive datetime and is deprecated since Python 3.12. All other timestamps in the codebase use `datetime.now(timezone.utc)`.

**Fix:** `invoice.updated_at = datetime.now(timezone.utc)`

---

### [LOW] `assign_order` does not verify the courier is in the same city as the order
**File:** `src/routers/orders.py:336–379`

`accept_order` (courier self-assigns) checks `order.city_id != profile.city_id`. But `assign_order` (admin assigns) does not check this — an admin can assign a courier from Riyadh to an order in Jeddah.

**Fix:** Add a city match check in `assign_order`.

---

## 4. Improvement Suggestions

### [HIGH] Add `asyncio.gather` for concurrent image uploads
**File:** `src/routers/orders.py:113–128`

Image uploads happen one-by-one. Using `asyncio.gather` can reduce latency by ~2× for 2 images and ~3× for 3 images with no code complexity increase (see Performance section).

---

### [HIGH] Replace all `raw dict` endpoint signatures with Pydantic models
**Files:** `src/routers/auth.py:417, 452`, `src/routers/admin.py` (charge endpoint)

Three endpoints accept `data: dict` instead of typed Pydantic models. This means no OpenAPI docs for these parameters, no automatic validation, and no IDE autocompletion. Create `UpdateTimezoneRequest`, `UpdatePushTokenRequest` Pydantic models.

---

### [HIGH] Move storage base URL to settings
**File:** `src/utils/clients/storage_client.py` (hardcoded `https://storage-giftly-storage.cranl.net/`)

The storage URL is hardcoded in the client. If the CDN or bucket changes, the code must be edited. Add `STORAGE_BASE_URL` to `settings`.

---

### [HIGH] Add `Content-Security-Policy` and `Permissions-Policy` security headers
**File:** `src/main.py:76–87`

The `SecurityHeadersMiddleware` is missing CSP and `Permissions-Policy`. The SQLAdmin interface (which serves HTML) is particularly vulnerable without CSP.

---

### [MEDIUM] Standardize money-to-display conversion into a helper
**Files:** `src/routers/invoices.py:96, 225`, `src/routers/payments.py:52, 466`

Some places divide by 100, some don't. Introduce a one-liner:
```python
def sar(halalas: int) -> str:
    return f"{halalas / 100:.2f}"
```
Use it everywhere money is displayed to users.

---

### [MEDIUM] `complete_profile` should enforce a temp-token auth check
**File:** `src/routers/auth.py:348`

The endpoint queries by `phone_number` from the request body — no JWT validation at all. Any caller knowing a phone number can complete another user's profile if that user is in the `is_verified=False` state. The temp token issued at `verify_otp` (line 214) should be required via `Depends`.

---

### [MEDIUM] Replace `threading.Timer` PDF cleanup with `asyncio`
**File:** `src/routers/invoices.py:279–291`

Use `background_tasks.add_task(os.remove, path)` (already available in the endpoint signature) instead of creating OS threads. See Performance section.

---

### [MEDIUM] `CourierBalanceAddition` only records when a payment record exists — silently skips wallet payments
**File:** `src/routers/orders.py:716–732`

```python
result = await db.execute(select(Payment).where(..., Payment.status == "completed"))
payment = result.scalar_one_or_none()
if payment:
    db.add(CourierBalanceAddition(...))
# silently no audit log if no payment found
```

The status comparison uses a string `"completed"` instead of `PaymentStatus.COMPLETED`. If the comparison fails, no audit record is created — the courier's wallet increases silently with no audit trail. Fix the enum comparison and add an `else` branch to log the anomaly.

---

### [MEDIUM] Paginate courier/city broadcast on order creation
**File:** `src/routers/orders.py:206–223`

Broadcasting to `couriers_city_{city_id}` is O(n) where n is connected couriers. If a city has 500 connected couriers, this sends 500 WebSocket messages synchronously in the request handler, adding latency proportional to room size. Consider an async broadcast queue or background task.

---

### [MEDIUM] Add explicit `status` filter to `/courier/available` to exclude `assigned_to_user_id IS NOT NULL` orders from a race window
**File:** `src/routers/orders.py:403–416`

The query already filters `Order.assigned_to_user_id.is_(None)` and `Order.status == OrderStatus.NEW`, but between the SELECT and the courier's `accept_order` request, another courier may have already accepted. A database-level `SELECT FOR UPDATE SKIP LOCKED` in the accept endpoint (see Logic Issues) is the real fix, but the available orders list should also refresh client-side more aggressively to reduce UX friction.

---

### [MEDIUM] Courier `max_concurrent_orders` field exists but is never enforced
**File:** `src/models/courier/courier_profile.py` (field exists), `src/routers/orders.py` (no check)

`CourierProfile.max_concurrent_orders` is defined in the model but `accept_order` never checks it. A courier can accept unlimited orders regardless of this setting.

**Fix:** In `accept_order`, query active order count and compare against `profile.max_concurrent_orders`.

---

### [LOW] Add database health check to `/health` endpoint
**File:** `src/main.py:204–206`

`GET /health` returns `{"status": "ok"}` regardless of DB connectivity. Load balancers and k8s liveness probes rely on this endpoint — it should actually test the DB.

**Fix:**
```python
@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
```

---

### [LOW] `generate_invoice_pdf` uses floating-point arithmetic on halala values
**File:** `src/routers/invoices.py:359–362`

```python
["Order Value", "1", f"{invoice.order_only_price:.2f} SAR"],
["Tax (15%)", "1", f"{(invoice.order_only_price * 0.15):.2f} SAR"],
```

Amounts are halalas (integers), but formatted with `:.2f` which shows them as SAR without division. Multiplying by 0.15 on an integer is also potentially wrong if the stored value is not in SAR. All PDF amounts should divide by 100 first.

---

### [LOW] Soft-delete cleanup endpoint lacks a dry-run mode
**File:** `src/routers/admin.py` (cleanup endpoint)

The hard-delete cleanup endpoint permanently destroys records. A dry-run query param (`?dry_run=true`) that returns counts without deleting would make the admin safer to operate without fear of accidental data loss.

---

### [LOW] Structured logging could include `order_id` and `invoice_id` for better traceability
**File:** `src/middleware/logging.py`

The request logger records `method`, `path`, `status_code`, `duration_ms`, and `user_id`. Adding `order_id` or `invoice_id` when present in the path would make log correlation much easier during incident investigation.

---

### [LOW] `is_verified` is embedded in the access token but can become stale
**File:** `src/utils/auth/auth.py:70`

```python
"is_verified": user.is_verified,
```

If an admin revokes a user's verification after they have a valid access token, the token still claims `is_verified=True` until it expires (up to 15 minutes). For a financial platform this window may be acceptable, but it should be a documented decision. Consider checking `is_verified` from the DB in `get_current_user` for sensitive operations.

---

*End of audit — 44 findings across 4 categories.*
