# Giftly Backend — Open Security Findings

> Last updated: 2026-04-22
> Scope: `src/` — all routers, middleware, utils, models, schemas
> Only unfixed findings are listed. 28 findings have been resolved and removed.

---

## Severity Key

| Severity | Definition |
|---|---|
| **CRITICAL** | Exploitable without privilege, leads to account takeover, data theft, or financial fraud |
| **HIGH** | Requires low privilege or specific conditions, significant business impact |
| **MEDIUM** | Requires moderate effort or conditions, partial impact |
| **LOW** | Defence-in-depth issue, minimal direct impact |

---

## CRITICAL

### No webhook signature verification on `POST /payments/paylink-callback`
**File:** `src/routers/payments.py`

The callback endpoint accepts any POST payload and trusts the `orderStatus` field directly. An unauthenticated attacker can craft a fake "paid" webhook to mark any payment as completed, credit wallets, and mark invoices as paid without an actual fund transfer.

**Fix:** Re-validate transaction status directly with the Paylink API before updating state:
```python
async with PaylinkClient(settings.paylink_api_key) as paylink:
    live = await paylink.get_invoice(transaction_no)
    if live.get("orderStatus") != "paid":
        return {"message": "Status mismatch — ignoring"}
```

---

## HIGH

### In-memory OTP rate limit bypassed in multi-worker deployments
**File:** `src/routers/auth.py`

`_phone_timestamps` and `_verify_timestamps` are per-process dicts. With N uvicorn workers or replicas, the effective rate limit is N × 3 requests.

**Fix:** Replace with Redis atomic counters (`INCR` + `EXPIRE`). The Redis URL is already in settings.

---

### Admin Basic Auth credentials travel in Base64 — mitigated
`ForceHTTPSMiddleware` and HSTS headers mitigate this in production. Ensure HTTPS is enforced at the infrastructure level; no plaintext HTTP allowed.

---

### Non-constant-time OTP comparison
**File:** `src/routers/auth.py`

```python
if user.otp != otp_data.otp:
```

Python `!=` on strings is not constant-time. Statistical timing analysis can leak OTP digits.

**Fix:**
```python
import secrets
if not secrets.compare_digest(user.otp or "", otp_data.otp or ""):
    raise HTTPException(status_code=400, detail="Invalid OTP")
```

---

## MEDIUM

### Courier locked out of invoice by DB ID endpoint
**File:** `src/routers/invoices.py`

`GET /invoices/id/{invoice_db_id}` only checks `Order.created_by_user_id == current_user.id`, locking out the assigned courier. The string-ID endpoint `/invoices/{invoice_id}` correctly allows both.

**Fix:** Add `or_(Order.created_by_user_id == current_user.id, Order.assigned_to_user_id == current_user.id)` to the secondary endpoint's ownership filter.

---

### CORS defaults to wildcard with credentials
**File:** `src/utils/database/config.py`, `src/main.py`

`allowed_origins: list[str] = ["*"]` combined with `allow_credentials=True` allows any website to make authenticated cross-origin requests on behalf of users.

**Fix:** Set explicit origins in production `.env`:
```
ALLOWED_ORIGINS=["https://app.giftly.com","https://admin.giftly.com"]
```

---

### No audit log for sensitive admin actions
Actions like courier approval/rejection, admin wallet credits, and invoice modifications leave no immutable audit trail.

**Fix:** Create an `AuditLog` model and write entries for: courier approval, admin wallet credits, invoice creation/modification, order cancellation.

---

### Paylink webhook not logged with source IP
**File:** `src/routers/payments.py`

Successful and failed webhook deliveries are not logged with IP, timestamp, or payload hash, making post-fraud forensics impossible.

**Fix:**
```python
logging.info(
    "paylink_callback received",
    extra={"transaction_no": transaction_no, "status": paylink_status,
           "client_ip": request.client.host if request.client else "unknown"}
)
```

---

## LOW

### No rate limit on `POST /payments/paylink-callback`
The webhook endpoint is unauthenticated and rate-unlimited. A flood of garbage `transactionNo` values triggers a DB query per request.

**Fix:** Add IP allowlisting for Paylink's server IP ranges, or add `slowapi` rate limiting on this endpoint.

---

### `is_verified` JWT claim can become stale
If an admin revokes a user's verified status, their existing access token continues to claim `is_verified=True` until expiry. Acceptable for short-lived tokens; document as known risk.

**Fix (optional):** Re-check `is_verified` from DB in `get_current_user` for sensitive endpoints, or reduce token lifetime.

---

### CSP includes `'unsafe-inline'`
**File:** `src/main.py`

`'unsafe-inline'` in `script-src` allows arbitrary inline `<script>` blocks, negating most XSS protection.

**Fix:** Remove `'unsafe-inline'`. Use nonces for any legitimate inline scripts.

---

### No automated dependency scanning
No `pip audit`, `safety`, or Dependabot configuration in the repo.

**Fix:** Add `uv run pip-audit` to CI (`.github/workflows/ci.yml`) and/or enable GitHub Dependabot alerts.

---

### SQLAlchemy `declarative_base()` deprecated
**File:** `src/utils/database/database.py`

`from sqlalchemy.ext.declarative import declarative_base` is deprecated since SQLAlchemy 2.0.

**Fix:**
```python
from sqlalchemy.orm import declarative_base
```

---

### No upper bound on `ACCESS_TOKEN_EXPIRE_MINUTES`
**File:** `src/utils/database/config.py`

A misconfigured value (e.g., 525600) makes tokens effectively non-expiring.

**Fix:**
```python
from pydantic import Field
access_token_expire_minutes: int = Field(default=15, ge=5, le=1440)
```

---

### No alerting on repeated failed OTP attempts
Failed OTP verifications are not logged at WARNING level. A brute-force attempt against a phone number is invisible.

**Fix:** `logging.warning("OTP verification failed for %s", normalized_phone)` with monitoring integration.

---

### No rate limiting on public enumeration endpoints
`GET /cities/`, `GET /couriers/available/{city_id}`, `GET /promocodes/active/list` have no rate limiting, allowing enumeration of users and couriers.

**Fix:** Add per-IP rate limiting via `slowapi` or Redis counters.

---

## Priority Order

| Priority | Severity | Finding | File |
|---|---|---|---|
| 1 | **CRITICAL** | No Paylink webhook signature verification | `payments.py` |
| 2 | **HIGH** | Non-constant-time OTP comparison | `auth.py` |
| 3 | **HIGH** | In-memory OTP rate limit (multi-worker) | `auth.py` |
| 4 | **MEDIUM** | CORS wildcard with credentials | `main.py`, `config.py` |
| 5 | **MEDIUM** | Courier locked out of invoice by DB ID | `invoices.py` |
| 6 | **MEDIUM** | No audit log for sensitive admin actions | all routers |
| 7 | **MEDIUM** | Webhook not logged with source IP | `payments.py` |
| 8 | **LOW** | CSP `'unsafe-inline'` | `main.py` |
| 9 | **LOW** | No dependency scanning | CI config |
| 10 | **LOW** | `declarative_base()` deprecated | `database.py` |
| 11 | **LOW** | No upper bound on token expiry config | `config.py` |
| 12 | **LOW** | No alerting on failed OTP | `auth.py` |
| 13 | **LOW** | No rate limit on enumeration endpoints | `cities.py`, `couriers.py` |
| 14 | **LOW** | No rate limit on `/paylink-callback` | `payments.py` |
| 15 | **LOW** | `is_verified` JWT claim can be stale | `auth.py` |
