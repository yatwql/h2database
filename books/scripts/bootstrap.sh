#!/usr/bin/env bash
# Create books/.venv and install the toolchain dependencies.
#
#   books/scripts/bootstrap.sh            # runtime extras only
#   books/scripts/bootstrap.sh --dev      # + lint/coverage/typecheck
#   books/scripts/bootstrap.sh --check    # report state, install nothing
#
# Uses uv when available (fast), otherwise python3 -m venv + pip.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$BOOK_DIR/.venv"
DEV=0
CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --dev) DEV=1 ;;
    --check) CHECK_ONLY=1 ;;
    *) echo "usage: bootstrap.sh [--dev] [--check]" >&2; exit 2 ;;
  esac
done

PYTHON="${PYTHON:-python3}"
REQ="$BOOK_DIR/requirements.txt"
if [ "$DEV" -eq 1 ]; then REQ="$BOOK_DIR/requirements-dev.txt"; fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  if [ -x "$VENV/bin/python" ]; then
    echo "venv   : $VENV ($("$VENV/bin/python" -V 2>&1))"
  else
    echo "venv   : missing (run bootstrap.sh)"
  fi
  echo "reqs   : $REQ"
  exit 0
fi

if command -v uv >/dev/null 2>&1; then
  uv venv --allow-existing "$VENV" >/dev/null
  uv pip install --python "$VENV/bin/python" -q -r "$REQ"
else
  [ -x "$VENV/bin/python" ] || "$PYTHON" -m venv "$VENV"
  "$VENV/bin/python" -m pip install -q --upgrade pip
  "$VENV/bin/python" -m pip install -q -r "$REQ"
fi
echo "bootstrap: $VENV ready ($REQ)"
