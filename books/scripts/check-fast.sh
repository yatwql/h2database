#!/usr/bin/env bash
# Convenience wrapper: the fast tier of scripts/check.sh
exec "$(dirname "${BASH_SOURCE[0]}")/check.sh" fast "$@"
