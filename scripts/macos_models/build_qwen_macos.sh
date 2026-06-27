#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODEL_DIR="${1:-$ROOT/models/Qwen3-TTS-1.7B}"
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

if [ ! -d "$MODEL_DIR/Qwen" ] || [ ! -d "$MODEL_DIR/qwen_tts" ]; then
  echo "Qwen3-TTS 目录不完整：$MODEL_DIR" >&2
  echo "请先把 Qwen、qwen_tts 和权重文件复制到 models/Qwen3-TTS-1.7B。" >&2
  exit 1
fi

PY="$(pick_python)"
"$PY" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Qwen3-TTS 建议使用 Python 3.11+。")
PY

cd "$MODEL_DIR"
rm -rf .venv
"$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install \
  torch torchaudio soundfile librosa numpy einops \
  transformers==4.57.3 accelerate==1.12.0

chmod +x .venv/bin/python
echo "Qwen3-TTS macOS 运行环境已生成：$MODEL_DIR/.venv/bin/python"
