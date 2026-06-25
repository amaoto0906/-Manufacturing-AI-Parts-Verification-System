#!/usr/bin/env bash
# 部品照合 API + 管理UI を HTTPS で起動する（モバイルのカメラ撮影に必要）。
#   ./scripts/run_api_https.sh [PORT]
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${1:-8443}"
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

if [ ! -f certs/cert.pem ] || [ ! -f certs/key.pem ]; then
  echo "証明書がありません。先に生成します..."
  bash scripts/gen_cert.sh
fi

LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
export PYTHONPATH="src:${PYTHONPATH:-}"
echo "管理UI(HTTPS): https://${LAN_IP:-127.0.0.1}:${PORT}/ui/   （モバイル可・カメラ利用可）"
echo "API Docs     : https://127.0.0.1:${PORT}/docs"
exec "$PY" -m uvicorn partmatch.service.app:app \
  --host 0.0.0.0 --port "${PORT}" \
  --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem
