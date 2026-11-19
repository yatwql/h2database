#!/usr/bin/env bash
# Local gate runner, mirroring CI (.github/workflows/book.yml). Thin wrapper:
# the orchestration lives in check_runner.py, so local and CI share one place.
#
#   scripts/check-fast.sh       P0  ~16s   lint + structural gates + unit suite
#   scripts/check-full.sh       P1         every gate + unit suite
#   scripts/check-release.sh    P2         P1 + slow suite + deliver
#   scripts/check.sh p0|p1|p2   any tier directly (--json for machine output)
set -euo pipefail
TIER="${1:-p0}"
shift || true
BOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$BOOK_DIR/.venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
exec "$PYTHON" "$BOOK_DIR/src/python/check_runner.py" --mode "$TIER" "$@"
