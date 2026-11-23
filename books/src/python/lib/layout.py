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
    'layout_body_px': 16,
    'layout_code_px': 10,
    'layout_code_line_height': 1.0,
    'layout_column_px': 960,
    'layout_spacing_scale': 1.0,
    'layout_para_gap_em': 0.8,
    'layout_heading_gap_before_em': 1.5,
    'layout_heading_gap_after_em': 0.5,
    'layout_list_gap_em': 0.5,
    'layout_table_gap_em': 1.0,
}

# field name -> the thresholds key it is read from
_FIELD_KEYS = {name[len('layout_'):]: name for name in DEFAULTS}

# field -> (minimum, maximum); anything outside is a configuration error, not a
# silently different page count
RANGES = {
    'body_px': (8, 24),
    'code_px': (5, 18),
    'code_line_height': (0.8, 2.4),
    'column_px': (480, 1600),
    'spacing_scale': (0.3, 2.0),
    'para_gap_em': (0.0, 3.0),
    'heading_gap_before_em': (0.0, 4.0),
    'heading_gap_after_em': (0.0, 2.0),
    'list_gap_em': (0.0, 2.0),
    'table_gap_em': (0.0, 3.0),
}


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

    def describe(self) -> str:
        """One line for the build log: what this run used."""
        parts = [f'{f.name}={getattr(self, f.name)}' for f in fields(self)]
        return 'layout: ' + ', '.join(parts)
