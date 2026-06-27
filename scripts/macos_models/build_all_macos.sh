#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/build_omnivoice_macos.sh"
"$SCRIPT_DIR/build_qwen_macos.sh"
"$SCRIPT_DIR/package_macos_models.sh"
