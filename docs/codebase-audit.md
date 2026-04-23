# Codebase Audit — New Findings
> Generated: 2026-04-24. Covers logic issues, performance, improvements, and suggestions. Only findings NOT yet addressed are listed.

---

## Logic Issues

### L-01 — `update_order_status` uses non-atomic write (race condition)
**File:** `src/routers/orders.py` — `update_order_status`  
**Severity:** Medium  
**Issue:** Reads current status, validates transition, then writes with `order.status = new_status`. Two concurrent requests can both pass validation and produce an illegal state.  
**Fix:** Use a conditional `UPDATE ... WHERE status = <current>` and check `rowcount == 0` to detect a lost race (same pattern as `accept_order`).

---

### L-02 — Missing rate limit on `POST /invoices/verify-coupon`
**File:** `src/routers/invoices.py` — `verify_coupon`  
**Severity:** Medium  
**Issue:** Authenticated users can call this endpoint at unlimited frequency to enumerate valid promo codes.  
**Fix:** Apply `make_ip_rate_limiter(10, 60)` as a dependency.

---

## Performance

### P-01 — No pagination on `GET /chat/conversations`
**File:** `src/routers/chat.py` — `get_user_conversations`  
**Severity:** Low  
**Issue:** The endpoint fetches all conversations for a user with no `skip`/`limit`. A user with many conversations causes a large DB query and response payload.  
**Fix:** Add `skip: int = Query(0, ge=0)` and `limit: int = Query(50, ge=1, le=200)` parameters.

---

## Improvements

### I-01 — Float SAR value sent to Paylink instead of rounded decimal
**File:** `src/routers/payments.py` line 172, `src/routers/wallets.py` line 86  
**Severity:** Low  
**Issue:** `payment_data.amount / 100` and `float(amount_sar)` may produce floating-point imprecision in the JSON body sent to Paylink.  
**Fix:** Use `round(payment_data.amount / 100, 2)` in payments.py and `round(amount_sar, 2)` in wallets.py for the API payload.

---

### I-02 — Typo in admin wallet charge response
**File:** `src/routers/admin.py` line 177  
**Severity:** Low  
**Issue:** `f"Charged {amount} halaym to user {user_id}"` — "halaym" is not a standard English or Arabic term; should be "halalas".  
**Fix:** `f"Charged {amount} halalas to user {user_id}"`

---

### I-03 — `paylink_callback` swallows exceptions silently in invoice processing
**File:** `src/routers/payments.py` — `paylink_callback`, lines 304–316  
**Severity:** Low  
**Issue:** If `_mark_invoice_paid` raises inside the callback, the exception propagates without logging the payment ID or invoice ID, making failures hard to trace.  
**Fix:** Wrap the block in `try/except Exception as e: logging.error("paylink_callback invoice processing failed: payment=%s invoice=%s error=%s", payment.id, invoice.id, e)`.

---

## Suggestions

### SG-01 — Consider a Pydantic schema for `paylink_callback` payload
**File:** `src/routers/payments.py` — `paylink_callback`  
**Issue:** `payload: dict` accepts arbitrary JSON. A Pydantic model would make expected fields explicit, reject unexpected shapes, and improve documentation.  
**Suggested schema fields:** `transactionNo`, `orderStatus`, `orderNumber`, `status`.
