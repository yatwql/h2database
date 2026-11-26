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

import re
from dataclasses import dataclass, fields
from typing import Any

# key in `[toolchain]` -> default, so a missing key is a default rather than a crash
DEFAULTS = {
    'layout_page_size': 'A4',
    'layout_page_margin': '24mm 20mm',
    'layout_body_px': 16,           # 0 = derive from the column and the reading density
    'layout_code_px': 10,
    'layout_code_line_height': 0,   # 0 = derive: the same leading as prose
    'layout_column_px': 0,          # 0 = derive from the reading measure below
    'layout_spacing_scale': 1.0,
    'layout_para_gap_em': 0.8,
    'layout_heading_gap_before_em': 1.5,
    'layout_heading_gap_after_em': 0.5,
    'layout_list_gap_em': 0.5,
    'layout_table_gap_em': 1.0,
    'layout_epub_code_em': 0.85,
    'layout_chars_per_line': 40,
    'layout_lead_ratio': 0.23,
    'layout_epub_line_height': 1.55,
    # advance of one monospace character, in em: the width a printed code line
    # occupies is `columns * advance * size`, which is what the sheet must hold
    'layout_print_mono_advance': 0.6,
    # below this the code is unreadable on paper, so the column wraps instead
    'layout_print_code_min_px': 6,
    # wrap long code lines rather than shrinking them; costs pages
    'layout_print_wrap': 0,
    # the smallest margin paper gets; the column gives way if it would go below
    'layout_print_margin_min_mm': 16.0,
    # the reading measure on paper: roomier than the screen's, because a printed
    # line is followed by a reader who can see the whole page at once
    'layout_print_chars_per_line': 44,
    # the band the reading measure must land in, in em; outside it the gate fails
    'layout_chars_per_line_min': 36,
    'layout_chars_per_line_max': 46,
}

# field name -> the thresholds key it is read from
_FIELD_KEYS = {name[len('layout_'):]: name for name in DEFAULTS}

# field -> (minimum, maximum); anything outside is a configuration error, not a
# silently different page count
RANGES = {
    'body_px': (0, 24),          # 0 means 'derive it'
    'chars_per_line': (20, 80),
    'chars_per_line_min': (10, 60),
    'chars_per_line_max': (20, 90),
    'lead_ratio': (0.05, 0.6),
    'epub_line_height': (1.0, 2.4),
    'code_px': (5, 18),
    'code_line_height': (0, 2.4),   # 0 means 'derive it'
    'column_px': (0, 1600),          # 0 = derive it
    'spacing_scale': (0.3, 2.0),
    'para_gap_em': (0.0, 3.0),
    'heading_gap_before_em': (0.0, 4.0),
    'heading_gap_after_em': (0.0, 2.0),
    'list_gap_em': (0.0, 2.0),
    'table_gap_em': (0.0, 3.0),
    'epub_code_em': (0.4, 1.2),
    'print_mono_advance': (0.3, 1.2),
    'print_code_min_px': (4, 14),
    'print_wrap': (0, 1),
    'print_margin_min_mm': (5.0, 40.0),
    'print_chars_per_line': (30, 80),
}

# sheet sizes in millimetres; an unknown name falls back to A4 rather than guessing
PAGE_SIZES_MM = {
    'A3': (297.0, 420.0), 'A4': (210.0, 297.0), 'A5': (148.0, 210.0),
    'B4': (250.0, 353.0), 'B5': (176.0, 250.0),
    'LETTER': (215.9, 279.4), 'LEGAL': (215.9, 355.6),
}
PX_PER_MM = 96 / 25.4
PT_PER_MM = 72 / 25.4
_UNIT_MM = {'mm': 1.0, 'cm': 10.0, 'in': 25.4, 'pt': 25.4 / 72, 'px': 25.4 / 96}


def _mm(token: str) -> float:
    """One CSS length in millimetres; a bare number is millimetres."""
    text = str(token).strip().lower()
    for unit, factor in _UNIT_MM.items():
        if text.endswith(unit):
            return float(text[:-len(unit)]) * factor
    return float(text)


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
    chars_per_line: int = DEFAULTS['layout_chars_per_line']
    lead_ratio: float = DEFAULTS['layout_lead_ratio']
    # the reflowable column sets its own leading: a reader may zoom, and the
    # page's 1 + lead_ratio would look cramped there
    epub_line_height: float = DEFAULTS['layout_epub_line_height']
    # width of one monospace character in em, for fitting a printed code column
    print_mono_advance: float = DEFAULTS['layout_print_mono_advance']
    print_code_min_px: int = DEFAULTS['layout_print_code_min_px']
    # wrap instead of shrinking: one diagram row becomes several text rows
    print_wrap: int = DEFAULTS['layout_print_wrap']
    print_margin_min_mm: float = DEFAULTS['layout_print_margin_min_mm']
    print_chars_per_line: int = DEFAULTS['layout_print_chars_per_line']
    chars_per_line_min: int = DEFAULTS['layout_chars_per_line_min']
    chars_per_line_max: int = DEFAULTS['layout_chars_per_line_max']

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
            'flex: 1; max-width: 960px;': f'flex: 1; max-width: {self.column()}px;',
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

    def page_size_mm(self) -> tuple[float, float]:
        """The sheet in millimetres, by name or as `WxH` lengths."""
        key = str(self.page_size).strip().upper()
        if key in PAGE_SIZES_MM:
            return PAGE_SIZES_MM[key]
        parts = [p for p in re.split(r'[xX×\s]+', key) if p]
        if len(parts) == 2:
            try:
                return _mm(parts[0]), _mm(parts[1])
            except ValueError:
                pass
        return PAGE_SIZES_MM['A4']

    def margins_mm(self) -> tuple[float, float]:
        """Left and right margin, from the CSS shorthand in `page_margin`."""
        tokens = [t for t in re.split(r'\s+', str(self.page_margin).strip()) if t]
        try:
            values = [_mm(t) for t in tokens] or [0.0]
        except ValueError:
            values = [0.0]
        if len(values) == 1:
            return values[0], values[0]
        if len(values) == 3:
            return values[1], values[1]
        if len(values) >= 4:
            return values[3], values[1]
        return values[1], values[1]

    def printable_width_px(self) -> float:
        """What the sheet leaves for text, in CSS pixels.

        A column wider than this prints outside the margins, and a column that only
        fits because the renderer clips the overflow loses the end of every long
        line. Both are the same defect, so the printable width is the budget every
        printed column is measured against. On a derived layout the horizontal margin
        is what the column does not use, so this is the column.
        """
        _top_bottom, horizontal = self.print_margins_mm()
        return max(0.0, (self.page_size_mm()[0] - 2 * horizontal) * PX_PER_MM)

    def print_margins_mm(self) -> tuple[float, float]:
        """Vertical and horizontal margin for paper, in millimetres.

        The horizontal margin is what the column does not use, never less than the
        configured floor: the reading measure decides how wide the text is, and the
        sheet then has to carry it. A column that does not fit at the floor is
        clipped by `print_column` instead of eating into the edge.
        """
        tokens = [t for t in re.split(r'\s+', str(self.page_margin).strip()) if t]
        try:
            vertical = _mm(tokens[0]) if tokens else 0.0
        except ValueError:
            vertical = 0.0
        requested = self.column() / PX_PER_MM
        horizontal = max(float(self.print_margin_min_mm),
                         (self.page_size_mm()[0] - requested) / 2)
        return vertical, round(horizontal, 2)

    def print_page_margin(self) -> str:
        """The `@page` margin for paper, as a CSS shorthand."""
        vertical, horizontal = self.print_margins_mm()
        return f'{round(vertical, 2)}mm {horizontal}mm'

    def printable_width_pt(self) -> float:
        """The same width in points, which is what a built page is measured in."""
        return round(self.printable_width_px() / PX_PER_MM * PT_PER_MM, 2)

    def column(self) -> int:
        """The column, in CSS pixels — the same rule on screen and on paper.

        A line holds a fixed number of `em`, so the column is the reading measure
        times the type size. `em` is the one unit that means the same thing in another
        font, on another OS and in another book: 40em is 40 CJK characters and about
        80 Latin ones, whichever face is installed. `layout_column_px` still overrides
        it for a screen that wants a fixed width.
        """
        if self.column_px:
            return int(self.column_px)
        return max(1, int(round(self.chars_per_line * self.body_size_px())))

    def print_column(self) -> int:
        """The printed column: the same measure, clipped to the sheet at the margin floor.

        The literal this replaces was the viewport minus its padding (794 minus a bit
        = 760px, leaving 4.5mm of paper margin), so the column was never derived from
        anything and the text sat in the margin.
        """
        requested = self.column() / PX_PER_MM
        floor = float(self.print_margin_min_mm)
        horizontal = max(floor, (self.page_size_mm()[0] - requested) / 2)
        available = (self.page_size_mm()[0] - 2 * horizontal) * PX_PER_MM
        return max(1, int(min(self.column(), round(available))))

    def measure_em(self) -> float:
        """`em` per printed line: the reading measure, measured rather than assumed."""
        return round(self.print_column() / max(1, self.body_size_px()), 2)

    def measure_problems(self) -> list[str]:
        """The reading measure and the sheet, judged by one book-free invariant.

        `chars_per_line_min <= column / body <= chars_per_line_max`: a line too long
        tires the eye and a line too short breaks the rhythm, and both are properties
        of the text, not of the page it lands on. The second half is the sheet: the
        column must still fit what the margins leave, or the print clips it.
        """
        problems: list[str] = []
        band = f'[{self.chars_per_line_min}, {self.chars_per_line_max}]'
        if not self.chars_per_line_min <= self.chars_per_line <= self.chars_per_line_max:
            problems.append(f'阅读度量 {self.chars_per_line}em 超出阅读区间 {band}')
        measure = self.measure_em()
        if not self.chars_per_line_min <= measure <= self.chars_per_line_max:
            problems.append(f'实际每行 {measure:g}em 超出阅读区间 {band}')

        printable = self.printable_width_px()
        if self.column() > printable + 1:
            problems.append(f'栏宽 {self.column()}px 超出这张纸的可印宽度 '
                            f'{printable:.0f}px（左右各 {self.print_margins_mm()[1]:g}mm，'
                            f'实际落到 {self.print_column()}px）')
        return problems

    def _print_fit_px(self, columns: int) -> float:
        """Code size at which `columns` characters exactly fill the printable width."""
        return (self.printable_width_px() / max(1, int(columns))
                / max(0.1, self.print_mono_advance))

    def print_code_px(self, columns: int) -> float:
        """Largest code type that keeps `columns` characters inside the sheet.

        Capped by the screen size: printing code larger than the screen edition was
        never the intent, and the cap keeps this a pure fit calculation.
        """
        return round(max(float(self.print_code_min_px),
                         min(float(self.code_px), self._print_fit_px(columns))), 2)

    def print_wraps(self, columns: int) -> bool:
        """Whether the printed code column wraps instead of shrinking further.

        Wrapping keeps every line inside the sheet but turns one diagram row into
        several text rows, so it is a decision with a page cost — taken only when
        the alternative is type too small to read.
        """
        return bool(self.print_wrap) or self._print_fit_px(columns) < self.print_code_min_px

    def body_size_px(self) -> int:
        """The body size: explicit when configured, else derived from the column.

        A fixed pixel size is a decision that only suits one column width: widen the
        column and the same 16px gives longer lines, narrower and it gives more of
        them. Deriving from "how many characters a line should hold" is the invariant
        that survives a different page, a different font and a different book.
        """
        if self.body_px:
            return int(self.body_px)
        derived = round(self.column() / max(1, self.chars_per_line))
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
            column_px=self.column(),
            body_px=self.body_size_px(),
            body_line_height=self.body_line_height(),
            code_px=self.code_px,
            code_line_height=self.code_line_height_value(),
        )

    def describe(self) -> str:
        """One line for the build log: what this run used."""
        parts = [f'{f.name}={getattr(self, f.name)}' for f in fields(self)]
        return 'layout: ' + ', '.join(parts)
