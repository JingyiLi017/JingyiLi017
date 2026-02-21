#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "Starting postgres(pgvector)..."
docker compose -f infra/docker-compose.yml up -d

if [ ! -d "engine/.venv" ]; then
  python3 -m venv engine/.venv
fi

source engine/.venv/bin/activate
pip install -U pip
pip install -r engine/requirements.txt

cd engine
uvicorn app.main:app --reload --host 127.0.0.1 --port 17777

