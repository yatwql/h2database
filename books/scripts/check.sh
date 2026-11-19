#!/usr/bin/env bash
# Local gate runner, mirroring the CI tiers in .github/workflows/book.yml.
#
#   scripts/check-fast.sh       recency,  ~16s   — lint + structural gates + unit suite
#   scripts/check-full.sh       pre-merge        — every gate
#   scripts/check-release.sh    pre-tag          — full + slow suite + artifacts
#
# Naming: `check-*` verifies (exit code decides), `eval-*` measures (scorecards,
# coverage). Everything a developer runs day to day lives in this directory so
# nobody has to remember python paths.
#
# Exit codes: 0 pass, 1 gate/test failure, 2 environment problem (missing python/.venv).
set -euo pipefail

TIER="${1:-fast}"
BOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$BOOK_DIR/.." && pwd)"
PYTHON="${PYTHON:-$BOOK_DIR/.venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3 || true)"
if [ -z "$PYTHON" ]; then
  echo "error: python3 not found (set PYTHON=/path/to/python)" >&2
  exit 2
fi
cd "$REPO_DIR"

FAST_GATES="architecture,script_contract,style_schema,llm_policy,versions,file_length"

LOG_DIR="$BOOK_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/check-$TIER-$(date +%Y-%m-%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1
trap 'if [ "$KEEP_LOG" = "1" ]; then :; else rm -f "$LOG_FILE"; fi' EXIT
KEEP_LOG=0

say() { printf '\n\033[1;36m== [%s] %s\033[0m\n' "$LEVEL" "$1"; }

case "$TIER" in
  fast) LEVEL=P0 ;;
  full) LEVEL=P1 ;;
  release) LEVEL=P2 ;;
  *) LEVEL=P? ;;
esac

say "lint (ruff)"
if "$PYTHON" -m ruff --version >/dev/null 2>&1; then
  "$PYTHON" -m ruff check books/src/python books/src/test
elif command -v ruff >/dev/null 2>&1; then
  ruff check books/src/python books/src/test
elif command -v uvx >/dev/null 2>&1; then
  uvx ruff check books/src/python books/src/test
else
  echo "skip: ruff not installed (pip install -r requirements-dev.txt)" >&2
fi

say "structural gates"
"$PYTHON" books/src/python/make.py check --only "$FAST_GATES"

say "unit suite (fast tier)"
"$PYTHON" books/src/python/make.py test --timings

case "$TIER" in
  fast)
    KEEP_LOG=1
    say "fast tier passed"
    echo "log: $LOG_FILE"
    ;;
  full|release)
    say "every gate"
    "$PYTHON" books/src/python/make.py check --keep-going --timings
    if [ "$TIER" = "release" ]; then
      say "slow suite (browser + pandoc)"
      BOOK_SLOW=1 "$PYTHON" books/src/python/make.py test --full --timings
      say "deliver artifacts"
      "$PYTHON" books/src/python/make.py deliver --timings
    fi
    KEEP_LOG=1
    say "$TIER tier passed"
    echo "log: $LOG_FILE"
    ;;
  *)
    echo "usage: $0 [fast|full|release]" >&2
    exit 2
    ;;
esac
