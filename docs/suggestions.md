# Suggestions
> Ideas for improving code quality, architecture, features, and developer experience.  
> These are not bugs or security issues — they are opportunities to make the codebase better.

---

## Architecture

### A-01 — Centralize WebSocket room name constants
Room name strings (`"user_{id}"`, `"couriers_city_{id}"`, `"chat_{id}"`) are inline f-strings in `main.py`, `orders.py`, and `websocket_events.py`. A single `src/utils/websocket/rooms.py` module with helper functions would eliminate the duplication and make future renames safe.

### A-02 — Extract a shared `transition_order_status` helper
`accept_order`, `complete_order`, `confirm_delivery`, and `update_order_status` all write `order.status` independently. Centralizing this into one function that accepts `(order, new_status, db)`, validates the transition, performs the atomic UPDATE, and emits the WebSocket event would reduce duplication and ensure consistency.

### A-03 — Move SQLAdmin view definitions to `src/admin_views.py`
`src/utils/admin/admin.py` is a presentation layer (SQLAdmin view configuration), not a utility. It belongs at the top level of `src/` or in a dedicated `src/admin_views.py` so the distinction between utilities and views is clear.

### A-04 — Consider separating wallet top-up payments from invoice payments
`Payment` rows currently serve two purposes: invoice payments and wallet top-ups (`invoice_id = NULL`). The dual purpose complicates queries and reporting. A dedicated `WalletTopUp` table (or at minimum a `PaymentType` enum column) would make the two flows explicit.

---

## Features

### F-01 — Add a `GET /admin/orders` endpoint with filtering
Admins currently manage orders only through the SQLAdmin dashboard. A JSON API endpoint (`GET /admin/orders?status=new&city_id=1`) would allow automated tooling, mobile admin apps, or custom dashboards to integrate without scraping the SQLAdmin HTML.

### F-02 — Add soft-delete support for users
The codebase has `deleted_at` on several models but not on `User`. If a user account needs to be deactivated, the current options are: delete the row (breaks foreign keys) or leave it active. Adding `deleted_at` + `is_active` to `User` would support account suspension and GDPR-style "right to be forgotten" flows.

### F-03 — Add an admin endpoint to manage promocodes
Promocodes can be created and read, but there is no admin API endpoint to deactivate, extend, or bulk-create them without going through SQLAdmin. A `PUT /admin/promocodes/{id}` endpoint would be useful.

### F-04 — Push notification delivery
`utils/clients/push.py` exists as a stub. Completing the FCM/APNs integration would allow the app to notify customers when a courier accepts their order, and couriers when a new order arrives in their city — currently only WebSocket (requires an open connection) is used for these events.

### F-05 — Order status history / audit trail
There is an `AuditLog` table for admin actions, but order status changes made by couriers are not logged. An `OrderStatusHistory` table (`order_id`, `old_status`, `new_status`, `changed_by`, `changed_at`) would make debugging disputes and SLA tracking possible.

### F-06 — Delivery date reminder via email
Since customers store important events and orders have a `delivery_date`, a scheduled background job (TaskIQ + Redis cron) could send a reminder email 24 hours before delivery. The email infrastructure and task queue are already in place.

---

## Code Quality

### Q-01 — Standardize all routers to use module-level loggers
Only `payments.py` uses `logger = logging.getLogger(__name__)`. Adding this to every router file allows log filtering by module name and is a one-line change per file.

### Q-02 — Add `conftest.py` env defaults for every new `Settings` field
The CLAUDE.md instructions already note this requirement, but it is easy to forget. Consider adding a CI lint step or a startup test that verifies all Settings fields have a corresponding test default, failing fast instead of surfacing at import time.

### Q-03 — Type-annotate all route handler return types
FastAPI infers return types from `response_model`, but adding explicit `-> SomeResponse` return annotations improves IDE support and makes the contract obvious when reading the function signature alone.

### Q-04 — Replace bare `except Exception` with specific exception types
Several routers catch `Exception` broadly. Where the actual exception types are known (e.g., `botocore.exceptions.ClientError` for S3, `httpx.HTTPError` for Paylink), catching specific types produces better log messages and avoids accidentally swallowing `KeyboardInterrupt` or `SystemExit`.

### Q-05 — Add `__all__` to router modules
Routers are imported via `from routers import admin, auth, ...`. Adding `__all__` to `src/routers/__init__.py` would make the public interface explicit and prevent accidental exposure of internal helpers.

---

## Developer Experience

### D-01 — Add a CI job that runs tests on PRs targeting `main`
Currently CI only runs on pushes to `dev`. Adding a `pull_request: branches: [main]` trigger in `.github/workflows/ci.yml` would gate merges to production on a passing test suite.

### D-02 — Add a `Makefile` or `justfile` with common commands
`uv run --directory src uvicorn main:app --host 0.0.0.0 --port 3000 --reload` is long to type. A `Makefile` with targets like `make dev`, `make test`, `make migrate`, `make seed` would reduce friction for new contributors.

### D-03 — Add pre-commit hooks for linting and formatting
A `.pre-commit-config.yaml` with `ruff` (lint + format) and `mypy` (type check) would catch issues before they reach CI, shortening the feedback loop.

### D-04 — Document the webhook flow with a sequence diagram
The Paylink payment flow (create payment → redirect → callback → credit wallet/invoice) spans three endpoints and involves an external party. A short Mermaid sequence diagram in `docs/` would help new developers understand the flow without reading all three files.

### D-05 — Purge the committed GitHub PAT from git history
`mcp.json` at the repo root contains a committed GitHub PAT. Even if the token has been rotated, the commit history still exposes it. Use `git filter-repo` or BFG Repo Cleaner to remove it from all commits, then force-push. This is a one-time operation.
