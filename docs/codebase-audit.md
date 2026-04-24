# Codebase Audit
> Scope: `src/` — bugs, performance issues, and logic improvements.  
> Generated: 2026-04-24.

---

## Bugs

### B-01 — Discount calculated with `int()` truncation instead of rounding
**Files:** `src/routers/payments.py`, `src/routers/invoices.py`  
**Severity:** Medium  
**Issue:** Discount amounts are computed as `int(base * coupon.percentage / 100)`. Integer truncation silently rounds down. Example: an invoice of 333 halalas at 10% should produce 33.3, which truncates to 33 instead of rounding to the correct value. Over many transactions this systematically under-discounts customers.  
**Fix:** Use `round(base * coupon.percentage / 100)` (rounds to nearest integer halala).

### B-02 — Chat message length checked before HTML escaping
**File:** `src/routers/chat.py` — `send_message`  
**Severity:** Low  
**Issue:** `len(content.strip()) > settings.chat_msg_max_chars` is evaluated on the raw input. After `html.escape()`, characters like `<` become `&lt;` (3× longer). A message exactly at the character limit can exceed it after escaping, producing a stored message longer than the configured maximum.  
**Fix:** Move the length check to after `html.escape()`:
```python
content = html.escape(content.strip())
if len(content) > settings.chat_msg_max_chars:
    raise HTTPException(400, ...)
```

### B-03 — WebSocket `send_message` emits before DB commit
**File:** `src/main.py` — WebSocket handler  
**Severity:** Low  
**Issue:** `await db.commit()` is called before `await db.refresh(new_message)`, which is correct. But the broadcast happens immediately after, before confirming the commit succeeded. If the commit fails after the broadcast, connected clients receive a message that was never actually persisted.  
**Fix:** Wrap the broadcast inside a `try/except` and only broadcast after confirming the commit completed successfully, or use a post-commit hook pattern.

### B-04 — Courier fee not validated before crediting in `complete_order`
**File:** `src/routers/orders.py` — `complete_order`  
**Severity:** Low  
**Issue:** `courier_fee = invoice.courier_fee` is used to credit the courier's wallet without checking it is positive. An invoice with `courier_fee = 0` would complete successfully while crediting nothing, leaving the courier unpaid silently.  
**Fix:** Assert `invoice.courier_fee > 0` before completing the order, or return an informative error if the fee is zero.

---

## Performance

### P-01 — PDF generation blocks the event loop
**File:** `src/routers/invoices.py` — `generate_invoice_pdf`, `download_invoice_pdf`, `download_invoice_pdf_by_id`  
**Severity:** Medium  
**Issue:** `generate_invoice_pdf` uses ReportLab, which is CPU-bound and synchronous. It runs directly in the async request handler, blocking the entire event loop for the duration of PDF assembly. Under concurrent requests, all other requests stall.  
**Fix:** Offload to a thread pool:
```python
import asyncio, functools
loop = asyncio.get_event_loop()
pdf_buffer = await loop.run_in_executor(None, functools.partial(generate_invoice_pdf, invoice, order))
```

### P-02 — Missing composite database indexes for common query patterns
**Files:** `src/models/payment.py`, `src/models/order.py`  
**Severity:** Medium  
**Issue:**  
- `Payment` has separate indexes on `user_id` and `status` but no composite `(user_id, status)` or `(user_id, created_at)`. Queries like "all pending payments for user X" require a full scan of user X's payments.  
- `Order` queries courier active orders by `(assigned_to_user_id, status)` without a composite index on those columns.  
**Fix:** Add composite indexes in the model `__table_args__`:
```python
Index("idx_payment_user_status", "user_id", "status"),
Index("idx_order_courier_status", "assigned_to_user_id", "status"),
```

### P-03 — `get_courier_stats` can produce large aggregations
**File:** `src/routers/orders.py` — `get_courier_stats`  
**Severity:** Low  
**Issue:** Today's earnings are computed by summing all `invoice.courier_fee` for invoices paid today. As a courier completes more orders over time, the date range query could grow, though it is bounded to `today`. The query loads all matching rows into Python before summing instead of using a `func.sum()` at the DB level.  
**Fix:** Push the summation to the database:
```python
from sqlalchemy import func
result = await db.execute(
    select(func.sum(Invoice.courier_fee))
    .join(Order, Invoice.order_id == Order.id)
    .where(Order.assigned_to_user_id == current_user.id, ...)
)
total = result.scalar() or 0
```

### P-04 — No database statement timeout configured
**File:** `src/utils/database/database.py`  
**Severity:** Low  
**Issue:** If a query hangs (slow query, lock contention), the async task holds the connection indefinitely. There is no per-statement timeout at the asyncpg/SQLAlchemy level.  
**Fix:** Add `connect_args={"command_timeout": 30}` (seconds) to `create_async_engine` for PostgreSQL, or set `statement_timeout` in the database session.

### P-05 — SQLAdmin views likely trigger N+1 queries
**File:** `src/utils/admin/admin.py`  
**Severity:** Low  
**Issue:** SQLAdmin `ModelView` classes don't override `column_details_list` or add `selectinload` for relationships. Viewing a list of orders or invoices with relational columns (user name, city name) will fire one query per row.  
**Fix:** Add `column_formatters` that join eagerly, or override `get_query` to add `selectinload` on the relationships used in `column_list`.

---

## Logic Issues

### LG-01 — Order status state machine is inconsistent across endpoints
**File:** `src/routers/orders.py`  
**Severity:** Medium  
**Issue:** `_COURIER_TRANSITIONS` governs the generic `PUT /orders/{id}/status` endpoint. However, `accept_order`, `complete_order`, and `confirm_delivery` bypass this dict entirely and perform their own status writes. This means:
- The same order can be moved to `DONE` via `complete_order` without the state machine knowing.
- Transitions not in `_COURIER_TRANSITIONS` silently fail via the generic endpoint but succeed via dedicated endpoints, creating confusing double paths.  
**Fix:** Define a single authoritative transition table that all endpoints reference. Dedicated endpoints can still exist but should invoke a shared `transition_order_status(order, new_status, db)` helper that enforces the machine.

### LG-02 — Courier balance addition `balance_before` read is not atomic
**File:** `src/routers/orders.py` — `complete_order`  
**Severity:** Low  
**Issue:** `balance_before = wallet.balance` is read from the Python ORM object before the atomic `UPDATE wallets SET balance = balance + :fee`. If two orders complete concurrently, both reads get the same `balance_before` snapshot, making the audit trail entry incorrect (not wrong money, but wrong logged starting balance).  
**Fix:** Read `balance_before` from the RETURNING clause of the UPDATE, or use `SELECT ... FOR UPDATE` to lock the row before reading.

### LG-03 — Order image count not enforced at the router level
**File:** `src/routers/orders.py` — `create_order`  
**Severity:** Low  
**Issue:** The form accepts `image1`, `image2`, `image3` as optional but there is no check that at least one image is provided when the order description is empty. A completely empty order (no description, no images) can be submitted.  
**Fix:** Require either a non-empty description or at least one image in the validation logic.

### LG-04 — `complete_order` does not verify invoice status before crediting courier
**File:** `src/routers/orders.py` — `complete_order`  
**Severity:** Low  
**Issue:** The check `invoice.status != InvoiceStatus.PAID` correctly blocks completion for unpaid invoices. However, if someone externally changes the invoice status to `REFUNDED` between the check and the wallet credit, the courier still gets paid. This is an edge case but possible if admin manually updates the DB.  
**Fix:** Use a conditional UPDATE on the Invoice row (WHERE status = PAID) to confirm its state atomically before crediting the wallet.

### LG-05 — No validation that `assigned_to_user_id` is a courier in `assign_order` (admin)
**File:** `src/routers/admin.py` — assignment endpoint (if present) / `src/routers/orders.py`  
**Severity:** Low  
**Issue:** When an admin assigns an order to a user, the check verifies the role, but does not verify the courier has an approved profile in the correct city. An admin can assign an order to an unapproved or out-of-city courier.  
**Fix:** Add a check that the target courier's `CourierProfile.is_approved == True` and `city_id == order.city_id`.

---

## Code Quality

### CQ-01 — Inconsistent logger usage across routers
**Files:** Multiple routers  
**Issue:** `payments.py` uses a module-level `logger = logging.getLogger(__name__)`. All other routers call `logging.error(...)` directly on the root logger. This means log records from other routers show `root` as the logger name instead of the module name, making log filtering harder.  
**Fix:** Add `logger = logging.getLogger(__name__)` at the top of every router that logs, and replace `logging.X(...)` calls with `logger.X(...)`.

### CQ-02 — WebSocket room names are magic strings in multiple files
**Files:** `src/main.py`, `src/routers/orders.py`, `src/utils/websocket/websocket_events.py`  
**Issue:** Room name patterns (`"user_{id}"`, `"couriers_city_{id}"`, `"chat_{id}"`) are duplicated as f-strings in at least three files. A typo in one location would silently break room joining without any error.  
**Fix:** Define a central constants module (e.g., `src/utils/websocket/rooms.py`):
```python
def user_room(user_id: int) -> str: return f"user_{user_id}"
def city_couriers_room(city_id: int) -> str: return f"couriers_city_{city_id}"
def chat_room(conversation_id: int) -> str: return f"chat_{conversation_id}"
```

### CQ-03 — Response shape inconsistency across endpoints
**Files:** Multiple routers  
**Issue:** Some endpoints return `{"message": "..."}`, others `{"detail": "..."}`, others a flat dict. Clients need to handle multiple shapes.  
**Fix:** Standardize success responses on `{"message": "..."}` for command endpoints (non-entity returns) and `{"detail": "..."}` only for errors (FastAPI default). Entity endpoints return the entity schema directly.
