#!/usr/bin/env bash
set -euo pipefail

repository_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_dir"

if [[ -x .venv/bin/python ]]; then
  python_command=".venv/bin/python"
  pi_bench_command=".venv/bin/pi-bench"
  ruff_command=".venv/bin/ruff"
  pytest_command=".venv/bin/pytest"
else
  python_command="${PYTHON_COMMAND:-python}"
  pi_bench_command="${PI_BENCH_COMMAND:-pi-bench}"
  ruff_command="${RUFF_COMMAND:-ruff}"
  pytest_command="${PYTEST_COMMAND:-pytest}"
fi

"$pi_bench_command" build-sandbox
"$ruff_command" check .
"$pytest_command"
"$pi_bench_command" validate evals/sample/cases.jsonl
"$pi_bench_command" validate evals/starter/cases.jsonl
"$pi_bench_command" versions
"$python_command" scripts/check-starter-verifiers.py
"$python_command" scripts/check-agent-profile-examples.py
sandbox_image="$("$python_command" -c \
  'from pi_agent_bench.versions import SANDBOX_IMAGE; print(SANDBOX_IMAGE)')"
docker run --rm \
  --volume "$repository_dir:/repo:ro" \
  "$sandbox_image" \
  node --test /repo/tests/js/viewer-statistics.test.js
