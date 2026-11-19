#!/usr/bin/env bash
# Point git at the tracked hooks in .githooks/ (pre-commit = P0, pre-push = P1).
#
#   scripts/install-hooks.sh          # install
#   scripts/install-hooks.sh --print  # show what would be configured
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "error: not a git checkout" >&2
  exit 2
fi
if [ "${1:-}" = "--print" ]; then
  echo "core.hooksPath = .githooks"
  sed -n '2,8p' .githooks/pre-commit
  exit 0
fi
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/pre-push
echo "installed: core.hooksPath=.githooks"
echo "  pre-commit -> check_runner.py --mode p0  (~16s)"
echo "  pre-push   -> check_runner.py --mode p1"
echo "bypass: git commit --no-verify / git push --no-verify"
