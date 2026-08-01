#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_dir"

for command_name in docker git; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing $command_name. Follow docs/setup-mac.md, then rerun this script." >&2
    exit 1
  fi
done

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but not running. Start Docker Desktop and rerun." >&2
  exit 1
fi

python_command="${PYTHON_COMMAND:-}"
if [[ -z "$python_command" ]]; then
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c \
      'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
      python_command="$candidate"
      break
    fi
  done
fi
if [[ -z "$python_command" ]]; then
  echo "Missing Python 3.11 or newer. Follow docs/setup-mac.md, then rerun." >&2
  exit 1
fi

"$python_command" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/pi-bench init
scripts/check-all.sh

echo
echo "Setup complete."
echo "1. Edit .env.local and the local model, Pi, and agent profile files"
echo "2. Run: .venv/bin/pi-bench doctor --agent-profile <name>"
echo "3. See: README.md#run-a-benchmark"
