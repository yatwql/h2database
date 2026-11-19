#!/usr/bin/env bash
# Convenience wrapper: release tier (p2) of check.sh
exec "$(dirname "${BASH_SOURCE[0]}")/check.sh" p2 "$@"
