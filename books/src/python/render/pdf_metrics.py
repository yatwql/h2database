#!/usr/bin/env python3
"""Report the layout metrics of a built PDF, and compare two of them.

Calibration used to be guesswork ("set a margin, count pages"), which cannot tell
a book that is too dense from one with smaller type. These numbers can, and each
is producer-independent:

  * font size — normalised by the text matrix, because Chromium writes a 0.1 base
    transform plus a 10x restore, so the raw `/Tf` operand is not a point size;
  * line pitch — the distance between consecutive baselines, in points;
  * lines per page and characters per page — geometry and text only;
  * 文本宽度只作参考，不作为判据：文本被切成多段绘制时，宽度只能粗估。

Usage:
    python render/pdf_metrics.py <pdf> [<pdf> ...]
    python render/pdf_metrics.py --compare <reference.pdf> <built.pdf>
"""
from __future__ import annotations

import os
import statistics
import sys
from collections import Counter

from pypdf import PdfReader

SAMPLE_PAGES = 80


def _sample(reader: PdfReader, first: int = 40) -> list:
    pages = reader.pages
    if len(pages) <= SAMPLE_PAGES:
        return list(pages)
    start = min(first, len(pages) - SAMPLE_PAGES)
    return list(pages[start:start + SAMPLE_PAGES])


def measure(path: str) -> dict:
    """Layout metrics for one PDF; empty dict when the file cannot be read."""
    reader = PdfReader(path)
    sizes: Counter = Counter()
    baselines: list[int] = []
    pitches: list[float] = []
    widths: list[float] = []

    for page in _sample(reader):
        ys: set[float] = set()
        xs: list[float] = []

        def visit(text, cm, tm, _font_dict, font_size, ys=ys, xs=xs):
            if not text.strip():
                return
            scale = abs(cm[0] or 1) * abs(tm[0] or 1)
            sizes[round(font_size * scale, 1)] += len(text)
            ys.add(round(tm[5], 1))
            xs.append(tm[4] + tm[0] * len(text) * font_size)

        page.extract_text(visitor_text=visit)
        ordered = sorted(ys, reverse=True)
        baselines.append(len(ordered))
        pitches.extend(ordered[i - 1] - ordered[i] for i in range(1, len(ordered))
                       if 4 < ordered[i - 1] - ordered[i] < 40)
        if xs:
            widths.append(max(xs) - min(xs))

    total = sum(sizes.values()) or 1
    full_text = sum(len(p.extract_text() or '') for p in reader.pages)
    body = sizes.most_common(1)[0][0] if sizes else 0.0
    return {
        'path': path,
        'pages': len(reader.pages),
        'mb': os.path.getsize(path) / (1024 * 1024),
        'chars_per_page': round(full_text / len(reader.pages)),
        'body_pt': body,
        'heading_pt': max(sizes) if sizes else 0.0,
        'body_share': round(sizes.get(body, 0) * 100 / total),
        'lines_per_page': round(statistics.median(baselines)) if baselines else 0,
        'pitch_pt': round(statistics.median(pitches), 1) if pitches else 0.0,
        'text_width_pt': round(statistics.median(widths), 1) if widths else 0.0,
    }


def describe(metrics: dict) -> str:
    name = os.path.basename(metrics['path'])
    return (f'{name[:34]:34s} {metrics["pages"]:5d} 页 {metrics["mb"]:6.2f} MB '
            f'| 正文 {metrics["body_pt"]:4.1f}pt ({metrics["body_share"]}%) '
            f'标题 {metrics["heading_pt"]:5.1f}pt | 行距 {metrics["pitch_pt"]:4.1f}pt '
            f'每页 {metrics["lines_per_page"]:3d} 行 | 宽度 {metrics["text_width_pt"]:5.1f}pt '
            f'| {metrics["chars_per_page"]:5d} 字符/页')


def compare(reference: dict, built: dict) -> str:
    """Line-per-metric delta, so a calibration run reads as a short list."""
    rows = [('页数', 'pages'), ('体积 MB', 'mb'), ('字符/页', 'chars_per_page'),
            ('正文字号 pt', 'body_pt'), ('行距 pt', 'pitch_pt'),
            ('每页行数', 'lines_per_page')]
    out = []
    for label, key in rows:
        a, b = reference[key], built[key]
        delta = (b - a) / a * 100 if a else 0.0
        flag = '' if abs(delta) <= 3 else ('  ← 偏' + ('大' if delta > 0 else '小'))
        out.append(f'  {label:12s} {a:8.2f} → {b:8.2f}  ({delta:+.1f}%){flag}')
    return '\n'.join(out)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith('-')]
    if not args:
        print(__doc__)
        return 2
    if '--compare' in argv:
        if len(args) < 2:
            print('--compare 需要两个 PDF')
            return 2
        reference, built = measure(args[0]), measure(args[1])
        print(describe(reference))
        print(describe(built))
        print(compare(reference, built))
        return 0
    for path in args:
        print(describe(measure(path)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
