#!/usr/bin/env bash
# Test coverage with the ratchet from base.json [toolchain].coverage_fail_under.
#
#   scripts/test-eval-coverage.sh          # run the suite under coverage, enforce ratchet
#
# Naming: `eval-*` measures. This one exits non-zero when coverage drops below
# the ratchet, so it is also usable as a gate in a release job.
set -euo pipefail
BOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$BOOK_DIR/.venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
exec "$PYTHON" "$BOOK_DIR/src/python/make.py" cover "$@"
