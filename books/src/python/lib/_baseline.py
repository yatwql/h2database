"""Reviewed acceptances for a gate's known findings.

A baseline is the escape hatch for a *known, reviewed* backlog: the gate keeps
failing on anything new while the recorded items stay visible in a diffable
JSON file. It is not a mute button — every file here is a list of keys, and an
item that disappears from the manuscript is reported as stale so the baseline
shrinks instead of rotting.

Keys are whatever identifies a finding locally (`file:figure-id`,
`file:line:code`); the gate decides. A payload may carry more than the keys —
the source-version a drift baseline was recorded against, for one — so
`load_at`/`save_at` hand the whole object back and the gate reads the fields it
knows. Recording is not the same as accepting: a coverage ratchet or a volume
ledger is a measurement, not a reviewed backlog, and those gates keep their own
files.
"""

from __future__ import annotations

import datetime
import json
import os

from . import _config, _fsutil

DEFAULT_NOTE = "Reviewed backlog: these findings are accepted, new ones fail."


def baseline_dir() -> str:
    """Directory holding this book's baseline files.

    Read per call, not at import: the toolchain serves several books, and a value
    captured at import would keep writing the first book's baselines no matter which
    one is active.
    """
    return _config.baseline_dir()


def path_for(name: str) -> str:
    """Baseline file for a gate, resolved through the active book.

    `base.json [baselines]` is authoritative and `Config.baseline_path` scopes the
    answer to the current edition; a gate without an entry falls back to
    `<name>-findings.json`, so adding a baseline stays a config decision rather
    than a code one.
    """
    key = name.replace("-", "_")
    if key in (_config.BASE_POLICY.get("baselines") or {}):
        return _config.current().baseline_path(key)
    return os.path.join(baseline_dir(), f"{name}-findings.json")


def load(name: str) -> set[str]:
    """Accepted keys for a gate; empty when no baseline was recorded yet."""
    return {str(key) for key in (load_raw(name).get("accepted") or [])}


def load_at(path: str) -> dict:
    """The recorded payload at ``path``, or `{}` when absent or unreadable."""
    if not os.path.exists(path):
        return {}
    try:
        payload = json.loads(_fsutil.read_text(path))
    except (OSError, ValueError):
        return {}  # a broken baseline must not crash the gate it protects
    return payload if isinstance(payload, dict) else {}


def load_raw(name: str) -> dict:
    """The recorded payload for a gate, whole: keys plus whatever else it carries."""
    return load_at(path_for(name))


def load_accepted(path: str) -> set[str]:
    """Accepted keys recorded at ``path``; empty when none were recorded yet."""
    return {str(key) for key in (load_at(path).get("accepted") or [])}


def save(name: str, keys: set[str], note: str = "") -> str:
    return save_at(path_for(name), {"accepted": sorted(keys)}, note)


def save_at(path: str, payload: dict, note: str = "") -> str:
    """Write the keys (and extras) with the review stamp this tree expects."""
    _fsutil.ensure_dir(path)
    body = {
        "updated": datetime.date.today().isoformat(),
        "note": note or payload.get("note") or DEFAULT_NOTE,
    }
    body.update({key: value for key, value in payload.items() if key not in ("updated", "note")})
    _fsutil.dump_json(path, body)
    return path


def split(name: str, keys: set[str]) -> tuple[set[str], set[str]]:
    """(new, stale) relative to the recorded baseline."""
    accepted = load(name)
    return keys - accepted, accepted - keys
