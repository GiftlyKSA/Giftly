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

## HIGH

### In-memory rate limits bypassed in multi-worker deployments
**Files:** `src/routers/auth.py`, `src/utils/rate_limit.py`

`_phone_timestamps`, `_verify_timestamps`, and all `make_ip_rate_limiter` closures are per-process dicts. With N uvicorn workers or K8s replicas the effective rate limit multiplies by N. OTP brute-force and endpoint scraping are under-throttled.

**Fix:** Replace with Redis atomic counters (`INCR` + `EXPIRE`). The Redis URL is already in settings.

---

### Admin Basic Auth — mitigated, not eliminated
Basic-auth credentials travel Base64-encoded in every request header. `ForceHTTPSMiddleware` and HSTS mitigate this in production. **Risk remains** if HTTP is reachable at the infrastructure level (e.g., internal load-balancer → app in plain HTTP).

**Fix:** Enforce TLS termination at the infrastructure level; reject plain-HTTP at the load balancer, not just at the app.

---

## MEDIUM

### No audit log model for sensitive admin actions
**Files:** `src/routers/admin.py`, `src/routers/orders.py`, `src/routers/invoices.py`

Actions like courier approval/rejection, admin wallet credits, and order cancellation are logged via `logging.info/warning` (ephemeral), but there is no `AuditLog` database table for immutable, queryable records. Forensic investigations require parsing log files.

**Fix:** Create an `AuditLog` model with `actor_id`, `action`, `target_type`, `target_id`, `detail`, `created_at`. Write entries for: courier approval, admin wallet credits, invoice creation, order cancellation.

---

### No dependency vulnerability scanning
No `pip audit`, `safety`, or Dependabot configuration in the repository.

**Fix:** Add `uv run pip-audit` step to `.github/workflows/ci.yml` and/or enable GitHub Dependabot alerts for the repo.

---

## LOW

### `is_verified` JWT claim can become stale
**File:** `src/utils/auth/auth.py`

If an admin revokes a user's verified status, their existing access token continues to claim `is_verified=True` until token expiry (default 30 min). Acceptable for short-lived tokens; documented as known risk.

**Mitigation:** Keep `ACCESS_TOKEN_EXPIRE_MINUTES` short (≤ 30). For immediate revocation, move to a token blocklist backed by Redis.

---

### Duplicate invoice creation endpoints
**Files:** `src/routers/invoices.py`

`POST /invoices/` and `POST /invoices/courier/create` are now functionally identical after auth was added to the generic route. Duplicate endpoints enlarge the attack surface and cause maintenance confusion.

**Fix:** Remove one route (suggest keeping `/courier/create` for clarity).

---

## Priority Order

| Priority | Severity | Finding | File |
|---|---|---|---|
| 1 | **HIGH** | In-memory rate limits bypassed multi-worker | `auth.py`, `rate_limit.py` |
| 2 | **HIGH** | Admin Basic Auth plain-HTTP risk | infra / `main.py` |
| 3 | **MEDIUM** | No audit log model for admin actions | `admin.py`, routers |
| 4 | **MEDIUM** | No dependency vulnerability scanning | CI config |
| 5 | **LOW** | `is_verified` JWT claim stale | `auth.py` |
| 6 | **LOW** | Duplicate invoice creation endpoints | `invoices.py` |
