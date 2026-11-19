#!/usr/bin/env bash
# Launch the books toolchain (Linux/macOS).
#
#   books/scripts/run.sh                 # TUI
#   books/scripts/run.sh cli status      # CLI passthrough
#   books/scripts/run.sh web --port 8080 # Web console
#
# Requires python3 on PATH. No business logic here: it only locates the
# interpreter and forwards to books/src/python/app/*.py.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/../src/python/app"
PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "error: $PYTHON not found (set PYTHON=/path/to/python3)" >&2
  exit 2
fi

channel="${1:-tui}"
shift || true

case "$channel" in
  cli|tui|web)
    exec "$PYTHON" "$APP_DIR/$channel.py" "$@"
    ;;
  *)
    echo "usage: run.sh [cli|tui|web] [args...]" >&2
    exit 2
    ;;
esac
