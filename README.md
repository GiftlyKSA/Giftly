# Giftly

Async FastAPI backend for a delivery and gifting marketplace targeted at the Saudi market. Customers create gift orders; couriers in the same city accept, deliver, and get paid through the platform's wallet, with payments brokered via Paylink.sa.

The API exposes REST endpoints for auth (phone-OTP), orders, invoices, payments, wallets, promo codes, chat, and a WebSocket channel for real-time messaging and dispatch events. An SQLAdmin dashboard is mounted under `/admin` for back-office work.

## Stack

- **Python 3.11**, **FastAPI**, **async SQLAlchemy 2.0**
- **PostgreSQL** (asyncpg) in production; **SQLite in-memory** (aiosqlite) for tests
- **TaskIQ** + **Redis** for background email tasks
- **SQLAdmin** for the admin dashboard
- **Paylink.sa** for payments, **AWS S3** (or Cloudflare R2) for media, **JWT** (HS256) for auth
- **uv** for dependency management — the project does **not** use pip or `requirements.txt`

## Project layout

```
src/
├── main.py             FastAPI app: middleware, routers, SQLAdmin, /ws
├── routers/            REST endpoints (auth, orders, chat, payments, …)
├── models/             SQLAlchemy models — re-exported from models/__init__.py
├── schemas/            Pydantic request/response shapes (split by audience)
├── middleware/         Logging + last-activity tracking
├── tasks/              TaskIQ broker + registered background tasks
└── utils/
    ├── auth/           JWT issue/verify, token rotation
    ├── clients/        External integrations: paylink, sms, S3 storage
    ├── database/       Settings + async engine/session
    ├── email/          Jinja2 email templating
    └── websocket/      WebSocket connection + room manager
tests/                  Pytest suite — runs against in-memory SQLite
```

## Getting started

### Prerequisites

- **Python 3.11**
- **uv** — install once:
  - Linux/macOS: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows:    `irm https://astral.sh/uv/install.ps1 | iex`
- A reachable **Redis** (default `redis://localhost:6379`) for background tasks
- A reachable **PostgreSQL** for non-test runs (or rely on the in-memory SQLite for tests)

### One-shot bootstrap

The setup scripts create a project-local `.venv` (never global site-packages), install pinned dependencies from `uv.lock`, and start the API.

```bash
# Linux / macOS
chmod +x setup.sh
./setup.sh                # start API on http://0.0.0.0:3000
./setup.sh worker         # start TaskIQ worker
./setup.sh shell          # install only; prints venv activation hint
```

```powershell
# Windows PowerShell
.\setup.ps1               # start API
.\setup.ps1 worker        # start TaskIQ worker
.\setup.ps1 shell         # install only
```

### Manual / day-to-day

```bash
uv sync --frozen                                                      # install from lockfile
uv run alembic upgrade head                                           # apply schema migrations
uv run python scripts/seed.py                                         # (optional) seed local DB
uv run --directory src uvicorn main:app --host 0.0.0.0 --port 3000 --reload
uv run --directory src taskiq worker tasks.broker:broker tasks.email_tasks
uv run pytest tests/                                                  # full test suite
uv add <package>                                                      # add a dependency
```

### Database migrations

Schema is managed by **Alembic** (`migrations/`). The runtime no longer auto-creates tables.

```bash
uv run alembic upgrade head                              # apply pending migrations
uv run alembic revision --autogenerate -m "add column X" # generate a new migration from model changes
uv run alembic downgrade -1                              # roll back one revision
```

`migrations/env.py` reads `DATABASE_URL` from settings, so you don't need to mirror it into `alembic.ini`.

### Seeding sample data

`scripts/seed.py` is idempotent and creates:
- 2 cities (Riyadh, Jeddah)
- 1 admin — username `admin`, password `admin`
- 2 couriers (one per city, both approved + available)
- 3 customers, each with a wallet balance
- 3 orders + matching invoices per customer (9 orders total)

```bash
uv run python scripts/seed.py
```

### Docker

```bash
docker build -f DOCKERFILE -t giftly .
docker run --rm -p 3000:3000 --env-file .env giftly
```

The image installs deps with `uv sync --frozen --no-dev` into `/app/.venv` and runs `uvicorn` from `entrypoint.sh`.

## Configuration

Copy `.env.example` to `.env` and fill in real values. Settings are validated at startup by `src/utils/database/config.py`.

### Required

| Variable | Notes |
|---|---|
| `SECRET_KEY` | ≥32 chars, must include upper, lower, digit, and special char |
| `DATABASE_URL` | e.g. `postgresql+asyncpg://user:pass@host:5432/giftly` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access-token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | JWT refresh-token lifetime |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_S3_BUCKET_NAME` | Object storage for uploads |
| `REDIS_URL` | Broker URL for TaskIQ; defaults to `redis://localhost:6379` |

### Optional

| Variable | Default | Purpose |
|---|---|---|
| `STORAGE_ENDPOINT_URL` | — | Custom S3 endpoint (e.g. Cloudflare R2) |
| `OTP_EXPIRY_SECONDS` | `90` | OTP validity window |
| `RATE_LIMIT_OTP_MAX` | `3` | Max OTP requests per phone per window |
| `RATE_LIMIT_OTP_WINDOW_SECONDS` | `600` | Rate-limit window (10 min) |
| `SMS_PROVIDER_ENABLED` | `false` | Set true once `utils/clients/sms.py` is wired to a real provider |
| `DEBUG` | `false` | Enables `/auth/dev/otp` for testing without an SMS provider |
| `PAYLINK_API_KEY` / `PAYLINK_TEST_MODE` / `PAYLINK_CALLBACK_URL` / `PAYLINK_RETURN_URL` | — / `true` / — / — | Paylink.sa payment gateway |
| `PAYLINK_WEBHOOK_SECRET` | — | HMAC-SHA256 secret for verifying Paylink callback signatures |
| `WALLET_CHARGE_MIN_SAR` | `10` | Minimum customer wallet top-up (SAR) |
| `WALLET_CHARGE_MAX_SAR` | `1000` | Maximum customer wallet top-up (SAR) |
| `ADMIN_WALLET_CHARGE_MAX_HALALAS` | `1000000` | Maximum admin wallet credit (halalas) |
| `RATE_LIMIT_PAYMENT_CREATE_PER_MINUTE` | `20` | Per-IP rate limit for payment creation |
| `RATE_LIMIT_WALLET_CHARGE_PER_MINUTE` | `5` | Per-IP rate limit for wallet top-ups |
| `RATE_LIMIT_COUPON_VERIFY_PER_MINUTE` | `10` | Per-IP rate limit for coupon verification |
| `CHAT_CONVERSATIONS_MAX_LIMIT` | `100` | Max page size for listing conversations |
| `HSTS_MAX_AGE_SECONDS` | `31536000` | Strict-Transport-Security header value |

## Money

All monetary fields (`Wallet.balance`, `Invoice.full_amount`, fees, etc.) are stored as **integers in halalas** — 1 SAR = 100 halalas. Never use floats for money.

## Tests

```bash
uv run pytest tests/                                  # full suite (in-memory SQLite, mocks SMS/Paylink/S3)
uv run pytest tests/auth/test_auth.py::test_name      # single test
uv run pytest -k "promocode and not expired"          # by keyword
```

## Endpoints (high level)

| Prefix | Purpose |
|---|---|
| `/auth` | Phone-OTP send/verify, JWT refresh, profile completion, logout |
| `/orders` | Create / list / accept / status-transition orders |
| `/invoices` | Courier-issued quotes + PDF generation |
| `/payments` | Wallet payments + Paylink callback |
| `/wallets` | Balance, deposits, withdrawals |
| `/promocodes` | Apply / validate promo codes |
| `/chat` | Conversation history, file uploads |
| `/cities` | List supported cities |
| `/couriers` | Courier profile, availability, reviews |
| `/events` | Important-events feed |
| `/admin` | SQLAdmin dashboard (Basic auth) |
| `/ws` | WebSocket: room-based chat + dispatch broadcasts |
| `/health` | Liveness probe |

## Notes

- Schema is managed by **Alembic** — `Base.metadata.create_all` is **not** called at startup. Apply migrations with `uv run alembic upgrade head` before running the server for the first time (or after pulling new model changes).
- Mock external clients in tests by patching the **import site** (e.g. `routers.auth.send_sms`), not the source module.
- `mcp.json` historically contained a committed GitHub token. Rotate and purge from history before publishing.
