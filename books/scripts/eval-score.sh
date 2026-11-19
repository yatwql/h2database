#!/usr/bin/env bash
# Six-dimension release scorecard (功能/稳定/交互/代码/文档风格/文档质量).
#
#   scripts/eval-score.sh          # human table
#   scripts/eval-score.sh --json   # machine readable
#
# Naming: `eval-*` measures and reports; it never fails a build on its own.
set -euo pipefail
BOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$BOOK_DIR/.venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
exec "$PYTHON" "$BOOK_DIR/src/python/make.py" report "$@"
