# Security Audit
> Last updated: 2026-04-24. All previous findings have been resolved.

---

## Status: All findings resolved

| ID | Severity | Description | Status |
|---|---|---|---|
| S-01 | MEDIUM | Missing Paylink webhook HMAC signature verification | ✅ Fixed |
| S-02 | MEDIUM | Race condition in `update_order_status` (non-atomic write) | ✅ Fixed |
| S-03 | MEDIUM | No rate limit on `POST /invoices/verify-coupon` | ✅ Fixed |
| S-04 | LOW | Float precision for Paylink API currency amounts | ✅ Fixed |

---

## Resolved

### S-01 — Paylink webhook HMAC signature verification
**File:** `src/routers/payments.py` — `paylink_callback`  
**Fix:** Added HMAC-SHA256 signature verification using `hmac.compare_digest`. The signing secret is read from `settings.paylink_webhook_secret` (`PAYLINK_WEBHOOK_SECRET` env var). Verification is skipped if the secret is not configured, preserving backward compatibility.

### S-02 — Race condition in `update_order_status`
**File:** `src/routers/orders.py` — `update_order_status`  
**Fix:** Replaced the read-then-write pattern with a conditional `UPDATE ... WHERE order_id = ? AND status = <current>`. Returns HTTP 409 if `rowcount == 0` (concurrent modification detected).

### S-03 — Rate limit on `POST /invoices/verify-coupon`
**File:** `src/routers/invoices.py` — `verify_coupon`  
**Fix:** Added `_: None = Depends(_coupon_rate_limit)` backed by `settings.rate_limit_coupon_verify_per_minute` (`RATE_LIMIT_COUPON_VERIFY_PER_MINUTE` env var, default 10/min per IP).

### S-04 — Float precision for Paylink API amounts
**Files:** `src/routers/payments.py`, `src/routers/wallets.py`  
**Fix:** Replaced raw float division with `round(amount / 100, 2)` / `round(amount_sar, 2)` for all values sent to the Paylink API.

---

## Open items

_None._
