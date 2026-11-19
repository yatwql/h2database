#!/usr/bin/env bash
# Convenience wrapper: the release tier of scripts/check.sh
exec "$(dirname "${BASH_SOURCE[0]}")/check.sh" release "$@"
