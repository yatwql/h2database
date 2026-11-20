#!/usr/bin/env bash
# Convenience wrapper: docs-only edit tier.
exec "$(dirname "${BASH_SOURCE[0]}")/check.sh" docs "$@"
