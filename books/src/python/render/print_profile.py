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

STYLE_ID = "print-grade-css"

# A neutral accent when the book does not name one; the layout owns every dimension,
# so a colour is the only thing this module may decide by itself.
DEFAULT_ACCENT = "#1565C0"


def accent() -> str:
    """The book's accent colour, from its display copy.

    Resolved at call time: a module that binds the config at import keeps pointing at
    the book that was current when it was first imported.
    """
    from lib import _config  # noqa: PLC0415 - call-time resolution

    return _config.project("accent_color", DEFAULT_ACCENT) or DEFAULT_ACCENT


PRINT_CSS = """<style id="__STYLE_ID__">
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
</style>"""


def solve_print_type(
    metrics: dict,
    *,
    body_px: int,
    chars_per_line: int,
    lead_target: float,
    code_lead_target: float | None = None,
    scale_min: float = 0.8,
) -> dict[str, float]:
    """Printed type solved from a *measured* sample, not from this book.

    The only inputs are properties of the set type: how many characters a line
    actually holds in the reference document (that number moves when the font
    changes) and the leading ratio the page should have. A wider face therefore
    shrinks the body more, a narrower one less, and no page count of any particular
    book is baked in.

    `lead_target` governs running text; `code_lead_target` (default: the same) is
    the listings' leading. They are separate because a page of listings is set by
    its column width, not by the prose reading measure — giving both one number is
    what tied the printed page count to a decision about running text.

    `metrics` comes from `render.pdf_metrics.measure`; a missing `chars_per_line`
    means "no adaptation" and the scale stays 1.0.
    """
    measured = float(metrics.get("chars_per_line") or 0)
    # characters per line is inversely proportional to the type size in a fixed
    # column, so a line that holds *fewer* characters than the reading measure wants
    # means the type is too big: scale the body by measured/target, never upwards
    scale = measured / float(chars_per_line) if measured > 0 and chars_per_line else 1.0
    scale = max(float(scale_min), min(1.0, scale))
    code_px = metrics.get("code_px") or body_px * 0.75
    code_lead = lead_target if code_lead_target is None else code_lead_target
    return {
        "body_px": max(1, int(round(body_px * scale))),
        "line_height": round(float(lead_target), 3),
        "code_line_height": round(float(code_lead), 3),
        "code_px": round(float(code_px), 1),
        "scale": round(scale, 3),
    }


def density_css(numbers: dict) -> str:
    """The `@media print` rule that makes paper denser than the screen."""
    code_lead = numbers.get("code_line_height", numbers["line_height"])
    return (
        "@media print {\n"
        f"    #content {{ font-size: {numbers['body_px']}px; "
        f"line-height: {numbers['line_height']}; }}\n"
        f"    #content pre, #content code {{ font-size: {numbers['code_px']}px; "
        f"line-height: {code_lead}; }}\n"
        "}\n"
    )


def style_block() -> str:
    """The print-only rules, sized in `em` so they follow the layout's type scale.

    Plain text substitution, not `str.format`: the rules are full of CSS braces, and
    escaping every one of them would be a second place to keep correct.
    """
    return PRINT_CSS.replace("__ACCENT__", accent()).replace("__STYLE_ID__", STYLE_ID)


def inject(html: str, numbers: dict | None = None) -> str:
    """Add the print stylesheet once, just before `</head>`.

    `numbers` (from `solve_print_type`) adds the measured, print-only density rule;
    without it the edition keeps the screen's type size.
    """
    if f'id="{STYLE_ID}"' in html:
        return html
    block = style_block()
    if numbers:
        block = block.replace("</style>", density_css(numbers) + "</style>", 1)
    return html.replace("</head>", block + "</head>", 1)


def describe() -> str:
    """One line for the build log: what the print edition added."""
    return f"print profile: accent={accent()}, style=#{STYLE_ID}"
