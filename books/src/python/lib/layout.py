#!/usr/bin/env python3
"""Layout parameters as one validated object.

Density used to be a scatter of literals: a margin here, a font size there, a
spacing multiplier read straight out of the thresholds dictionary. That made the
renderer depend on the shape of the config, and a typo turned into a silently
different book. This module is the single place where the numbers are read,
coerced, range-checked and handed to the CSS layer.

All vertical spacing is expressed in `em` and multiplied by one scale: the rhythm
follows the type size automatically, and a calibration run only ever moves
`spacing_scale`.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

# key in `[toolchain]` -> default, so a missing key is a default rather than a crash
DEFAULTS = {
    'layout_page_size': 'A4',
    'layout_page_margin': '24mm 20mm',
    'layout_body_px': 16,           # 0 = derive from the column and the reading density
    'layout_code_px': 10,
    'layout_code_line_height': 0,   # 0 = derive: the same leading as prose
    'layout_column_px': 960,
    'layout_spacing_scale': 1.0,
    'layout_para_gap_em': 0.8,
    'layout_heading_gap_before_em': 1.5,
    'layout_heading_gap_after_em': 0.5,
    'layout_list_gap_em': 0.5,
    'layout_table_gap_em': 1.0,
    'layout_epub_code_em': 0.85,
    'layout_body_chars_per_line': 40,
    'layout_lead_ratio': 0.23,
    'layout_epub_line_height': 1.55,
    'layout_print_body_pt': 8.0,
}

# field name -> the thresholds key it is read from
_FIELD_KEYS = {name[len('layout_'):]: name for name in DEFAULTS}

# field -> (minimum, maximum); anything outside is a configuration error, not a
# silently different page count
RANGES = {
    'body_px': (0, 24),          # 0 means 'derive it'
    'body_chars_per_line': (20, 80),
    'lead_ratio': (0.05, 0.6),
    'epub_line_height': (1.0, 2.4),
    'print_body_pt': (4.0, 14.0),
    'code_px': (5, 18),
    'code_line_height': (0, 2.4),   # 0 means 'derive it'
    'column_px': (480, 1600),
    'spacing_scale': (0.3, 2.0),
    'para_gap_em': (0.0, 3.0),
    'heading_gap_before_em': (0.0, 4.0),
    'heading_gap_after_em': (0.0, 2.0),
    'list_gap_em': (0.0, 2.0),
    'table_gap_em': (0.0, 3.0),
    'epub_code_em': (0.4, 1.2),
}


@dataclass(frozen=True)
class TypeScale:
    """How text is sized, in units both formats can use.

    PDF and EPUB disagree about almost everything, but not about the type: the
    ratio between body and code, the heading ladder, the rhythm between blocks.
    Those live here, expressed in `em` — the one unit that means the same thing on
    a page and in a reflowable column. Anything in pixels belongs to
    `PageGeometry`; a fixed pixel size in an EPUB stops the reader from enlarging
    the text, which is the whole point of the format.
    """

    body_em: float = 1.0
    code_em: float = DEFAULTS['layout_epub_code_em']
    code_line_height: float = 1.0 + DEFAULTS['layout_lead_ratio']
    heading_em: tuple[float, ...] = (1.6, 1.3, 1.1, 1.0)
    body_line_height: float = DEFAULTS['layout_epub_line_height']
    code_block_line_height: float = 1.35
    spacing_scale: float = 1.0
    para_gap_em: float = 0.8
    heading_gap_before_em: float = 1.5
    heading_gap_after_em: float = 0.5
    list_gap_em: float = 0.5
    table_gap_em: float = 1.0

    @classmethod
    def from_layout(cls, layout: Layout) -> TypeScale:
        """Derive the shared scale from one validated layout."""
        return cls(
            body_em=1.0,
            body_line_height=round(float(layout.epub_line_height), 3),
            code_em=round(float(layout.epub_code_em), 4),
            code_line_height=layout.code_line_height_value(),
            spacing_scale=layout.spacing_scale,
            para_gap_em=layout.para_gap_em,
            heading_gap_before_em=layout.heading_gap_before_em,
            heading_gap_after_em=layout.heading_gap_after_em,
            list_gap_em=layout.list_gap_em,
            table_gap_em=layout.table_gap_em,
        )

    @staticmethod
    def _em(value: float) -> str:
        """Format a multiple without a trailing `.0`: `1em`, not `1.0em`."""
        text = f'{round(float(value), 3)}'
        return (text[:-2] if text.endswith('.0') else text) + 'em'

    def gap(self, name: str) -> str:
        """One vertical gap, scaled and formatted in em."""
        return self._em(float(getattr(self, name)) * self.spacing_scale)

    def css_substitutions(self) -> dict[str, str]:
        """Replacement pairs for the EPUB stylesheet, all in relative units."""
        subs = {
            'body { line-height: 1.55;':
                f'body {{ line-height: {self.body_line_height};',
            'font-size: 1.6em;': f'font-size: {self._em(self.heading_em[0])};',
            'font-size: 1.3em;': f'font-size: {self._em(self.heading_em[1])};',
            'font-size: 1.1em;': f'font-size: {self._em(self.heading_em[2])};',
            'font-size: 0.85em;': f'font-size: {self._em(self.code_em)};',
            'h4 { font-size: 1em;': f'h4 {{ font-size: {self._em(self.heading_em[3])};',
            'line-height: 1.35;': f'line-height: {self.code_block_line_height};',
            'margin: 1em 0;': f'margin: {self.gap("table_gap_em")} 0;',
        }
        return subs

    def apply(self, css: str) -> str:
        """Substitute the shared scale into an EPUB stylesheet."""
        for literal, replacement in self.css_substitutions().items():
            css = css.replace(literal, replacement)
        return css

    def describe(self) -> str:
        return (f'type: body={self.body_em}em, code={self.code_em}em, '
                f'headings={"/".join(str(x) for x in self.heading_em)}em, '
                f'spacing_scale={self.spacing_scale}')


@dataclass(frozen=True)
class PageGeometry:
    """What only a fixed page can have: a sheet, margins, a column, pixels.

    An EPUB has none of this — the reader owns the viewport — so keeping these
    fields here rather than in `TypeScale` is what stops paged values from leaking
    into the reflowable output.
    """

    page_size: str
    page_margin: str
    column_px: int
    body_px: int
    body_line_height: float
    code_px: int
    code_line_height: float


@dataclass(frozen=True)
class Layout:
    """Every dimension that decides density, in one immutable object."""

    page_size: str = DEFAULTS['layout_page_size']
    page_margin: str = DEFAULTS['layout_page_margin']
    body_px: int = DEFAULTS['layout_body_px']
    code_px: int = DEFAULTS['layout_code_px']
    code_line_height: float = DEFAULTS['layout_code_line_height']
    column_px: int = DEFAULTS['layout_column_px']
    spacing_scale: float = DEFAULTS['layout_spacing_scale']
    para_gap_em: float = DEFAULTS['layout_para_gap_em']
    heading_gap_before_em: float = DEFAULTS['layout_heading_gap_before_em']
    heading_gap_after_em: float = DEFAULTS['layout_heading_gap_after_em']
    list_gap_em: float = DEFAULTS['layout_list_gap_em']
    table_gap_em: float = DEFAULTS['layout_table_gap_em']
    # the EPUB column is narrower and the reader may zoom; its code size is
    # tuned separately from the page's px ratio, so it is a key of its own
    epub_code_em: float = DEFAULTS['layout_epub_code_em']
    body_chars_per_line: int = DEFAULTS['layout_body_chars_per_line']
    lead_ratio: float = DEFAULTS['layout_lead_ratio']
    # the reflowable column sets its own leading: a reader may zoom, and the
    # page's 1 + lead_ratio would look cramped there
    epub_line_height: float = DEFAULTS['layout_epub_line_height']
    # what a printed body line should measure on paper; the scale follows
    print_body_pt: float = DEFAULTS['layout_print_body_pt']

    @classmethod
    def from_mapping(cls, mapping) -> tuple[Layout, list[str]]:
        """Build from `[toolchain]`, collecting problems instead of raising.

        A bad value keeps its default and is reported: the build continues with a
        known-good layout and the operator sees exactly which key is wrong, rather
        than a page count nobody can explain.
        """
        problems: list[str] = []
        values: dict[str, Any] = {}
        for name, key in _FIELD_KEYS.items():
            raw = (mapping or {}).get(key, DEFAULTS[key])
            default = DEFAULTS[key]
            if isinstance(default, str):
                text = str(raw).strip() if raw is not None else ''
                if not text:
                    problems.append(f'{key} 为空，使用默认值 {default!r}')
                    text = default
                values[name] = text
                continue
            try:
                number = float(raw)
            except (TypeError, ValueError):
                problems.append(f'{key} 不是数字（{raw!r}），使用默认值 {default}')
                number = float(default)
            low, high = RANGES.get(name, (None, None))
            if low is not None and not low <= number <= high:
                problems.append(f'{key} = {number} 超出 [{low}, {high}]，使用默认值 {default}')
                number = float(default)
            values[name] = number if isinstance(default, float) else int(round(number))
        return cls(**values), problems

    def gap(self, name: str) -> str:
        """One vertical gap, scaled by `spacing_scale`, formatted in em."""
        base = float(getattr(self, name))
        return f'{round(base * self.spacing_scale, 3)}em'

    def css_substitutions(self) -> dict[str, str]:
        """Literal in the stylesheet -> replacement, so the CSS stays declarative."""
        return {
            '  @page { size: A4; margin: 24mm 20mm; }':
                f'  @page {{ size: {self.page_size}; margin: {self.page_margin}; }}',
            'flex: 1; max-width: 960px;': f'flex: 1; max-width: {self.column_px}px;',
            'body {\n    font-size: 16px;': f'body {{\n    font-size: {self.body_px}px;',
            '  pre { font-size: 10px; }':
                f'  pre {{ font-size: {self.code_px}px; line-height: {self.code_line_height}; }}',
            'p { margin: 0.8em 0; text-align: justify; }':
                f'p {{ margin: {self.gap("para_gap_em")} 0; text-align: justify; }}',
            'margin-top: 1.5em; margin-bottom: 0.5em; font-family:':
                f'margin-top: {self.gap("heading_gap_before_em")}; '
                f'margin-bottom: {self.gap("heading_gap_after_em")}; font-family:',
            'ul, ol { margin: 0.5em 0; padding-left: 2em; }':
                f'ul, ol {{ margin: {self.gap("list_gap_em")} 0; padding-left: 2em; }}',
            'table { border-collapse: collapse; width: 100%; margin: 1em 0; }':
                f'table {{ border-collapse: collapse; width: 100%; margin: {self.gap("table_gap_em")} 0; }}',
        }

    def apply(self, css: str) -> str:
        """Substitute every configured dimension into a stylesheet."""
        for literal, replacement in self.css_substitutions().items():
            css = css.replace(literal, replacement)
        return css

    def print_scale(self) -> float:
        """Scale that puts the body text at its intended size on paper.

        Fitting the column into the printable width sounds principled but chooses the
        type size as a side effect: a wide column paired with a narrow sheet produces
        text too small to read. The size a printed line should measure is a design
        decision (`print_body_pt`), so the scale is whatever delivers it -- on any
        paper and for any book.
        """
        body_pt = max(0.5, float(self.body_size_px()) * 0.75)
        return round(float(self.print_body_pt) / body_pt, 4)

    def body_size_px(self) -> int:
        """The body size: explicit when configured, else derived from the column.

        A fixed pixel size is a decision that only suits one column width: widen the
        column and the same 16px gives longer lines, narrower and it gives more of
        them. Deriving from "how many characters a line should hold" is the invariant
        that survives a different page, a different font and a different book.
        """
        if self.body_px:
            return int(self.body_px)
        derived = round(self.column_px / max(1, self.body_chars_per_line))
        return max(8, min(24, int(derived)))

    def code_line_height_value(self) -> float:
        """Leading inside a code block: explicit, or the prose leading.

        A block of code set at 1.0 is cramped, and in a source-code book the blocks
        dominate the page — which is exactly what a density check sees.
        """
        if self.code_line_height:
            return float(self.code_line_height)
        return self.body_line_height()

    def body_line_height(self) -> float:
        """Leading as a multiple of the body size, from the configured lead ratio."""
        return round(1.0 + float(self.lead_ratio), 3)

    def typescale(self) -> TypeScale:
        """The part of this layout that EPUB shares."""
        return TypeScale.from_layout(self)

    def geometry(self) -> PageGeometry:
        """The part of this layout only a fixed page can use."""
        return PageGeometry(
            page_size=self.page_size,
            page_margin=self.page_margin,
            column_px=self.column_px,
            body_px=self.body_size_px(),
            body_line_height=self.body_line_height(),
            code_px=self.code_px,
            code_line_height=self.code_line_height_value(),
        )

    def describe(self) -> str:
        """One line for the build log: what this run used."""
        parts = [f'{f.name}={getattr(self, f.name)}' for f in fields(self)]
        return 'layout: ' + ', '.join(parts)
