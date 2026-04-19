#!/usr/bin/env bash
# Bootstrap the project on Linux/macOS:
#   1. Verify uv is available (https://docs.astral.sh/uv/)
#   2. Create a project-local virtualenv at ./.venv and install pinned deps from uv.lock
#   3. Launch the FastAPI app with uvicorn
#
# Run:  ./setup.sh           (install + start the API)
#       ./setup.sh worker    (install + start the TaskIQ worker)
#       ./setup.sh shell     (install only, then drop you into a venv shell)

set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

# Create .venv (if missing) and sync exact pinned deps from uv.lock — never global site-packages.
uv sync --frozen

cmd="${1:-api}"
case "$cmd" in
    api)
        exec uv run --directory src uvicorn main:app --host 0.0.0.0 --port 3000 --reload
        ;;
    worker)
        exec uv run --directory src taskiq worker tasks.broker:broker tasks.email_tasks
        ;;
    shell)
        echo "Activate with: source .venv/bin/activate"
        ;;
    *)
        echo "Usage: $0 [api|worker|shell]" >&2
        exit 2
        ;;
esac
