#!/usr/bin/env bash
# Order-dependence probe: run the suite twice (normal, reversed) and diff.
#
#   scripts/eval-order.sh                 # whole suite (slow: two runs)
#   scripts/eval-order.sh --only a,b      # a module subset
#
# Naming: `eval-*` measures; this exits 1 when a case only passes in one order.
set -euo pipefail
BOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$BOOK_DIR/.venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
exec "$PYTHON" "$BOOK_DIR/src/python/audit/order_dependence.py" "$@"
