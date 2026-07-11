#!/usr/bin/env bash
# Run the API locally with auto-reload. Assumes .env is present and
# postgres/redis are reachable (e.g. via `docker compose up postgres redis -d`).
set -euo pipefail

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
