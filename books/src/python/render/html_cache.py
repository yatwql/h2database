#!/usr/bin/env python3
"""Per-chapter HTML fragments: re-render only the chapters that changed.

The cache sits at the chapter-fragment seam, not at the merge step: merging is
pure concatenation, so a cache there would save nothing. A fragment depends on
its own markdown and on the renderer's source text, and on nothing else — the
TOC, the anchors and the cross-chapter numbering are computed before the seam —
so reusing a fragment cannot change a byte of the output. Keys are content
hashes; a changed chapter has a new key and only that fragment is re-rendered.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re

from lib import _config, _fsutil

CACHE_SUBDIR = 'html-cache'
HEADING = re.compile(r'^#\s+\S')
FENCE = '```'


def cache_root() -> str:
    """Directory holding cached fragments, under the book's cache directory.

    Fragments stay valid until the renderer source or the chunk changes, which is
    the definition of a cache rather than of scratch space.
    """
    return os.path.join(_config.cache_dir(), CACHE_SUBDIR)


def fingerprint(*functions) -> str:
    """Hash of the renderer's own source, so a changed renderer invalidates all.

    Reading the source keeps the invalidation honest: nobody has to remember to
    bump a version constant after touching the renderer.
    """
    digest = hashlib.sha256()
    for function in functions:
        try:
            digest.update(inspect.getsource(function).encode('utf-8'))
        except (OSError, TypeError):
            digest.update(b'v1')
    return digest.hexdigest()[:16]


def chunk_lines(lines: list[str]) -> list[list[str]]:
    """Split body lines at H1 headings that sit outside a code fence.

    Splitting only outside fences keeps the renderer's fence state identical to
    a single pass, which is what makes cached and full output byte-identical.
    """
    chunks: list[list[str]] = []
    current: list[str] = []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(FENCE):
            in_fence = not in_fence
        if not in_fence and HEADING.match(line) and current:
            chunks.append(current)
            current = []
        current.append(line)
    if current:
        chunks.append(current)
    return chunks


def key_for(chunk: list[str], renderer: str) -> str:
    """Content-addressed key for one fragment."""
    digest = hashlib.sha256(renderer.encode('utf-8'))
    digest.update(''.join(chunk).encode('utf-8'))
    return digest.hexdigest()[:32]


def load(key: str) -> dict | None:
    """Cached fragment entry for ``key``, or None when absent or unreadable."""
    path = os.path.join(cache_root(), key + '.json')
    if not os.path.isfile(path):
        return None
    try:
        entry = json.loads(_fsutil.read_text(path))
    except (OSError, ValueError):
        return None
    return entry if isinstance(entry, dict) and 'html' in entry else None


def store(key: str, entry: dict) -> None:
    """Write one fragment entry; a read-only or missing directory is not fatal."""
    folder = cache_root()
    try:
        os.makedirs(folder, exist_ok=True)
        _fsutil.write_text(os.path.join(folder, key + '.json'),
                           json.dumps(entry, ensure_ascii=False))
    except OSError:
        pass


def prune(keep: set[str]) -> int:
    """Drop fragments that no chapter on disk refers to any more."""
    folder = cache_root()
    if not os.path.isdir(folder):
        return 0
    removed = 0
    try:
        names = os.listdir(folder)
    except OSError:
        return 0
    for name in names:
        if name.endswith('.json') and name[:-5] not in keep:
            try:
                os.remove(os.path.join(folder, name))
                removed += 1
            except OSError:
                continue
    return removed
