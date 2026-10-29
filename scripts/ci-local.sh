#!/usr/bin/env bash
# Run the same checks as .github/workflows/ci.yml on this machine (Linux/WSL), using uv.
# Usage: scripts/ci-local.sh [python versions...]   (default: 3.12 3.14)
set -euo pipefail
cd "$(dirname "$0")/.."

versions=("$@")
[ ${#versions[@]} -gt 0 ] || versions=(3.12 3.14)

for v in "${versions[@]}"; do
  env=".venv-ci-$v"
  echo "== tests on Python $v =="
  uv venv --python "$v" --clear -q "$env"
  uv pip install --python "$env/bin/python" -q -e . pytest hypothesis jsonschema
  "$env/bin/python" -m pytest -q
done

echo "== quality (ruff, mypy) =="
env=".venv-ci-quality"
uv venv --python 3.14 --clear -q "$env"
uv pip install --python "$env/bin/python" -q -e . pytest hypothesis jsonschema types-jsonschema ruff mypy
"$env/bin/ruff" check .
"$env/bin/ruff" format --check .
"$env/bin/mypy"
echo "OK: all local CI checks passed"
