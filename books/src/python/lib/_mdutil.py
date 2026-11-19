#!/usr/bin/env python3
"""Markdown helpers shared by the HTML generator and the link audit.

Keeping the anchor algorithm in one place is what makes ``generate_html``'s
``<h2 id="...">`` and ``_audit_links``'s anchor check agree.
"""
from __future__ import annotations

import re

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*$')
_FENCE_RE = re.compile(r'^\s*```')
_SLUG_STRIP_RE = re.compile(r'[^\w\u4e00-\u9fff\u3400-\u4dbf\s-]')
LINK_RE = re.compile(r'!?\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')

EXTERNAL_SCHEMES = ('http://', 'https://', 'mailto:', 'tel:', 'data:', 'ftp://')


def slugify(title: str) -> str:
    """GitHub-style heading anchor, matching what generate_html emits."""
    anchor = title.strip().lower()
    anchor = _SLUG_STRIP_RE.sub('', anchor)
    return anchor.replace(' ', '-')


def iter_headings(lines: list[str]) -> list[tuple[int, str, str]]:
    """Return (level, title, slug) for every heading outside fenced blocks."""
    out: list[tuple[int, str, str]] = []
    in_fence = False
    for raw in lines:
        if _FENCE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(raw.rstrip('\n'))
        if m:
            title = m.group(2).strip()
            out.append((len(m.group(1)), title, slugify(title)))
    return out


def heading_slugs(lines: list[str]) -> set[str]:
    return {slug for _level, _title, slug in iter_headings(lines)}


def is_external(target: str) -> bool:
    lowered = target.strip().lower()
    return lowered.startswith(EXTERNAL_SCHEMES)


def iter_links(text: str) -> list[tuple[str, str]]:
    """Return (label, target) for every inline link/image in ``text``."""
    return [(m.group(1), m.group(2)) for m in LINK_RE.finditer(text)]


def split_fences(text: str) -> list[str]:
    """Split text into (non-fenced) chunks, dropping fenced code blocks."""
    chunks: list[str] = []
    current: list[str] = []
    in_fence = False
    for raw in text.split('\n'):
        if _FENCE_RE.match(raw):
            in_fence = not in_fence
            if not in_fence:
                current.append('')
            continue
        if not in_fence:
            current.append(raw)
    if current:
        chunks.append('\n'.join(current))
    return chunks
