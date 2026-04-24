# Codebase Audit
> Last updated: 2026-04-24. All previous findings have been resolved.

---

## Status: All findings resolved

| ID | Severity | Description | Status |
|---|---|---|---|
| L-01 | Medium | Non-atomic order status write (race condition) | ✅ Fixed |
| L-02 | Medium | No rate limit on `POST /invoices/verify-coupon` | ✅ Fixed |
| P-01 | Low | No pagination on `GET /chat/conversations` | ✅ Fixed |
| I-01 | Low | Float precision for Paylink API amounts | ✅ Fixed |
| I-02 | Low | Typo "halaym" in admin wallet charge response | ✅ Fixed |
| I-03 | Low | `paylink_callback` swallowed exceptions silently | ✅ Fixed |
| SG-01 | Info | No Pydantic schema for `paylink_callback` payload | ✅ Fixed |

---

## Resolved

### L-01 — Non-atomic order status write
**File:** `src/routers/orders.py` — `update_order_status`  
**Fix:** Conditional `UPDATE ... WHERE status = <current>` with `rowcount == 0` check. Returns HTTP 409 on concurrent modification.

### L-02 — Rate limit on `/invoices/verify-coupon`
**File:** `src/routers/invoices.py` — `verify_coupon`  
**Fix:** `_coupon_rate_limit` dependency reads `settings.rate_limit_coupon_verify_per_minute` (env: `RATE_LIMIT_COUPON_VERIFY_PER_MINUTE`, default 10/min per IP).

### P-01 — Pagination on `GET /chat/conversations`
**File:** `src/routers/chat.py` — `get_user_conversations`  
**Fix:** Added `skip: int = Query(0, ge=0)` and `limit: int = Query(20, ge=1)` parameters. Limit is capped by `settings.chat_conversations_max_limit` (env: `CHAT_CONVERSATIONS_MAX_LIMIT`, default 100).

### I-01 — Float precision for Paylink API amounts
**Files:** `src/routers/payments.py`, `src/routers/wallets.py`  
**Fix:** `round(amount / 100, 2)` and `round(amount_sar, 2)` used for all Paylink API calls.

### I-02 — "halaym" typo in admin wallet charge response
**File:** `src/routers/admin.py` — `admin_charge_wallet`  
**Fix:** Response message now reads `f"Successfully charged {amount / 100:.2f} SAR to wallet for user {user_id}"`.

### I-03 — Silent exception swallowing in `paylink_callback`
**File:** `src/routers/payments.py` — `paylink_callback`  
**Fix:** Invoice processing block is wrapped in `try/except` with `logger.exception(...)` logging payment and invoice IDs.

### SG-01 — Pydantic schema for `paylink_callback` payload
**File:** `src/routers/payments.py`  
**Fix:** Added `PaylinkCallbackPayload(BaseModel)` with `extra = "allow"`. Fields: `transactionNo`, `orderNumber`, `orderStatus`, `status`.

---

## Open items

_None._
