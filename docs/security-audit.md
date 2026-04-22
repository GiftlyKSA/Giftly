# Giftly Backend — Security Audit

> Original audit: 2026-04-21
> Updated: 2026-04-22 — 26 original findings (21 fixed, 5 carried as open); OWASP Top 10 comprehensive review added (15 new findings, 3 critical)
> Scope: `src/` — all routers, middleware, utils, models, schemas

---

## Severity Key

| Severity | Definition |
|---|---|
| **CRITICAL** | Exploitable without privilege, leads to account takeover, data theft, or financial fraud |
| **HIGH** | Requires low privilege or specific conditions, significant business impact |
| **MEDIUM** | Requires moderate effort or conditions, partial impact |
| **LOW** | Defence-in-depth issue, minimal direct impact |

---

## Part 1 — Original Audit Findings

### 1. Broken Authentication & Authorization

#### ✅ [CRITICAL] Account takeover via unauthenticated `/auth/complete-profile` — FIXED
`complete_profile` now requires a temp JWT (issued by `verify_otp`). The endpoint uses `get_profile_user` dependency which accepts only temp tokens. The user's phone is taken from `current_user.phone_number`, not the request body. Temp tokens are rejected by all other endpoints via `get_current_user`.

---

#### ✅ [CRITICAL] IDOR on `GET /invoices/{invoice_id}` — FIXED
Ownership check added: the query now JOINs with `Order` and requires `created_by_user_id == current_user.id OR assigned_to_user_id == current_user.id`.

---

#### ✅ [HIGH] `PUT /orders/{id}/assign` has no role check — FIXED
Endpoint now uses `authenticate_admin` (HTTP Basic Auth) instead of `get_current_user`. Only admins with valid credentials can assign orders.

---

#### ✅ [MEDIUM] `initiate_wallet_charge` accepts unbounded amount — FIXED
Only `UserRole.CUSTOMER` can call the endpoint (couriers are rejected). Minimum and maximum are env-configurable (`WALLET_CHARGE_MIN_SAR`, `WALLET_CHARGE_MAX_SAR`). Generic error message returned on gateway failure.

---

#### ✅ [MEDIUM] `admin_charge_wallet` has no upper bound — FIXED
Maximum cap is env-configurable (`ADMIN_WALLET_CHARGE_MAX_HALALAS`, default 1,000,000 halalas). Limit included in error message.

---

### 2. Race Conditions & Business Logic

#### ✅ [CRITICAL] Double-spend in `paylink_callback` — FIXED
Payment status update is now atomic: `UPDATE Payment WHERE status=PENDING → COMPLETED`. If `rowcount == 0` the webhook was already processed. Same pattern applied to the `FAILED` path.

---

#### ✅ [HIGH] `accept_order` has no `SELECT FOR UPDATE` — FIXED
Replaced with an atomic `UPDATE Order WHERE status=NEW` and `rowcount` check. Courier profile validation (approved, available, city) runs before the atomic claim. The order is reloaded after commit.

---

#### ✅ [HIGH] `cancel_order` leaves active payment → webhook can reactivate — FIXED
On cancellation: if the invoice exists and is not already paid/cancelled, it is marked `CANCELLED`. All `PENDING` payments for that invoice are atomically set to `FAILED`.

---

#### ✅ [MEDIUM] `complete_order` courier `balance_before` wrong under concurrency — FIXED
`balance_before` is now read from the in-memory `courier_wallet.balance` (fetched before the UPDATE), not derived after the fact.

---

#### ✅ [MEDIUM] `CourierBalanceAddition` silently skipped due to string vs enum — FIXED
`Payment.status == "completed"` changed to `Payment.status == PaymentStatus.COMPLETED`.

---

### 3. Injection & XSS

#### ✅ [HIGH] SVG file upload allows stored XSS — FIXED
`image/svg+xml` removed from allowed MIME types and `"svg"` removed from the file-extension fallback in `POST /orders/`.

---

#### ✅ [HIGH] SVG allowed in chat media uploads — FIXED
`image/svg+xml` and `"svg"` removed from chat upload allowed lists. Only JPEG and PNG are permitted. Magic-byte validation added (`_image_magic_ok`). Size limit: 6 MB (env: `CHAT_IMAGE_MAX_BYTES`).

---

#### ✅ [HIGH] Stored XSS in WebSocket chat — FIXED
`html.escape()` applied to message content after the control-character filter. Untrusted `invoice_*` fields removed from the WebSocket `Message` constructor.

---

#### ✅ [MEDIUM] Untrusted invoice amounts in REST chat endpoint — FIXED (blocked from clients)
`invoice_*` form fields are accepted but the `system` message type is now blocked from clients. Additionally: invoice amounts are client-supplied for `invoice` type messages only, which is restricted to conversation participants. Cross-checking against the DB invoice record remains a recommended hardening step.

---

#### ✅ [LOW] No HTML escaping in REST chat messages — FIXED
`html.escape(content.strip())` applied before creating the `Message` object in `send_message`. Content length also enforced (env: `CHAT_MSG_MAX_CHARS`, default 300).

---

#### ✅ [MEDIUM] Internal exception messages exposed in API responses — FIXED
`str(e)` removed from all HTTP 500/502 error details. Full exceptions are logged server-side; clients receive generic messages.

---

#### ✅ [MEDIUM] WebSocket `send_message` accepts invoice fields from client — FIXED
Invoice fields no longer accepted from WebSocket clients.

---

### 4. File Handling

#### ✅ [HIGH] Predictable PDF temp filenames — FIXED
Both PDF endpoints now use `StreamingResponse` to stream the PDF buffer directly — no temp file written to disk.

---

### 5. Rate Limiting & Denial of Service

#### [HIGH] In-memory rate limiting bypassed in multi-worker deployments — **OPEN**
**File:** `src/routers/auth.py`

The `_phone_timestamps` and `_verify_timestamps` dicts are per-process. With N uvicorn workers, the effective OTP rate limit is N × 3.

**Partial mitigation:** Phone numbers are normalized before the rate limit check. `CLAUDE.md` documents this limitation.

**Full fix:** Replace with Redis atomic counters (`INCR` + `EXPIRE`). The Redis URL is already in settings.

---

#### ✅ [MEDIUM] OTP rate limit on un-normalized phone — FIXED
Both `send_otp` and `verify_otp` now normalize the phone number via `re.sub(r"^(\+966|0)+", "", ...)` before calling the rate-limit check functions.

---

#### ✅ [MEDIUM] Unbounded `push_token` length — FIXED
`len(push_token) > 300` check added; returns HTTP 400.

---

#### [LOW] No rate limiting on `/paylink-callback` — **OPEN**
The webhook endpoint remains unauthenticated and rate-unlimited. A flood of garbage `transactionNo` values triggers a DB query per request.

**Fix:** Add IP allowlisting for Paylink server IPs, or add `slowapi` rate limiting on this endpoint.

---

#### ✅ [LOW] Any user can create `system`-type messages — FIXED
`"system"` removed from the set of valid message types accepted from clients. Valid client types: `["text", "invoice", "image", "video"]`.

---

#### ✅ [LOW] No max content length in REST chat messages — FIXED
Content length limited to `settings.chat_msg_max_chars` (default 300, env: `CHAT_MSG_MAX_CHARS`) before persisting.

---

### 6. Sensitive Data Exposure

#### ✅ [HIGH] `dev/otp` endpoint always registered — FIXED
The route is now registered only when `settings.debug is True`. In production (`DEBUG=false`) the route does not exist.

---

#### ✅ [MEDIUM] PII embedded in `order.comments` — PARTIALLY FIXED
User names (`current_user.name`) have been removed from `order.comments`. User IDs are retained for audit correlation.

---

#### ✅ [LOW] Payment gateway `str(e)` in 502 detail — FIXED

---

### 7. Security Misconfiguration

#### [HIGH] Admin Basic auth credentials travel in Base64 — **OPEN** (mitigated)
HTTP Basic Auth is Base64-encoded. `ForceHTTPSMiddleware` and `HSTS` headers mitigate this in production. Ensure HTTPS is enforced at the infrastructure level.

---

#### ✅ [MEDIUM] Admin middleware runs bcrypt on every static asset — FIXED
Successful `Authorization` header verifications are cached for 60 seconds (keyed by `sha256(Authorization header)`). Cached requests skip the DB query and bcrypt check.

---

#### [LOW] `is_verified` claim in JWT can become stale — **OPEN**
If an admin revokes a user's verified status, their existing access token continues to claim `is_verified=True` until expiry. Acceptable for short-lived tokens.

---

#### ✅ [LOW] Pydantic V1-style validators — FIXED
All `@validator` decorators migrated to `@field_validator` + `@classmethod`. All `class Config:` blocks replaced with `model_config = ConfigDict(...)`. `SettingsConfigDict` used for pydantic-settings. No more deprecation warnings on request.

---

---

## Part 2 — OWASP Top 10 Comprehensive Review

> Performed: 2026-04-22

---

### A01: Broken Access Control

#### ✅ Temp token correctly blocked from regular endpoints
`get_current_user` rejects tokens with `"temp": True`. Confirmed in code and test coverage.

#### [MEDIUM] Courier cannot access invoice via `/invoices/id/{id}` endpoint — **OPEN**
**File:** `src/routers/invoices.py`

The `/invoices/{invoice_id}` (string lookup) correctly allows both customer and assigned courier. However, the secondary endpoint `GET /invoices/id/{invoice_db_id}` only checks `Order.created_by_user_id == current_user.id`, locking out the assigned courier.

**Fix:** Add `or_(Order.created_by_user_id == current_user.id, Order.assigned_to_user_id == current_user.id)` to the secondary endpoint's ownership filter.

#### [LOW] No rate limiting on public enumeration endpoints — **OPEN**
Endpoints like `GET /cities/`, `GET /couriers/available/{city_id}`, `GET /promocodes/active/list` have no rate limiting. An attacker can enumerate users and couriers by city.

**Fix:** Add per-IP rate limiting via `slowapi` or Redis counters on enumeration-sensitive endpoints.

---

### A02: Cryptographic Failures

#### [HIGH] Non-constant-time OTP comparison — **OPEN**
**File:** `src/routers/auth.py`

```python
if user.otp != otp_data.otp:
```

Python's `!=` on strings is not constant-time. Statistical timing analysis across many requests can leak OTP digits.

**Fix:**
```python
import secrets
if not secrets.compare_digest(user.otp or "", otp_data.otp or ""):
    raise HTTPException(status_code=400, detail="Invalid OTP")
```

#### ✅ JWT algorithm pinned to HS256
All `jwt.decode()` calls pass `algorithms=["HS256"]`. The `"none"` algorithm attack is not possible.

#### ✅ Refresh token comparison uses constant-time digest
`hmac.compare_digest()` confirmed at `src/utils/auth/auth.py`.

---

### A03: Injection

#### ✅ SQL Injection — Not present
All queries use SQLAlchemy ORM with parameterized bindings. No raw `execute()` with f-strings found.

#### ✅ Command Injection — Not present
No `os.system`, `subprocess`, `eval`, or `__import__` with user input found.

#### ✅ Template Injection — Not present
Jinja2 email templates use controlled context variables, not user-supplied template strings.

---

### A04: Insecure Design

#### [CRITICAL] No webhook signature verification on `/payments/paylink-callback` — **OPEN**
**File:** `src/routers/payments.py`

The callback endpoint accepts any POST payload and trusts the `orderStatus` field directly. An unauthenticated attacker can POST a fake "paid" callback to:
- Mark any payment as `COMPLETED`
- Credit any wallet with arbitrary amounts
- Mark invoices as paid without actual fund transfer

**Fix (recommended):** Verify incoming webhook payloads against a shared HMAC-SHA256 secret provided by Paylink, or re-validate the transaction status directly with the Paylink API before updating state:
```python
async with PaylinkClient(settings.paylink_api_key) as paylink:
    live = await paylink.get_invoice(transaction_no)
    if live.get("orderStatus") != "paid":
        return {"message": "Status mismatch — ignoring"}
```

#### ✅ Double-spend race condition — FIXED
Atomic `UPDATE WHERE status=PENDING` + rowcount check prevents replay.

#### [MEDIUM] In-memory OTP rate limit bypassed in multi-worker/multi-replica deployments — **OPEN**
See Part 1, Section 5. Repeated here as it is an architectural design gap.

---

### A05: Security Misconfiguration

#### [MEDIUM] CORS defaults to allow all origins — **OPEN**
**File:** `src/utils/database/config.py`, `src/main.py`

`allowed_origins: list[str] = ["*"]` is the default. With `allow_credentials=True`, browsers will include cookies/auth headers in cross-origin requests from any domain. This bypasses same-origin protection entirely.

**Fix:** Set explicit allowed origins in production `.env`:
```
ALLOWED_ORIGINS=["https://app.giftly.com","https://admin.giftly.com"]
```
And in `main.py`, enforce that `"*"` is rejected when `allow_credentials=True`:
```python
if "*" in settings.allowed_origins and allow_credentials:
    raise RuntimeError("CORS: cannot use wildcard origins with credentials")
```

#### [LOW] Content-Security-Policy includes `'unsafe-inline'` — **OPEN**
**File:** `src/main.py`

```python
"script-src 'self' 'unsafe-inline';"
```

`'unsafe-inline'` allows arbitrary inline `<script>` blocks, negating most XSS protection.

**Fix:** Remove `'unsafe-inline'`. Use nonces (`'nonce-<random>'`) for any legitimate inline scripts.

#### ✅ HTTPS forced — FIXED
`ForceHTTPSMiddleware` redirects HTTP to HTTPS. HSTS header set with configurable `max-age`.

#### ✅ Debug OTP endpoint gated by `settings.debug` — FIXED

---

### A06: Vulnerable and Outdated Components

#### [LOW] No automated dependency scanning — **OPEN**
There is no `pip audit`, `safety`, or Dependabot configuration in the repo.

**Fix:** Add `uv run pip-audit` to CI pipeline (`.github/workflows/ci.yml`) and/or enable GitHub Dependabot alerts.

#### [LOW] SQLAlchemy `declarative_base()` deprecated — **OPEN**
**File:** `src/utils/database/database.py`

`from sqlalchemy.ext.declarative import declarative_base` is deprecated since SQLAlchemy 2.0. The correct import is `from sqlalchemy.orm import declarative_base`.

**Fix:**
```python
from sqlalchemy.orm import declarative_base
Base = declarative_base()
```

---

### A07: Identification and Authentication Failures

#### ✅ Temp token correctly scoped
`get_current_user` rejects `payload.get("temp") == True`. New `get_profile_user` dependency accepts only temp tokens for `complete-profile`.

#### ✅ Refresh token rotation implemented
Old refresh token is invalidated on use. Tests confirm the old token is rejected after rotation.

#### [LOW] No upper bound validation on `access_token_expire_minutes` — **OPEN**
**File:** `src/utils/database/config.py`

If `ACCESS_TOKEN_EXPIRE_MINUTES` is misconfigured to a very large value (e.g., 525600 for 1 year), tokens become effectively non-expiring.

**Fix:**
```python
from pydantic import Field
access_token_expire_minutes: int = Field(default=15, ge=5, le=1440)
```

---

### A08: Software and Data Integrity Failures

#### ✅ Payment double-credit prevented — FIXED
Atomic `UPDATE WHERE status=PENDING` with `rowcount` guard.

#### ✅ Order claim race condition prevented — FIXED
Atomic `UPDATE WHERE status=NEW` with `rowcount` guard.

#### ✅ Chat media magic-byte validation — FIXED
Images: JPEG (`\xff\xd8\xff`) and PNG (`\x89PNG\r\n\x1a\n`) validated. Videos: box-type check (`ftyp`, `mdat`, etc.) + MP4 duration parser validates max 30 seconds.

---

### A09: Security Logging and Monitoring Failures

#### [MEDIUM] No audit log for sensitive admin actions — **OPEN**
Actions like courier approval, wallet credits, and invoice creation lack structured audit records. If a wallet is credited fraudulently, there is no immutable log trail.

**Fix:** Create an `AuditLog` model and write entries for: courier approval/rejection, admin wallet credits, invoice creation/modification, order cancellation.

#### [MEDIUM] Payment webhook not logged with source IP — **OPEN**
**File:** `src/routers/payments.py`

Successful and failed webhook deliveries are not logged with IP, timestamp, and payload hash. This makes forensic analysis after fraud impossible.

**Fix:**
```python
logging.info(
    "paylink_callback received",
    extra={"transaction_no": transaction_no, "status": paylink_status,
           "client_ip": request.client.host if request.client else "unknown"}
)
```

#### [LOW] No alerting on repeated failed OTP attempts — **OPEN**
Failed OTP verifications are not logged at WARNING level or forwarded to an alerting system. A brute-force attempt against a specific phone number is invisible.

**Fix:** `logging.warning("OTP verification failed for %s", normalized_phone)` with integration into your monitoring system.

---

### A10: Server-Side Request Forgery (SSRF)

#### ✅ Paylink client uses hardcoded base URL — Not vulnerable
`BASE_URL = "https://api.paylink.sa"` is hardcoded in `src/utils/clients/paylink.py`. Users cannot influence the target URL.

#### ✅ Storage client uses configured endpoint — Not vulnerable
boto3 uses `settings.storage_endpoint_url`; the value comes from env, not user input.

#### ✅ Media URLs stored, not fetched — Not vulnerable
`media_url` returned by `upload_media()` is stored in DB. The API never fetches URLs supplied by users.

---

## Summary Table

| # | Severity | Status | Issue | File(s) |
|---|---|---|---|---|
| 1 | **CRITICAL** | ✅ Fixed | Unauthenticated `complete-profile` | `auth.py` |
| 2 | **CRITICAL** | ✅ Fixed | IDOR on `GET /invoices/{id}` | `invoices.py` |
| 3 | **CRITICAL** | ✅ Fixed | Double-spend in payment callback | `payments.py` |
| 4 | **CRITICAL** | 🔴 Open | No webhook signature on Paylink callback | `payments.py` |
| 5 | **HIGH** | ✅ Fixed | No role check on `assign_order` | `orders.py` |
| 6 | **HIGH** | ✅ Fixed | SVG upload XSS in order images | `orders.py` |
| 7 | **HIGH** | ✅ Fixed | SVG upload XSS in chat images | `chat.py` |
| 8 | **HIGH** | ✅ Fixed | Stored XSS in WebSocket chat | `main.py` |
| 9 | **HIGH** | ✅ Fixed | `accept_order` race condition | `orders.py` |
| 10 | **HIGH** | ✅ Fixed | `cancel_order` payment not invalidated | `orders.py` |
| 11 | **HIGH** | ✅ Fixed | Predictable PDF temp files | `invoices.py` |
| 12 | **HIGH** | 🟡 Partial | In-memory rate limit (multi-worker) | `auth.py` |
| 13 | **HIGH** | ✅ Fixed | `dev/otp` always registered | `auth.py` |
| 14 | **HIGH** | 🔴 Open (mitigated) | Admin Basic auth over HTTP | `main.py` |
| 15 | **HIGH** | 🔴 Open | Non-constant-time OTP comparison | `auth.py` |
| 16 | **MEDIUM** | ✅ Fixed | No max amount on wallet charge | `wallets.py` |
| 17 | **MEDIUM** | ✅ Fixed | No max amount on admin wallet charge | `admin.py` |
| 18 | **MEDIUM** | ✅ Fixed | `CourierBalanceAddition` skipped (enum) | `orders.py` |
| 19 | **MEDIUM** | ✅ Fixed | `balance_before` wrong under concurrency | `orders.py` |
| 20 | **MEDIUM** | ✅ Fixed | Exception details in 502 responses | `payments.py`, `wallets.py`, `chat.py` |
| 21 | **MEDIUM** | ✅ Fixed | Untrusted invoice fields in WebSocket | `main.py` |
| 22 | **MEDIUM** | ✅ Fixed | Untrusted invoice amounts / system msgs in REST | `chat.py` |
| 23 | **MEDIUM** | ✅ Fixed | OTP rate limit on un-normalized phone | `auth.py` |
| 24 | **MEDIUM** | ✅ Fixed | Unbounded `push_token` length | `auth.py` |
| 25 | **MEDIUM** | ✅ Fixed | bcrypt DoS on every admin static asset | `main.py` |
| 26 | **MEDIUM** | ✅ Partial | PII in `order.comments` (name removed) | `orders.py` |
| 27 | **MEDIUM** | 🔴 Open | CORS defaults to wildcard with credentials | `main.py`, `config.py` |
| 28 | **MEDIUM** | 🔴 Open | Courier locked out of invoice by DB ID | `invoices.py` |
| 29 | **MEDIUM** | 🔴 Open | No audit log for sensitive admin actions | all routers |
| 30 | **MEDIUM** | 🔴 Open | Webhook not logged with source IP/payload | `payments.py` |
| 31 | **LOW** | ✅ Fixed | Payment gateway `str(e)` in 502 | `payments.py` |
| 32 | **LOW** | 🔴 Open | No rate limit on `/paylink-callback` | `payments.py` |
| 33 | **LOW** | 🔴 Open | `is_verified` in JWT can be stale | `auth.py` |
| 34 | **LOW** | ✅ Fixed | Pydantic V1 validators — deprecation | `schemas/**` |
| 35 | **LOW** | ✅ Fixed | No HTML escape in REST chat messages | `chat.py` |
| 36 | **LOW** | ✅ Fixed | Any user can post `system` messages | `chat.py` |
| 37 | **LOW** | ✅ Fixed | No max content length in REST chat | `chat.py` |
| 38 | **LOW** | 🔴 Open | CSP includes `'unsafe-inline'` | `main.py` |
| 39 | **LOW** | 🔴 Open | No automated dependency scanning | CI config |
| 40 | **LOW** | 🔴 Open | `declarative_base()` deprecated (SQLAlchemy 2.0) | `database.py` |
| 41 | **LOW** | 🔴 Open | No upper bound on `ACCESS_TOKEN_EXPIRE_MINUTES` | `config.py` |
| 42 | **LOW** | 🔴 Open | No alerting on repeated failed OTP attempts | `auth.py` |
| 43 | **LOW** | 🔴 Open | No rate limit on public enumeration endpoints | `cities.py`, `couriers.py` |

---

## No Vulnerabilities Found In

- **SQL Injection:** All queries use SQLAlchemy ORM with parameterized bindings.
- **Command Injection:** No `os.system`, `subprocess`, or `eval()` usage.
- **Path Traversal:** File paths constructed from controlled values.
- **SSRF:** External HTTP calls only to Paylink and configured SMTP — URLs not user-controlled.
- **Insecure Deserialization:** No `pickle`, `yaml.load`, or similar.
- **CSRF:** Not applicable — API uses JWT Bearer tokens in `Authorization` header, not cookies.
- **Secrets in code:** No hardcoded secrets; all credentials loaded from `Settings`.
- **JWT algorithm confusion:** `algorithms=["HS256"]` pinned in all `jwt.decode()` calls.

---

## Open Items Priority

1. **CRITICAL #4** — Add Paylink webhook signature verification or re-validate with Paylink API
2. **HIGH #15** — Use `secrets.compare_digest()` for OTP comparison
3. **HIGH #12** — Migrate OTP rate limiting to Redis for multi-worker correctness
4. **MEDIUM #27** — Set explicit `ALLOWED_ORIGINS` in production; reject wildcard with credentials
5. **MEDIUM #28** — Fix courier access to invoice by DB ID endpoint
6. **MEDIUM #29** — Add audit logging for courier approval, wallet credits, invoice changes
7. **MEDIUM #30** — Log webhook source IP and payload hash
8. **LOW #38** — Remove `'unsafe-inline'` from CSP; use nonces
9. **LOW #39** — Add `pip-audit` to CI
10. **LOW #40** — Fix `declarative_base()` import to `sqlalchemy.orm`
