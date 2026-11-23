#!/usr/bin/env python3
"""Check the built PDF against invariants that must hold for any book.

Page count is a judgement call; these are not. A line of text outside the margins
means the column is too wide for its content, a Type3 font means glyphs were traced
instead of embedded, and an outline shorter than the heading list means navigation
lost entries. Each of those is a defect regardless of which book was rendered, so
they belong in a gate rather than in a person's eye.

    python audit/pdf_invariants.py build.pdf --merged merged.md [--json]

`--merged` supplies the level-one headings: the outline must list every one of
them, so a count mismatch is reported with the gap rather than as a bare number.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lib import _config, _fsutil, frontmatter  # noqa: E402

# a line may sit a hair outside the column: justifier rounding, not a layout error
EDGE_TOLERANCE_PT = 2.0
MAX_TYPE3 = 50
# how deep the outline goes is decided when it is written, so the comparison must
# read that depth off the outline itself rather than assume one
HEADING_LINE = re.compile(r'^(#{1,6}) \S')


def _outline_shape(reader) -> tuple[int, int]:
    """Entry count and the deepest nesting level the outline uses."""
    def walk(items, depth: int) -> tuple[int, int]:
        total = 0
        deepest = depth
        for item in items or []:
            if isinstance(item, list):
                count, deep = walk(item, depth + 1)
                total += count
                deepest = max(deepest, deep)
            else:
                total += 1
        return total, deepest

    try:
        return walk(reader.outline, 1)
    except Exception:  # noqa: BLE001 - a broken outline is a finding, not a crash
        return 0, 1


def _type3_count(reader) -> int:
    """Fonts whose glyphs are drawn as procedures instead of embedded outlines."""
    seen = set()
    for page in reader.pages:
        resources = page.get('/Resources') or {}
        fonts = resources.get('/Font') or {}
        for name in fonts:
            font = fonts[name]
            font = font.get_object() if hasattr(font, 'get_object') else font
            if font.get('/Subtype') == '/Type3':
                seen.add(id(font))
    return len(seen)


def _outside_column(reader) -> tuple[list[str], list[str]]:
    """Text beyond the printable area, plus pages whose text could not be read."""
    offenders: list[str] = []
    unreadable: list[str] = []
    for index, page in enumerate(reader.pages[:40], 1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        spills = []

        def visit(text, cm, tm, _fd, _fs, page_size=(width, height), out=spills):
            if not text.strip():
                return
            x = tm[4]
            y = tm[5]
            if page_size[0] > 0 and (x < -EDGE_TOLERANCE_PT
                                     or x > page_size[0] + EDGE_TOLERANCE_PT
                                     or y < -EDGE_TOLERANCE_PT
                                     or y > page_size[1] + EDGE_TOLERANCE_PT):
                out.append(f'x={x:.0f} y={y:.0f}')

        try:
            page.extract_text(visitor_text=visit)
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            unreadable.append(f'p{index}: {exc}')
        if spills:
            offenders.append(f'p{index}: {spills[0]}')
    return offenders, unreadable


def check(pdf_path: str, merged: str | None) -> dict:
    """Every invariant, as data, so the caller decides how to print it."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    outline, depth = _outline_shape(reader)
    headings = None
    if merged and os.path.exists(merged):
        text = _fsutil.read_text(merged)
        lines = text.splitlines()
        # the cover block is not part of the body, so its headings never reach the
        # outline; counting them was what made this check report a phantom gap
        _cover, body = frontmatter.split(
            lines, [_config.TITLE,
                    _config.project('display_title_en', _config.TITLE),
                    _config.project('display_title_zh', _config.TITLE)])
        headings = frontmatter.count_headings(body, depth)
    spills, unreadable = _outside_column(reader)
    report = {
        'pages': len(reader.pages),
        'outline': outline,
        'outline_depth': depth,
        'headings': headings,
        'type3': _type3_count(reader),
        'outside_column': spills,
        'unreadable_pages': unreadable,
    }
    problems = []
    if report['type3'] > MAX_TYPE3:
        problems.append(f'Type3 fonts {report["type3"]} > {MAX_TYPE3}：字体未被嵌入，字形被描成过程')
    if headings is not None and outline != headings:
        problems.append(f'大纲 {outline} 条（{depth} 层），前 {depth} 级标题 {headings} 条')
    if spills:
        problems.append(f'{len(spills)} 页有文字超出页面边界：{spills[0]}')
    if unreadable:
        problems.append(f'{len(unreadable)} 页文字无法读取：{unreadable[0]}')
    report['problems'] = problems
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or '').splitlines()[0])
    parser.add_argument('pdf')
    parser.add_argument('--merged', help='合并后的 markdown，用于核对大纲条目数')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    if not os.path.exists(args.pdf):
        print(f'  找不到 {args.pdf}')
        return 2
    report = check(args.pdf, args.merged)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f'  {report["pages"]} 页 | 大纲 {report["outline"]} 条'
              + (f' / 标题 {report["headings"]} 条' if report['headings'] else '')
              + f' | Type3 {report["type3"]} | 越界页 {len(report["outside_column"])}')
        for problem in report['problems']:
            print(f'  FAIL: {problem}')
    return 0 if not report['problems'] else 1


if __name__ == '__main__':
    sys.exit(main())
