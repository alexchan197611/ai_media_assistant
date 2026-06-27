#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -x ".venv/bin/python" ]; then
  echo "未找到 .venv。请先运行 ./scripts/setup_macos.sh。" >&2
  exit 1
fi

if [ ! -f "apps/web/dist/index.html" ]; then
  echo "Web build not found. Building Web UI..."
  npm run build
fi

if command -v lsof >/dev/null 2>&1 && lsof -ti tcp:8123 >/dev/null 2>&1; then
  echo "端口 8123 已被占用。请先关闭已有服务后再启动。" >&2
  exit 1
fi

mkdir -p storage/projects storage/uploads storage/outputs
find models -type f \( -path "*/bin/python" -o -name "python.exe" \) -exec chmod +x {} \; 2>/dev/null || true

echo "Starting AI Media Assistant..."
echo "Open http://127.0.0.1:8123 in your browser."

cleanup() {
  if [ -n "${API_PID:-}" ]; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "${WORKER_PID:-}" ]; then
    kill "$WORKER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup INT TERM EXIT

.venv/bin/python -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8123 &
API_PID=$!

.venv/bin/python -m workers.render_worker.main &
WORKER_PID=$!

while kill -0 "$API_PID" >/dev/null 2>&1 && kill -0 "$WORKER_PID" >/dev/null 2>&1; do
  sleep 2
done

wait "$API_PID" "$WORKER_PID"
