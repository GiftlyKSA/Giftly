# Giftly Backend — Open Security Findings

> Last updated: 2026-04-24
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

`_phone_timestamps`, `_verify_timestamps`, and all `make_ip_rate_limiter` closures are per-process dicts. With N uvicorn workers or K8s replicas the effective rate limit multiplies by N — OTP brute-force and endpoint scraping are under-throttled in production.

**Pending approval to fix.** Proposed fix: replace with Redis atomic counters (`INCR` + `EXPIRE`). Redis URL is already in settings.

---

### Admin Basic Auth over plain HTTP
**Files:** `src/main.py` (ForceHTTPSMiddleware)

Admin credentials travel Base64-encoded in every request header. `ForceHTTPSMiddleware` redirects plain HTTP at the app layer, but if TLS terminates at a load balancer that forwards HTTP internally (common setup), credentials are exposed on the internal network.

**Pending approval to fix.** Proposed fix: enforce TLS at the infrastructure level and/or switch admin auth to a token-based scheme.

---

## Priority Order

| Priority | Severity | Finding | File |
|---|---|---|---|
| 1 | **HIGH** | In-memory rate limits bypassed multi-worker | `auth.py`, `rate_limit.py` |
| 2 | **HIGH** | Admin Basic Auth plain-HTTP risk | infra / `main.py` |
