#!/usr/bin/env bash
# Convenience wrapper: code-only edit tier.
exec "$(dirname "${BASH_SOURCE[0]}")/check.sh" code "$@"
