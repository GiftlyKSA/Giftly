FROM python:3.11-slim

# Bring in the uv binary from Astral's distroless image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies into a project-local /app/.venv from the locked manifest.
# `--no-dev` skips test deps; `--frozen` errors out if uv.lock is stale.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Project source — kept after `uv sync` so a code change does not bust the deps layer.
COPY src/ ./src/
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Make the venv's binaries (uvicorn, taskiq) directly callable.
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 3000

ENTRYPOINT ["./entrypoint.sh"]
