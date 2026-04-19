# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Tooling

This project uses **uv** (https://docs.astral.sh/uv) — not pip. The lockfile (`uv.lock`) is authoritative; do not regenerate `requirements.txt` and do not `pip install` into a global Python. All commands run from the repo root unless noted.

```bash
# One-shot bootstrap (creates ./.venv from uv.lock, then runs the app)
./setup.sh                    # Linux/macOS
.\setup.ps1                   # Windows PowerShell
./setup.sh worker             # TaskIQ worker instead of API
./setup.sh shell              # install only

# Day-to-day (after .venv exists)
uv sync --frozen              # install/sync deps from lockfile
uv add <pkg>                  # add a new dependency (writes pyproject.toml + uv.lock)
uv run --directory src uvicorn main:app --host 0.0.0.0 --port 3000 --reload
uv run --directory src taskiq worker tasks.broker:broker tasks.email_tasks
uv run pytest tests/                                # full suite
uv run pytest tests/auth/test_auth.py::test_name    # single test
uv run pytest -k "promocode and not expired"

# Database migrations (Alembic)
uv run alembic upgrade head                         # apply migrations
uv run alembic revision --autogenerate -m "msg"     # new migration from model changes
uv run alembic downgrade -1                         # roll back one revision

# Seed local DB with sample data (admin/admin + 3 customers + 2 couriers + 9 orders)
uv run python scripts/seed.py
```

`pytest.ini` sets `asyncio_mode = auto`. `tests/conftest.py` prepends `src/` to `sys.path` and seeds `os.environ` with safe test defaults *before* importing app modules — when you add a new key to `utils/database/config.py`, add a matching `os.environ.setdefault(...)` in `conftest.py` or test collection will fail.

## Architecture

FastAPI async monolith for a delivery/gifting marketplace (customers ↔ couriers, Saudi market — Paylink.sa gateway, +9665 phone numbers). Python 3.11, async SQLAlchemy 2.0, PostgreSQL in production (asyncpg), in-memory SQLite (aiosqlite) for tests.

**Entry point** is `src/main.py`. It wires together: middleware stack, ~12 routers (mounted under `/auth`, `/orders`, `/chat`, `/payments`, `/wallets`, `/promocodes`, `/couriers`, `/cities`, `/invoices`, `/events`, `/admin`), an SQLAdmin dashboard at `/admin` (Basic-auth gated by an in-app middleware that checks the `Admin` table against bcrypt hashes), and a single WebSocket endpoint at `/ws`.

The `sqladmin` package's `Admin` class is imported as `SQLAdmin` to avoid colliding with the `Admin` SQLAlchemy model — keep that alias if you touch those imports.

**Database lifecycle.** Schema is owned by **Alembic** (`migrations/`). `lifespan` no longer calls `create_all` — apply schema with `uv run alembic upgrade head`. The container's `entrypoint.sh` runs the upgrade before booting uvicorn. To add a new migration: `uv run alembic revision --autogenerate -m "add_thing"` (requires a reachable DB matching `DATABASE_URL`). `migrations/env.py` injects `settings.database_url` into Alembic's config and points `target_metadata` at `Base.metadata`, so `--autogenerate` will diff models against the live DB.

**Seed data.** `scripts/seed.py` populates a fresh DB with 2 cities, 1 admin (`admin` / `admin`), 2 approved couriers (one per city), 3 customers, wallets for everyone, and 3 orders + invoices per customer. Idempotent by phone/username — safe to re-run. `uv run python scripts/seed.py`.

**Models** (`src/models/`) are re-exported from `models/__init__.py`; always import from `models` (not the submodule path) so SQLAdmin and SQLAlchemy relationship resolution see the same class objects. Domain enums live in `models/enums.py` and drive state machines for `Order`, `Invoice`, `Payment`, `Conversation`, `DepositRequest`. **Money is stored as integers in halalas** (1 SAR = 100); e.g. `Wallet.balance = 50_000` is 500 SAR. Never use floats for money.

**Schemas** (`src/schemas/`) are split by audience — `admin/`, `courier/`, `customer/`, `shared/` — keeping role-specific request/response shapes separated even when they wrap the same model.

**Background tasks.** `src/tasks/broker.py` configures a TaskIQ `ListQueueBroker` against Redis. `src/tasks/email_tasks.py` registers tasks; `main.py` imports it for side-effect registration (`# noqa: F401`). `lifespan` only starts/stops the broker when *not* running inside a worker process (`broker.is_worker_process`), so the same module is safe to import from both API and worker.

**WebSockets.** `utils/websocket/websocket_manager.py` exposes a singleton `manager` with room-based broadcast. `/ws` authenticates via JWT in the query string, auto-joins `user_<id>`, and for approved+available couriers also joins `couriers_city_<city_id>` for dispatch fan-out. The `send_message` action persists into the `Message` table and broadcasts to `chat_<conversation_id>` rooms — both customer and courier on the conversation are validated as participants.

**Auth.** JWT (HS256) with separate access (minutes) and refresh (days) tokens; refresh tokens are persisted in the `RefreshToken` table for revocation. `payload["type"] == "refresh"` must be rejected by access-token consumers (the WebSocket handler does this — replicate that check in any new token consumer).

**Middleware order matters** (registered last = runs first in FastAPI): `ForceHTTPSMiddleware` → `SecurityHeadersMiddleware` → `RequestLoggingMiddleware` → `LastActivityMiddleware`. The HTTP→HTTPS redirect happens before anything else, which 301s plain-HTTP local traffic — front the dev server with TLS or hit `https://` directly.

**External clients** are isolated in `src/utils/clients/` (`paylink.py`, `sms.py`, `storage_client.py` for S3). Tests neutralize them via env (`SMS_PROVIDER_ENABLED=false`, `PAYLINK_TEST_MODE=true`, dummy AWS creds). When mocking these in tests, patch the **import site** (e.g. `routers.auth.send_sms`), not the source module.

## Known issues

- `mcp.json` at the repo root contains a committed GitHub PAT. Treat as compromised — rotate and purge from git history.
- CI (`.github/workflows/ci.yml`) only triggers on pushes to `dev`; PRs into `main` do not run tests automatically.
- `entrypoint.sh` previously referenced `test_scripts_for_admin_dashboard/` (not in the repo); now stripped to a minimal uvicorn boot.
