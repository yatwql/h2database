#!/usr/bin/env bash
# Convenience wrapper: the diff-scoped tier (~2s).
#
# Only the gates and tests that the working-tree changes can influence run.
# Use it while iterating; P0 stays the commit gate.
exec "$(dirname "${BASH_SOURCE[0]}")/check.sh" quick "$@"
