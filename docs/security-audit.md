# Giftly Backend — Open Security Findings

> Last updated: 2026-04-22
> Scope: `src/` — all routers, middleware, utils, models, schemas
> Only unfixed findings are listed.

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

Successful and failed webhook deliveries are not logged with payload hash, making post-fraud forensics incomplete. *(Source IP logging is done; payload hash is missing.)*

**Fix:**
```python
import hashlib, json
payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
logging.info("paylink_callback payload_hash=%s", payload_hash)
```

---

## LOW

### `is_verified` JWT claim can become stale
If an admin revokes a user's verified status, their existing access token continues to claim `is_verified=True` until expiry. Acceptable for short-lived tokens; document as known risk.

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

### No alerting on repeated failed OTP attempts
Failed OTP verifications are not logged at WARNING level. A brute-force attempt is invisible.

**Fix:** `logging.warning("OTP verification failed for %s", normalized_phone)` with monitoring integration.

---

### No rate limit on public enumeration endpoints
`GET /cities/`, `GET /couriers/available/{city_id}`, `GET /promocodes/active/list` have no rate limiting.

**Fix:** Add per-IP rate limiting via `slowapi` or Redis counters.

---

## Priority Order

| Priority | Severity | Finding | File |
|---|---|---|---|
| 1 | **CRITICAL** | No Paylink webhook signature verification | `payments.py` |
| 2 | **HIGH** | Non-constant-time OTP comparison | `auth.py` |
| 3 | **HIGH** | In-memory OTP rate limit (multi-worker) | `auth.py` |
| 4 | **MEDIUM** | CORS wildcard with credentials | `main.py`, `config.py` |
| 5 | **MEDIUM** | No audit log for sensitive admin actions | all routers |
| 6 | **MEDIUM** | Webhook payload hash not logged | `payments.py` |
| 7 | **LOW** | CSP `'unsafe-inline'` | `main.py` |
| 8 | **LOW** | No dependency scanning | CI config |
| 9 | **LOW** | `declarative_base()` deprecated | `database.py` |
| 10 | **LOW** | No alerting on failed OTP | `auth.py` |
| 11 | **LOW** | No rate limit on enumeration endpoints | `cities.py`, `couriers.py` |
| 12 | **LOW** | `is_verified` JWT claim can be stale | `auth.py` |
