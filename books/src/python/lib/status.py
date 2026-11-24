#!/usr/bin/env python3
"""One human-readable account of what a run actually did.

A log line that says `check p0 -> pass (0.00s, 1 steps)` records that something
happened, not what happened. What a reader needs is the source tree that was read
and its version, the files that came out and how big they are, and how long it
took. Those facts live here so the log and the TUI show the same thing instead of
two paraphrases that drift apart.
"""
from __future__ import annotations

import datetime
import functools
import os

from lib import _config

MAX_ARTIFACTS = 8
TEXT_SUFFIXES = ('.html', '.epub', '.pdf', '.md')


def _stamp(path: str) -> str:
    try:
        when = datetime.datetime.fromtimestamp(os.path.getmtime(path))
    except OSError:
        return ''
    return when.strftime('%Y-%m-%d %H:%M')


def _mb(path: str) -> str:
    try:
        return f'{os.path.getsize(path) / 1048576:.2f} MB'
    except OSError:
        return '?'


@functools.lru_cache(maxsize=32)
def _pages_cached(path: str, _mtime: float) -> str:
    """Page count, when the reader is installed; a PDF is the only paged output."""
    if not path.lower().endswith('.pdf'):
        return ''  # an EPUB or an HTML has no pages, and the reader would complain
    try:
        from pypdf import PdfReader  # noqa: PLC0415 - optional at runtime
    except ImportError:
        return ''
    try:
        return f'{len(PdfReader(path).pages)} 页'
    except Exception:  # noqa: BLE001 - a broken PDF is reported elsewhere
        return ''


def _pages(path: str) -> str:
    """Page count, cached by modification time: a web request must not re-read a PDF."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return ''
    return _pages_cached(path, mtime)


def source_facts() -> dict:
    """What source tree this run read, its version, and when it last changed."""
    root = ''
    version = ''
    changed = ''
    inventory = _config.state_path('source-inventory.json')
    if os.path.exists(inventory):
        try:
            import json  # noqa: PLC0415 - small helper, imported where used
            with open(inventory, encoding='utf-8') as handle:
                data = json.load(handle)
            root = str(data.get('root') or '')
            version = str(data.get('source_version') or '')
        except (OSError, ValueError) as exc:  # a missing or stale inventory is fine
            del exc
        changed = _stamp(inventory)
    if not root:
        sources = _config.current().sources
        root = str(sources.get('src_main') or '')
    return {'root': root, 'version': version, 'changed': changed}


def artifact_facts(directory: str | None = None) -> list[dict]:
    """Delivered files with the numbers a reader may want to quote."""
    target = directory or _config.current().dist_dir
    try:
        listing = os.listdir(target)
    except OSError:
        return []  # nothing delivered yet
    names = sorted(
        (name for name in listing
         if name.lower().endswith(TEXT_SUFFIXES) and os.path.isfile(os.path.join(target, name))),
        key=lambda name: os.path.getmtime(os.path.join(target, name)),
        reverse=True,
    )
    facts = []
    for name in names[:MAX_ARTIFACTS]:
        path = os.path.join(target, name)
        facts.append({'name': name, 'size': _mb(path), 'pages': _pages(path),
                      'changed': _stamp(path)})
    return facts


def render(ok: bool, label: str, elapsed: float, code: int = 0,
           source: dict | None = None, artifacts: list[dict] | None = None) -> str:
    """The block a human reads after a run — the same text in the log and the TUI."""
    verdict = '✓ 完成' if ok else '✗ 失败'
    lines = [f'{verdict}  {label}   用时 {elapsed:.1f}s   退出码 {code}']
    facts = source if source is not None else source_facts()
    if facts.get('root'):
        parts = [f'源码 {facts["root"]}']
        if facts.get('version'):
            parts.append(f'版本 {facts["version"]}')
        if facts.get('changed'):
            parts.append(f'清单更新于 {facts["changed"]}')
        lines.append('  ' + '   '.join(parts))
    items = artifacts if artifacts is not None else artifact_facts()
    if items:
        lines.append('  产物：')
        for item in items:
            detail = '   '.join(part for part in (item.get('pages'), item.get('size'),
                                                  item.get('changed')) if part)
            lines.append(f'    {item["name"]}   {detail}')
    return '\n'.join(lines)
