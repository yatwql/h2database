#!/usr/bin/env python3
"""The per-run timing history: one JSON line per run, newest last.

Both readers live above this module — the perf gate compares against it, the
interactive menu estimates from it — and `core` may only import `lib`, so the file
format and its location belong here rather than in either of them.
"""
from __future__ import annotations

import json
import os

from lib import _config

DEFAULT_NAME = 'perf-history.jsonl'


def path() -> str:
    """Where the rolling window lives for the active book."""
    return os.path.join(_config.BOOK_ROOT, 'logs', DEFAULT_NAME)


def history(window: int = 20, source: str | None = None) -> list[dict]:
    """The newest `window` runs; unreadable or malformed lines are skipped."""
    target = source or path()
    if not window or not os.path.isfile(target):
        return []
    runs: list[dict] = []
    try:
        with open(target, encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    runs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return runs[-window:]
