#!/usr/bin/env python3
"""The print edition's own typography: chapter banners and TOC dot leaders.

The print edition is the delivery renderer with one difference: it may dress the
page. It shares the split renderer, the page box, the column and the code size with
the standard edition, so nothing here restates a number the layout already owns —
every length is in `em` or a multiple of the type, and the accent comes from the
book's display copy. That is what keeps this from turning into a second set of
figures that drift from the first (the 760px/643px split was exactly that).

`inject()` is idempotent and additive: the stylesheet it adds is a `@media print`
block, so the HTML on disk stays the one screen readers use.
"""
from __future__ import annotations

import os as _os
import sys as _sys

# importable from the renderer whether it runs as a script or as a module
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

STYLE_ID = 'print-grade-css'

# A neutral accent when the book does not name one; the layout owns every dimension,
# so a colour is the only thing this module may decide by itself.
DEFAULT_ACCENT = '#1565C0'


def accent() -> str:
    """The book's accent colour, from its display copy.

    Resolved at call time: a module that binds the config at import keeps pointing at
    the book that was current when it was first imported.
    """
    from lib import _config  # noqa: PLC0415 - call-time resolution

    return _config.project('accent_color', DEFAULT_ACCENT) or DEFAULT_ACCENT


PRINT_CSS = '''<style id="__STYLE_ID__">
@media print {
    /* === H1 chapter cover === */
    /* Each chapter starts on a fresh page, under a banner that scales with the type. */
    #content h1 {
        page-break-before: always;
        margin-top: 0;
        padding-top: 6em;
        font-size: 2.4em;
        text-align: center;
        border: none;
        position: relative;
    }
    #content h1::before {
        content: '';
        display: block;
        width: 6em;
        height: 0.25em;
        margin: 0 auto 1.5em;
        background: linear-gradient(90deg, __ACCENT__, rgba(21, 101, 192, 0.35));
        border-radius: 0.125em;
    }
    #content h1::after {
        content: '';
        display: block;
        width: 60%;
        height: 1px;
        margin: 1.5em auto 0;
        background: #ddd;
    }

    /* === TOC dot leaders === */
    /* Title and page number sit at the flex extremes and the leader fills the gap. */
    #toc-page-nav a {
        display: flex !important;
        align-items: baseline;
        gap: 0.4em;
        padding: 0.2em 0.5em !important;
        text-decoration: none;
    }
    #toc-page-nav a::after {
        content: '........................................'
                 '........................................';
        flex: 1 0 auto;
        margin: 0 0.3em;
        overflow: hidden;
        font-size: 0.75em;
        letter-spacing: 0.08em;
        color: #ccc;
        white-space: nowrap;
        order: 2;
    }
    #toc-page-nav a > span:first-child,
    #toc-page-nav a > div {
        order: 1;
        flex: 1 1 auto;
    }
    #toc-page-nav a > span:last-child {
        order: 3;
        flex: 0 0 auto;
        font-variant-numeric: tabular-nums;
    }
}
</style>'''


def style_block() -> str:
    """The print-only rules, sized in `em` so they follow the layout's type scale.

    Plain text substitution, not `str.format`: the rules are full of CSS braces, and
    escaping every one of them would be a second place to keep correct.
    """
    return PRINT_CSS.replace('__ACCENT__', accent()).replace('__STYLE_ID__', STYLE_ID)


def inject(html: str) -> str:
    """Add the print stylesheet once, just before `</head>`."""
    if f'id="{STYLE_ID}"' in html:
        return html
    return html.replace('</head>', style_block() + '</head>', 1)


def describe() -> str:
    """One line for the build log: what the print edition added."""
    return f'print profile: accent={accent()}, style=#{STYLE_ID}'
