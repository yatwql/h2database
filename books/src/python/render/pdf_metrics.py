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


class Calibration:
    """Bounded bisection on one density knob, aiming at a page count.

    A calibration run costs a full render, so the search has to be explainable and
    short: the knob moves monotonically with the page count, so each measurement
    brackets the answer further. The class holds the arithmetic only — the caller
    supplies the render — which keeps the search testable without building a book.
    """

    def __init__(self, target: int, low: float, high: float, tolerance: int = 4):
        self.target = target
        self.low = low
        self.high = high
        self.tolerance = tolerance
        self.history: list[tuple[float, int]] = []

    def record(self, scale: float, pages: int) -> None:
        self.history.append((scale, pages))
        # more spacing -> more pages, so a measurement on either side tightens a bound
        if pages < self.target:
            self.low = max(self.low, scale)
        elif pages > self.target:
            self.high = min(self.high, scale)

    @property
    def converged(self) -> bool:
        if not self.history:
            return False
        return abs(self.history[-1][1] - self.target) <= self.tolerance

    def suggest(self) -> float | None:
        """The next knob value, or None when the search should stop."""
        if self.converged or self.high - self.low <= 0.005:
            return None
        if not self.history:
            return round((self.low + self.high) / 2, 4)
        return round((self.low + self.high) / 2, 4)

    def report(self) -> str:
        lines = [f'  目标 {self.target} 页（容差 ±{self.tolerance}）']
        for scale, pages in self.history:
            lines.append(f'  scale={scale:.3f} → {pages} 页')
        verdict = '已收敛' if self.converged else '未收敛'
        return '\n'.join(lines) + f'\n  {verdict}：区间 [{self.low:.3f}, {self.high:.3f}]'


def compare_targets(built: dict, targets: dict[str, float]) -> str:
    """Compare one measurement against numbers, for when there is no reference PDF."""
    out = []
    for key, want in targets.items():
        if key not in built:
            out.append(f'  {key:12s} 未知指标')
            continue
        have = float(built[key])
        delta = (have - want) / want * 100 if want else 0.0
        flag = '' if abs(delta) <= 3 else ('  ← 偏' + ('大' if delta > 0 else '小'))
        out.append(f'  {key:12s} {want:8.2f} → {have:8.2f}  ({delta:+.1f}%){flag}')
    return '\n'.join(out)


def parse_targets(spec: str) -> dict[str, float]:
    """`pages=843,chars_per_page=1905` -> {'pages': 843.0, ...}."""
    targets: dict[str, float] = {}
    for part in spec.split(','):
        if not part.strip():
            continue
        key, _, value = part.partition('=')
        targets[key.strip()] = float(value)
    return targets


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith('-')]
    if '--target' in argv:
        index = argv.index('--target')
        if index + 1 < len(argv):
            spec = argv[index + 1]
            if spec in args:
                args.remove(spec)  # the target spec is not a file path
    if not args:
        print(__doc__)
        return 2
    if '--target' in argv:
        if not args:
            print('--target 需要一个 PDF')
            return 2
        targets = parse_targets(argv[argv.index('--target') + 1])
        built = measure(args[0])
        print(describe(built))
        print(compare_targets(built, targets))
        return 0
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
