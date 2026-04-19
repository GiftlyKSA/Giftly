#!/usr/bin/env bash
# Container entrypoint — runs inside the image built by DOCKERFILE.
# The .venv from `uv sync` is on PATH, so alembic/uvicorn are directly executable.
set -euo pipefail

# Apply any pending schema migrations before starting the app.
alembic upgrade head

cd /app/src
exec uvicorn main:app --host 0.0.0.0 --port 3000
