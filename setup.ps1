#!/usr/bin/env pwsh
# Bootstrap the project on Windows (PowerShell):
#   1. Verify uv is available (https://docs.astral.sh/uv/)
#   2. Create a project-local virtualenv at .\.venv and install pinned deps from uv.lock
#   3. Launch the FastAPI app with uvicorn
#
# Run:  .\setup.ps1           (install + start the API)
#       .\setup.ps1 worker    (install + start the TaskIQ worker)
#       .\setup.ps1 shell     (install only, then print activation hint)

param(
    [ValidateSet('api', 'worker', 'shell')]
    [string]$Command = 'api'
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv not found. Install it: irm https://astral.sh/uv/install.ps1 | iex"
    exit 1
}

# Create .venv (if missing) and sync exact pinned deps from uv.lock — never global site-packages.
uv sync --frozen
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

switch ($Command) {
    'api'    { uv run --directory src uvicorn main:app --host 0.0.0.0 --port 3000 --reload }
    'worker' { uv run --directory src taskiq worker tasks.broker:broker tasks.email_tasks }
    'shell'  { Write-Host "Activate with: .\.venv\Scripts\Activate.ps1" }
}

exit $LASTEXITCODE
