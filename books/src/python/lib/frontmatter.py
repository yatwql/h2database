#!/usr/bin/env python3
"""Split the merged manuscript into its cover block and its body.

The cover is the book title heading and the meta lines under it, up to the first
chapter. Everything else before that point is body content — the reading guide and
the preface live there, and treating them as cover is how two chapters once went
missing from the built PDF without any gate noticing.

Two consumers need the same answer: the HTML renderer, which must not print the
cover twice, and the outline check, which must not expect cover headings in the
navigation. Sharing the rule is what keeps them from drifting apart.
"""
from __future__ import annotations

import re

CHAPTER_LINE = re.compile(r'^# 第[\d一二三四五六七八九十百]+章')
HEADING_LINE = re.compile(r'^(#{1,6}) \S')


def split(lines: list[str], titles: list[str] | None = None) -> tuple[str, list[str]]:
    """Return (cover text, body lines) for a merged manuscript."""
    wanted = {f'# {title}'.strip() for title in (titles or []) if title}
    chapter_start = next((i for i, line in enumerate(lines) if CHAPTER_LINE.match(line)),
                         len(lines))
    if chapter_start == len(lines):
        # no chapter heading at all: there is no cover boundary to find, so the
        # whole document is body and nothing is silently dropped
        return '', lines
    cover_start = next((i for i, line in enumerate(lines[:chapter_start])
                        if not wanted or line.strip() in wanted), None)
    if cover_start is None:
        # nothing identifies the title, so everything before chapter one is cover
        return ''.join(lines[:chapter_start]), lines[chapter_start:]
    body_start = next((i for i, line in enumerate(lines[:cover_start])
                       if line.startswith('# ')), cover_start)
    return (''.join(lines[:chapter_start]),
            lines[body_start:cover_start] + lines[chapter_start:])


def count_headings(lines: list[str], depth: int) -> int:
    """Headings that reach an outline of `depth` levels.

    Lines inside a fenced block are content, not structure: a `# comment` in a shell
    snippet is not a heading, and counting it would make every check built on this
    number wrong.
    """
    total = 0
    in_fence = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('```'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_LINE.match(line)
        if match and len(match.group(1)) <= depth:
            total += 1
    return total
