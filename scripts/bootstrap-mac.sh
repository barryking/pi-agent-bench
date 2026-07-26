#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_dir"

for command_name in python3.11 docker git; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing $command_name. Follow docs/setup-mac.md, then rerun this script." >&2
    exit 1
  fi
done

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but not running. Start Docker Desktop and rerun." >&2
  exit 1
fi

python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/pi-bench init
docker compose -f docker/compose.yaml build
.venv/bin/python scripts/check-starter-verifiers.py
.venv/bin/ruff check .
.venv/bin/pytest

echo
echo "Setup complete."
echo "1. Edit .env.local and configs/model-baselines.local.json"
echo "2. Run: .venv/bin/pi-bench doctor --model-profile <name> --model-profiles-file configs/model-baselines.local.json --env-file .env.local"
echo "3. See: README.md#run-your-first-campaign"
