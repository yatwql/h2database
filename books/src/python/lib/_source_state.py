#!/usr/bin/env python3
"""What moved in the analyzed source tree since the last digest.

`digest.py` keeps the previous inventory beside the current one. Comparing the two
answers two different questions:

* did anything change at all — a byte comparison is enough for that, and it is what
  the chapter renderer asks before refreshing fact blocks;
* what changed — added and removed packages, and how the totals moved. That is the
  part a person needs before deciding to re-run the analysis: "the source tree
  changed" says nothing about whether it was one file or one subsystem.

Both answers live here so the digest, the renderer and the TUI cannot drift apart.
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any

from lib import _config, _fsutil


def inventory_path(previous: bool = False) -> str:
    """The current (or the kept) source inventory."""
    name = "source-inventory.prev.json" if previous else "source-inventory.json"
    return _config.state_path(name)


def load(path: str) -> dict[str, Any]:
    """The inventory at ``path``, or an empty mapping when it cannot be read."""
    try:
        return json.loads(_fsutil.read_text(path))
    except (OSError, ValueError, SystemExit):
        # read_text turns a missing file into a clean exit; here absence is expected
        return {}


def diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """What changed between two inventories: packages, files, lines."""
    old_packages = set(old.get("packages") or {})
    new_packages = set(new.get("packages") or {})

    def total(payload: dict[str, Any], key: str) -> int:
        raw = (payload.get("totals") or {}).get(key)
        return int(raw or 0)

    return {
        "added": sorted(new_packages - old_packages),
        "removed": sorted(old_packages - new_packages),
        "packages": total(new, "packages") - total(old, "packages"),
        "files": total(new, "files") - total(old, "files"),
        "lines": total(new, "lines") - total(old, "lines"),
    }


def _signed(value: int) -> str:
    return f"{value:+,}" if value else "0"


def summary(moved: dict[str, Any]) -> str:
    """One line: the packages that appeared or went, and how the totals moved."""
    parts = []
    if moved["added"]:
        shown = ", ".join(moved["added"][:3])
        more = f" 等 {len(moved['added'])} 个" if len(moved["added"]) > 3 else ""
        parts.append(f"新增包 {shown}{more}")
    if moved["removed"]:
        shown = ", ".join(moved["removed"][:3])
        more = f" 等 {len(moved['removed'])} 个" if len(moved["removed"]) > 3 else ""
        parts.append(f"移除包 {shown}{more}")
    parts.append(
        f"包 {_signed(moved['packages'])} / 文件 {_signed(moved['files'])}"
        f" / 行 {_signed(moved['lines'])}"
    )
    return "，".join(parts)


def _stamp(path: str) -> str:
    """The file's mtime as a date; empty when it cannot be read."""
    try:
        return datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()
    except OSError:  # pragma: no cover - best effort
        return ""


def state_paths() -> tuple[str, str]:
    """(current, previous) inventory paths for the active book."""
    return inventory_path(), inventory_path(previous=True)


def change_line(current: str, previous: str) -> tuple[str, bool]:
    """('源码清单：…', changed) comparing the current inventory with the kept one.

    Both paths are arguments on purpose: this module must not hold a configuration of
    its own, or a caller that switched books would read the previous one's state.
    """

    if not os.path.isfile(previous):
        return "源码清单：首次 ingest（无上次记录可比）", True
    try:
        same = _fsutil.read_text(previous) == _fsutil.read_text(current)
    except OSError:
        return "源码清单：上次记录不可读，按已变化处理", True
    if same:
        return "源码清单：与上次一致（源码树无变化，事实块不应变）", False
    moved = diff(load(previous), load(current))
    when = _stamp(previous)
    tail = f"，上次分析 {when}" if when else ""
    return f"源码清单：已变化（{summary(moved)}{tail}）", True
