#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== AI Media Assistant Web 2.0 setup =="

PYTHON_BIN=""
for candidate in python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "未找到 Python 3.11+。" >&2
  echo "请先安装 Python 3.11 或 3.12，然后重新运行本脚本。" >&2
  echo "" >&2
  echo "推荐方法一：到官网下载并安装 Python 3.12" >&2
  echo "https://www.python.org/downloads/macos/" >&2
  echo "" >&2
  echo "推荐方法二：如果已经安装 Homebrew，可运行：" >&2
  echo "brew install python@3.12" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "未找到 Node.js/npm。请先安装 Node.js 20+。" >&2
  exit 1
fi

echo "Python: $("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")') ($PYTHON_BIN)"
echo "Node: $(node -v)"

if [ -x ".venv/bin/python" ] && ! .venv/bin/python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
  echo "检测到旧的 .venv 使用了 Python 3.10 或更低版本，正在重建..."
  rm -rf .venv
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating Python virtual environment..."
  "$PYTHON_BIN" -m venv .venv
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

echo "Fixing local model executable permissions..."
find models -type f \( -path "*/bin/python" -o -name "python.exe" \) -exec chmod +x {} \; 2>/dev/null || true

echo "Upgrading SQLite database..."
.venv/bin/python -m alembic -c apps/api/alembic.ini upgrade head

echo ""
echo "Setup complete. Run ./scripts/start_macos.sh to start the app."
