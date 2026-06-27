#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== AI Media Assistant Web 2.0 setup =="

if ! command -v python3 >/dev/null 2>&1; then
  echo "未找到 Python。请先安装 Python 3.11+。" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "未找到 Node.js/npm。请先安装 Node.js 20+。" >&2
  exit 1
fi

echo "Python: $(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "Node: $(node -v)"

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi

echo "Installing Python dependencies..."
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"

echo "Installing Node dependencies..."
npm install
if [ -f "apps/web/package.json" ]; then
  npm --prefix apps/web install
fi

echo "Building Web UI..."
npm run build

echo "Preparing local storage directories..."
mkdir -p storage/projects storage/uploads storage/outputs storage/resources

echo "Upgrading SQLite database..."
.venv/bin/python -m alembic -c apps/api/alembic.ini upgrade head

echo ""
echo "Setup complete. Run ./scripts/start_macos.sh to start the app."
