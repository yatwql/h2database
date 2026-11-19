#!/usr/bin/env bash
# Convenience wrapper: fast tier (p0) of check.sh
exec "$(dirname "${BASH_SOURCE[0]}")/check.sh" p0 "$@"
