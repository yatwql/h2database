#!/usr/bin/env bash
# Release flow: status | gate | publish | manifest  (see src/python/release.py)
#
#   scripts/release.sh status
#   scripts/release.sh publish --title "6.5 交付"
set -euo pipefail
BOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$BOOK_DIR/.venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
exec "$PYTHON" "$BOOK_DIR/src/python/release.py" "$@"
