#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODELS_DIR="$ROOT/models"
DIST_DIR="$ROOT/dist"
OUT="$DIST_DIR/ai-media-assistant-models-macos-arm64.zip"

OMNI_PY="$MODELS_DIR/OmniVoice/.venv/bin/python"
QWEN_PY="$MODELS_DIR/Qwen3-TTS-1.7B/.venv/bin/python"

if [ ! -x "$OMNI_PY" ]; then
  echo "缺少 OmniVoice macOS Python：$OMNI_PY" >&2
  exit 1
fi

if [ ! -x "$QWEN_PY" ]; then
  echo "缺少 Qwen3-TTS macOS Python：$QWEN_PY" >&2
  exit 1
fi

mkdir -p "$DIST_DIR"
rm -f "$OUT"
cd "$MODELS_DIR"

zip -r "$OUT" OmniVoice Qwen3-TTS-1.7B \
  -x "*/.git/*" \
  -x "*/__pycache__/*" \
  -x "*.pyc" \
  -x "*/.DS_Store" \
  -x "*/python.exe" \
  -x "*/Scripts/*" \
  -x "*/DLLs/*" \
  -x "*/Lib/site-packages/*.pyd" \
  -x "*/Lib/site-packages/*.dll"

echo "macOS 模型包已生成：$OUT"
