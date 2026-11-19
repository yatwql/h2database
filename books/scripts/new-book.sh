#!/usr/bin/env bash
# Scaffold a new book (or a translation) from the current structure.
#
#   scripts/new-book.sh ../my-book --title "My Book"
#   scripts/new-book.sh ../translation --lang en --title "My Book (EN)"
#   scripts/new-book.sh ../copy --from-manuscript
#
# Writes four document-side files (book.toml, templates.toml, language pack,
# base.json) plus a *derived* style.json: same schema, fresh thresholds for the
# target script family, no inherited terminology or phrase lists.
set -euo pipefail
BOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-$BOOK_DIR/.venv/bin/python}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
exec "$PYTHON" "$BOOK_DIR/src/python/core/scaffold.py" "$@"
