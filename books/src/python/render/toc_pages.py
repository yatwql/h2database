#!/usr/bin/env python3
"""Write the printed page numbers back into the HTML table of contents.

The PDF is rendered first, so the numbers are read from it and then stamped into
`#toc-page-nav` for the next render (and for the screen edition). Two rules keep that
harmless:

  * the stamp goes inside the anchor, never over the markup — a TOC entry may end with
    an inline element (`<code>`, `<b>`), and cutting the closing tag off it corrupts
    the whole document from that point (a stray `<code>` became a child of `<body>`,
    and the book lost ten percent of its height);
  * after the rewrite the markup must still balance, `#content` must be byte-identical
    and the anchor count must be unchanged. Anything else leaves the file untouched:
    page numbers are a convenience, a broken HTML is a delivery defect.

`inject(html, keys, pages)` is pure so the rules are testable without a browser.
"""
from __future__ import annotations

import os as _os
import re
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from lib import _errors, _fsutil  # noqa: E402

NAV_OPEN = '<nav id="toc-page-nav">'
NAV_CLOSE = '</nav>'
ANCHOR_RE = re.compile(r'<a([^>]*)>(.*?)</a>', re.DOTALL)
TAG_RE = re.compile(r'<[^>]+>')
# tags the stamp can disturb; counted by name so `<body>` is not read as `<b>`
BALANCED = ('a', 'code', 'strong', 'em', 'b', 'span')


def _strip_ws(text: str) -> str:
    return re.sub(r'\s+', '', text)


def _plain(inner: str) -> str:
    return _strip_ws(TAG_RE.sub('', inner))


def _count(html: str, tag: str) -> int:
    return len(re.findall(rf'<{tag}\b', html))


def balanced(html: str) -> bool:
    """Whether the tags this module can disturb are still paired."""
    return all(_count(html, tag) == len(re.findall(rf'</{tag}>', html)) for tag in BALANCED)


def content_slice(html: str) -> str:
    """The body from `#content` to the end, which the stamp must never touch."""
    start = html.find('id="content"')
    return html[start:] if start >= 0 else ''


def _stamp(anchor: str, pages: dict[str, int]) -> str:
    """One anchor with its page number, or unchanged when the title is not found."""
    match = ANCHOR_RE.match(anchor)
    if match is None:
        return anchor
    page = pages.get(_plain(match.group(2)))
    if page is None:
        return anchor
    label = f'<span style="font-size:11px;color:#999;font-weight:normal;"> [{page}]</span>'
    # cut the four characters of `</a>`, not the set of characters in it
    head = anchor[:-len('</a>')] if anchor.endswith('</a>') else anchor
    return f'{head}{label}</a>'


def inject(html: str, keys: list[tuple[int, str, str]], found: list[int | None]) -> tuple[str, int]:
    """Stamp the TOC anchors; returns (html, stamps). Unchanged on any imbalance."""
    start = html.find(NAV_OPEN)
    if start < 0:
        return html, 0
    end = html.find(NAV_CLOSE, start)
    if end < 0:
        return html, 0
    pages: dict[str, int] = {}
    for (_level, text, _key), page in zip(keys, found, strict=False):
        if page is not None:
            pages.setdefault(_strip_ws(text), page + 1)
    section = html[start:end]
    stamps = 0

    def substitute(match: re.Match) -> str:
        nonlocal stamps
        stamped = _stamp(match.group(0), pages)
        if stamped != match.group(0):
            stamps += 1
        return stamped

    updated = ANCHOR_RE.sub(substitute, section)
    candidate = html[:start] + updated + html[end:]
    if (content_slice(candidate) != content_slice(html)
            or _count(candidate, 'a') != _count(html, 'a')
            or not balanced(candidate)):
        return html, 0
    return candidate, stamps


def apply(html_path: str, keys: list[tuple[int, str, str]],
          found: list[int | None]) -> int:
    """Rewrite the file in place when the result is sound; returns stamps written."""
    try:
        html = _fsutil.read_text(html_path)
    except _errors.ToolError:
        return 0
    updated, stamps = inject(html, keys, found)
    if not stamps or updated == html:
        return 0
    _fsutil.write_text(html_path, updated)
    return stamps
