#!/usr/bin/env bash
# Convenience wrapper: full tier (p1) of check.sh
exec "$(dirname "${BASH_SOURCE[0]}")/check.sh" p1 "$@"
