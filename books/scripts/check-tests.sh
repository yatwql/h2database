#!/usr/bin/env bash
# Convenience wrapper: tests-only edit tier.
exec "$(dirname "${BASH_SOURCE[0]}")/check.sh" tests "$@"
