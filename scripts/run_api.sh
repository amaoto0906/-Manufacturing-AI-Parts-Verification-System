#!/usr/bin/env bash
# 部品照合 API + 管理UI を起動する。
#   ./scripts/run_api.sh [PORT]
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${1:-8077}"
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

export PYTHONPATH="src:${PYTHONPATH:-}"
echo "管理UI:  http://127.0.0.1:${PORT}/ui/"
echo "API Docs: http://127.0.0.1:${PORT}/docs"
exec "$PY" -m uvicorn partmatch.service.app:app --host 0.0.0.0 --port "${PORT}"
