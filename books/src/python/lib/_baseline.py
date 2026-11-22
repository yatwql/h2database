"""Reviewed acceptances for a gate's known findings.

A baseline is the escape hatch for a *known, reviewed* backlog: the gate keeps
failing on anything new while the recorded items stay visible in a diffable
JSON file. It is not a mute button — every file here is a list of keys, and an
item that disappears from the manuscript is reported as stale so the baseline
shrinks instead of rotting.

Keys are whatever identifies a finding locally (`file:figure-id`,
`file:line:code`); the gate decides.
"""
from __future__ import annotations

import json
import os

from . import _config, _fsutil

BASELINE_DIR = _config.baseline_dir()


def path_for(name: str) -> str:
    """Baseline file for a gate.

    `base.json [baselines]` is authoritative; a gate without an entry falls back
    to `<name>-findings.json`, so adding a baseline stays a config decision
    rather than a code one.
    """
    configured = _config.BASE_POLICY.get('baselines', {}).get(name.replace('-', '_'))
    if configured:
        return os.path.join(_config.BOOK_ROOT, str(configured))
    return os.path.join(BASELINE_DIR, f'{name}-findings.json')


def load(name: str) -> set[str]:
    """Accepted keys for a gate; empty when no baseline was recorded yet."""
    path = path_for(name)
    if not os.path.exists(path):
        return set()
    try:
        payload = json.loads(_fsutil.read_text(path))
    except (OSError, ValueError):
        return set()  # a broken baseline must not crash the gate it protects
    keys = payload.get('accepted', []) if isinstance(payload, dict) else []
    return {str(key) for key in keys}


def save(name: str, keys: set[str], note: str = '') -> str:
    path = path_for(name)
    _fsutil.ensure_dir(path)
    _fsutil.dump_json(path, {
        'note': note or 'Reviewed backlog: these findings are accepted, new ones fail.',
        'accepted': sorted(keys),
    })
    return path


def split(name: str, keys: set[str]) -> tuple[set[str], set[str]]:
    """(new, stale) relative to the recorded baseline."""
    accepted = load(name)
    return keys - accepted, accepted - keys
