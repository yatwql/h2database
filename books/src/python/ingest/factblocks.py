#!/usr/bin/env python3
"""Marked fact blocks: the parts of a chapter that are re-derived from source.

Package tables, type tables, source coordinates and dependency directions change
with the source tree, but they are not prose. Marking them lets
``chapters.py --refresh-facts`` swap the facts inside a chapter that already
carries written prose, without touching a single word outside the markers.

Format, one block per name:

  <!-- generated:packages -->
  | 包 | 文件数 | 行数 | 职责 |
  <!-- /generated -->

A file without markers has nothing to refresh; the caller reports the skip.
"""
from __future__ import annotations

import difflib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re

from lib import _fsutil

GENERATED_OPEN = '<!-- generated:{} -->'
GENERATED_CLOSE = '<!-- /generated -->'
GENERATED_OPEN_RE = re.compile(r'^<!--\s*generated:([\w.:-]+)\s*-->$')
GENERATED_CLOSE_RE = re.compile(r'^<!--\s*/generated\s*-->$')
BACKUP_DIR = ('data', 'tmp', 'generated-backup')


def mark_block(name: str, lines: list[str]) -> list[str]:
    """One marked block: open marker, body, close marker, blank separator."""
    return [GENERATED_OPEN.format(name), *lines, GENERATED_CLOSE, '']


def generated_blocks(text: str) -> dict[str, list[str]]:
    """Block name -> body lines, for every marked block in ``text``."""
    blocks: dict[str, list[str]] = {}
    name = None
    body: list[str] = []
    for line in (text or '').split('\n'):
        stripped = line.strip()
        opening = GENERATED_OPEN_RE.match(stripped)
        if opening and name is None:
            name, body = opening.group(1), []
            continue
        if GENERATED_CLOSE_RE.match(stripped) and name is not None:
            blocks[name] = body
            name = None
            continue
        if name is not None:
            body.append(line)
    return blocks


def line_delta(old: str, new: str) -> tuple[int, int]:
    """(removed, added) line counts between two texts, for the cost preview."""
    matcher = difflib.SequenceMatcher(None, (old or '').split('\n'),
                                      (new or '').split('\n'), autojunk=False)
    removed = added = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        removed += i2 - i1
        added += j2 - j1
    return removed, added


def refresh_blocks(existing: str, fresh: str) -> tuple[str, int, int] | None:
    """Swap fresh facts into the existing chapter, leaving the rest untouched.

    Returns ``(new_text, removed_lines, added_lines)``, or None when the file on
    disk carries no marked block: there is nothing to refresh in place, and the
    caller reports the skip instead of guessing where the facts belong.
    """
    current = generated_blocks(existing)
    if not current:
        return None
    wanted = generated_blocks(fresh)
    out: list[str] = []
    name = None
    for line in existing.split('\n'):
        opening = GENERATED_OPEN_RE.match(line.strip())
        if opening and name is None:
            name = opening.group(1)
            out.append(line)
            if name in wanted:
                out.extend(wanted[name])
            continue
        if GENERATED_CLOSE_RE.match(line.strip()) and name is not None:
            out.append(line)
            name = None
            continue
        if name is not None and name in wanted:
            continue
        out.append(line)
    removed = added = 0
    for name, body in current.items():
        if name in wanted:
            gone, grown = line_delta('\n'.join(body), '\n'.join(wanted[name]))
            removed += gone
            added += grown
    return '\n'.join(out), removed, added


def backup_existing(path: str, stamp: str) -> str | None:
    """Copy a chapter aside before --force overwrites it; None when it is new."""
    if not os.path.isfile(path):
        return None
    from lib import _config  # resolved per call: the book root is runtime state
    folder = os.path.join(_config.BOOK_ROOT, *BACKUP_DIR, stamp)
    try:
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, os.path.basename(path))
        _fsutil.write_text(target, _fsutil.read_text(path))
    except OSError as exc:
        print(f'  [warn] 备份失败（{exc}）；继续覆盖', file=sys.stderr)
        return None
    return target
