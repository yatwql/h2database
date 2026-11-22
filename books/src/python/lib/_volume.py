#!/usr/bin/env python3
"""Read-only view of the manuscript's distance from its volume baseline.

The gate in ``audit/content_volume.py`` decides pass or fail; the header only
needs the one number an operator glances at ("how much room is left"). Both read
the same two things — the baseline file and the manuscript — so this module owns
the measurement and the gate keeps owning the judgement.
"""
from __future__ import annotations

import json
import os

from lib import _config, _fsutil

BASELINE_NAME = 'content-volume.json'


def baseline_path() -> str:
    return os.path.join(_config.baseline_dir(), BASELINE_NAME)


def manuscript_files() -> list[str]:
    """Manuscript files in reading order (the baseline key order)."""
    files = _config.front_matter()
    files += [os.path.join(_config.MANUSCRIPT_DIR, name)
              for name in _config.chapter_files(include_cover=True)]
    files += _config.back_matter()
    seen: set[str] = set()
    out: list[str] = []
    for path in files:
        if os.path.exists(path) and path not in seen:
            seen.add(path)
            out.append(path)
    return out


def current_lines() -> int:
    return sum(len(_fsutil.read_text(path).splitlines()) for path in manuscript_files())


def headroom() -> dict | None:
    """Current lines, the floor they must clear, and how far above it they sit.

    ``above`` is the honest number for the interface: "still 5,049 lines to spare"
    cannot be misread as "grew by 14%", which a signed percentage invites.

    ``None`` when no baseline has been reviewed yet — a new book has nothing to
    measure against, and a blank is honest where a zero would read as failure.
    """
    path = baseline_path()
    if not os.path.isfile(path):
        return None
    try:
        payload = json.loads(_fsutil.read_text(path))
    except (OSError, ValueError):
        return None
    total = ((payload.get('manuscript') or {}).get('total') or {})
    floor_ratio = float((payload.get('thresholds') or {}).get('floor_ratio', 0.95))
    base_lines = int(total.get('lines') or 0)
    if not base_lines:
        return None
    lines = current_lines()
    floor = int(base_lines * floor_ratio)
    above = lines - floor
    margin = above / floor * 100 if floor else 0.0
    return {'lines': lines, 'baseline': base_lines, 'floor': floor,
            'above': above, 'margin_pct': margin}
