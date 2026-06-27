#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODEL_DIR="${1:-$ROOT/models/OmniVoice}"
PYTHON_BIN="${PYTHON_BIN:-}"

pick_python() {
  if [ -n "$PYTHON_BIN" ]; then
    command -v "$PYTHON_BIN" >/dev/null 2>&1 && { echo "$PYTHON_BIN"; return; }
    echo "未找到指定的 PYTHON_BIN：$PYTHON_BIN" >&2
    exit 1
  fi
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return
    fi
  done
  echo "未找到 Python 3.11+，请先安装 Python。" >&2
  exit 1
}

if [ ! -d "$MODEL_DIR/omnivoice" ]; then
  echo "OmniVoice 目录不完整：$MODEL_DIR" >&2
  echo "请先把 OmniVoice 源码和权重复制到 models/OmniVoice。" >&2
  exit 1
fi

PY="$(pick_python)"
"$PY" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("OmniVoice 需要 Python 3.10+，建议使用 Python 3.11 或 3.12。")
PY

cd "$MODEL_DIR"
rm -rf .venv
"$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel

if [ -f pyproject.toml ] || [ -f setup.py ]; then
  .venv/bin/python -m pip install -e .
else
  .venv/bin/python -m pip install \
    "torch>=2.4" "torchaudio>=2.4" "transformers>=4.57" accelerate \
    pydub gradio tensorboardX webdataset numpy soundfile librosa
fi

chmod +x .venv/bin/python
echo "OmniVoice macOS 运行环境已生成：$MODEL_DIR/.venv/bin/python"
