#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
docker compose up -d --wait --wait-timeout 120 db
cd backend
uv sync --frozen --python 3.12
uv run --frozen alembic upgrade head
exec uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8000
