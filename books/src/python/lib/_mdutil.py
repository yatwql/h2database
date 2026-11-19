#!/usr/bin/env python3
"""Markdown helpers shared by the HTML generator and the link audit.

Keeping the anchor algorithm in one place is what makes ``to_html``'s
``<h2 id="...">`` and ``_audit_links``'s anchor check agree.
"""
from __future__ import annotations

import re

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*$')
_FENCE_RE = re.compile(r'^\s*```')
_SLUG_STRIP_RE = re.compile(r'[^\w\u4e00-\u9fff\u3400-\u4dbf\s-]')
HTML_HEADING_RE = re.compile(r'<h([1-4])\s+id="([^"]*)"[^>]*>(.*?)</h\1>', re.DOTALL)
_TAG_RE = re.compile(r'<[^>]+>')

LINK_RE = re.compile(r'!?\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')

EXTERNAL_SCHEMES = ('http://', 'https://', 'mailto:', 'tel:', 'data:', 'ftp://')


def slugify(title: str) -> str:
    """GitHub-style heading anchor, matching what to_html emits."""
    anchor = title.strip().lower()
    anchor = _SLUG_STRIP_RE.sub('', anchor)
    return anchor.replace(' ', '-')


def plain_text(fragment: str) -> str:
    """Inline HTML -> text (tags removed, zero-width space dropped)."""
    return _TAG_RE.sub('', fragment).replace('\u200b', '').strip()


def html_headings(html: str) -> list[dict]:
    """Every ``<hN id="...">`` in document order as {index, level, id, text}.

    One parser for the PDF pipeline (print, outline, verification), so heading
    order and text can never drift between those steps.
    """
    return [{'index': index,
             'level': int(match.group(1)),
             'id': match.group(2),
             'text': plain_text(match.group(3))}
            for index, match in enumerate(HTML_HEADING_RE.finditer(html))]


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

_CJK_RANGE = r'\u4e00-\u9fff'
# zero-width assertions so back-to-back boundaries all get a space
_CJK_LATIN = re.compile(f'(?<=[{_CJK_RANGE}])(?=[A-Za-z0-9])|(?<=[A-Za-z0-9])(?=[{_CJK_RANGE}])')
# Chinese numbering and reference idioms stay tight: 第3章 / §6.2 / 图 6-12 / 附录 A
_IDIOM = re.compile(r'第\d+[章节题条个张]|§\d+(?:\.\d+)*|图 [A-Z0-9]+-\d+|表 [A-Z0-9]+-\d+|附录 [A-Z]')


def _space_plain(part: str) -> str:
    """Insert CJK/Latin spaces in one non-code segment, protecting idioms."""
    masks: list[str] = []

    def mask(match: re.Match) -> str:
        masks.append(match.group(0))
        return f'\x00{len(masks) - 1}\x00'

    part = _IDIOM.sub(mask, part)
    part = _CJK_LATIN.sub(' ', part)
    return re.sub(r'\x00(\d+)\x00', lambda m: masks[int(m.group(1))], part)


def space_cjk_latin(text: str) -> str:
    """Insert a space between CJK characters and Latin letters/digits.

    Inline code spans (``...``) and links (``[label](target)``) are left
    untouched, and Chinese numbering idioms (第3章 / §6.2 / 图 6-12) stay tight.
    """
    parts = re.split(r'(`[^`]*`)', text)
    out = []
    for index, part in enumerate(parts):
        if index % 2 == 1:          # inside a code span
            out.append(part)
            continue
        part = re.sub(r'\[([^\]]*)\]\(([^)]*)\)',
                      lambda m: f'[{m.group(1)}]({m.group(2)})', part)
        out.append(_space_plain(part))
    return ''.join(out)
