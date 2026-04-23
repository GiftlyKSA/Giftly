# Security Audit — New Findings
> Generated: 2026-04-24. Only findings NOT yet addressed in the codebase are listed here.

---

## HIGH

_None identified._

---

## MEDIUM

### S-01 — Missing Paylink webhook signature verification
**File:** `src/routers/payments.py` — `paylink_callback`  
**Issue:** The callback endpoint re-validates the payment status with the Paylink API (good), but it does not verify an HMAC signature on the raw webhook payload. If Paylink's re-validation is unreachable (network issue, test mode), a spoofed POST can still pass through to the atomic update block.  
**Fix:** Verify a Paylink-provided signature header (e.g. `X-Paylink-Signature`) using `hmac.compare_digest` before touching the database. Store the signing secret in `settings`.

---

### S-02 — Race condition in `update_order_status` (non-atomic transition)
**File:** `src/routers/orders.py` — `update_order_status`  
**Issue:** The function reads the current order status, validates the transition via `_COURIER_TRANSITIONS`, then writes the new status with a plain `order.status = new_status`. Two concurrent requests from the same courier can both pass the read-side check and then both write, causing the order to skip a status step.  
**Fix:** Replace the read-then-write with a conditional `UPDATE ... WHERE order_id = ? AND status = <expected_current>` (same pattern used in `accept_order`). Check `rowcount == 0` to detect a lost race.

---

### S-03 — Missing rate limit on `/invoices/verify-coupon`
**File:** `src/routers/invoices.py` — `verify_coupon` (POST `/invoices/verify-coupon`)  
**Issue:** An authenticated attacker can brute-force valid promo codes at unlimited speed. No per-IP or per-user rate limit is applied to this endpoint.  
**Fix:** Add `_: None = Depends(make_ip_rate_limiter(10, 60))` (or a tighter per-user limit via Redis) to the endpoint signature.

---

## LOW

### S-04 — Float passed to Paylink API for currency amounts
**File:** `src/routers/payments.py` line 172 — `create_payment`  
**Issue:** `"amount": payment_data.amount / 100` converts integer halalas to a float SAR value for the external Paylink API call. Python float division can produce imprecise representations (e.g. 0.30000000000000004) that differ from what Paylink expects.  
**Fix:** Use `Decimal` or format as a rounded string: `"amount": round(payment_data.amount / 100, 2)`. The same applies in `initiate_wallet_charge` (wallets.py line 86).
