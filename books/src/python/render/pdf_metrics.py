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
import re
import statistics
import sys
from collections import Counter

from pypdf import PdfReader

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lib import _config, _fsutil  # noqa: E402

SAMPLE_PAGES = 80


def _sample(reader: PdfReader, first: int = 40) -> list:
    pages = reader.pages
    if len(pages) <= SAMPLE_PAGES:
        return list(pages)
    start = min(first, len(pages) - SAMPLE_PAGES)
    return list(pages[start:start + SAMPLE_PAGES])


def _is_mono_font(font_dict) -> bool:
    """True when the font is a monospace face (listings, not running text)."""
    try:
        name = str((font_dict or {}).get('/BaseFont') or '')
    except Exception:
        return False
    return 'Mono' in name or 'Courier' in name


def measure(path: str) -> dict:
    """Layout metrics for one PDF; empty dict when the file cannot be read."""
    reader = PdfReader(path)
    sizes: Counter = Counter()
    baselines: list[int] = []
    pitches: list[float] = []
    widths: list[float] = []

    prose_baselines: list[int] = []
    prose_pitches: list[float] = []
    prose_sizes: Counter = Counter()
    prose_chars = 0
    code_pitches: list[float] = []
    code_sizes: Counter = Counter()

    for page in _sample(reader):
        ys: set[float] = set()
        xs: list[float] = []
        prose_ys: set[float] = set()
        code_ys: set[float] = set()

        def visit(text, cm, tm, font_dict, font_size, ys=ys, xs=xs, prose_ys=prose_ys,
                  code_ys=code_ys):
            nonlocal prose_chars
            if not text.strip():
                return
            scale = abs(cm[0] or 1) * abs(tm[0] or 1)
            size = round(font_size * scale, 1)
            sizes[size] += len(text)
            ys.add(round(tm[5], 1))
            xs.append(tm[4] + tm[0] * len(text) * font_size)
            # the printed body size only governs running text: a listing is sized by
            # its column width, so its leading must not decide the prose judgement
            if _is_mono_font(font_dict):
                code_ys.add(round(tm[5], 1))
                code_sizes[size] += len(text)
            else:
                prose_ys.add(round(tm[5], 1))
                prose_sizes[size] += len(text)
                prose_chars += len(text)

        page.extract_text(visitor_text=visit)
        ordered = sorted(ys, reverse=True)
        baselines.append(len(ordered))
        pitches.extend(ordered[i - 1] - ordered[i] for i in range(1, len(ordered))
                       if 4 < ordered[i - 1] - ordered[i] < 40)
        prose_ordered = sorted(prose_ys, reverse=True)
        prose_baselines.append(len(prose_ordered))
        prose_pitches.extend(
            prose_ordered[i - 1] - prose_ordered[i] for i in range(1, len(prose_ordered))
            if 4 < prose_ordered[i - 1] - prose_ordered[i] < 40)
        code_ordered = sorted(code_ys, reverse=True)
        code_pitches.extend(
            code_ordered[i - 1] - code_ordered[i] for i in range(1, len(code_ordered))
            if 4 < code_ordered[i - 1] - code_ordered[i] < 40)
        if xs:
            widths.append(max(xs) - min(xs))

    total = sum(sizes.values()) or 1
    # the sample decides the density: reading all 900+ pages for one average cost
    # 14 of the 17 seconds `verify_pdf` spent, and the answer did not change
    sample = _sample(reader)
    sample_chars = sum(len(p.extract_text() or '') for p in sample)
    body = sizes.most_common(1)[0][0] if sizes else 0.0
    return {
        'path': path,
        'pages': len(reader.pages),
        'mb': os.path.getsize(path) / (1024 * 1024),
        'chars_per_page': round(sample_chars / len(sample)) if sample else 0,
        'body_pt': body,
        'heading_pt': max(sizes) if sizes else 0.0,
        'body_share': round(sizes.get(body, 0) * 100 / total),
        'lines_per_page': round(statistics.median(baselines)) if baselines else 0,
        # what the adaptive print step solves against: how many characters a line
        # actually holds (moves when the font changes) and the set leading ratio
        # characters per line: the sampled characters over the sampled *lines*
        # (median baselines is lines per page, so it cannot divide a multi-page count)
        'chars_per_line': round(sample_chars / max(1, sum(baselines)))
        if baselines and sample else 0,
        'pitch_ratio': round(statistics.median(pitches) / body, 3)
        if pitches and body else 0.0,
        # running text only: what a change to the printed body size actually moves
        'prose_body_pt': prose_sizes.most_common(1)[0][0] if prose_sizes else 0.0,
        'prose_chars_per_line': round(prose_chars / max(1, sum(prose_baselines)))
        if prose_baselines and prose_chars else 0,
        'prose_pitch_ratio': round(statistics.median(prose_pitches)
                                   / (prose_sizes.most_common(1)[0][0] or 1), 3)
        if prose_pitches and prose_sizes else 0.0,
        'code_pitch_ratio': round(statistics.median(code_pitches)
                                  / (code_sizes.most_common(1)[0][0] or 1), 3)
        if code_pitches and code_sizes else 0.0,
        # how many gaps the two ratios were drawn from: a ratio over three gaps is
        # noise, and a reader of this dict must be able to tell before judging it
        'prose_lines': len(prose_pitches),
        'code_lines': len(code_pitches),
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


def calibrate(render, target: int, low: float, high: float, tolerance: int = 4,
              max_rounds: int = 4) -> tuple[Calibration, float | None]:
    """Bisect one density knob until the page count lands near `target`.

    Public API: the `--target` path reports a measurement, while calibration is the
    loop a maintainer drives by hand (one render per round). Kept as an entry point
    rather than wired into the CLI, because a calibration run rebuilds the book.

    `render(scale) -> path` performs one build and returns the PDF it produced; the
    caller owns that because a build is expensive and cannot be faked here. Returns
    the search record and the scale that hit the target, if any.
    """
    search = Calibration(target=target, low=low, high=high, tolerance=tolerance)
    for _ in range(max_rounds):
        scale = search.suggest()
        if scale is None:
            break
        produced = render(scale)
        search.record(scale, measure(produced)['pages'])
    if search.converged:
        return search, search.history[-1][0]
    return search, None


def write_back(config_path: str, key: str, value: float) -> None:
    """Persist a calibrated value into `[toolchain]` without disturbing the rest."""
    text = _fsutil.read_text(config_path)
    pattern = re.compile(rf'("{re.escape(key)}"\s*:\s*)[-\d.]+')
    if not pattern.search(text):
        raise SystemExit(f'{key} 不在 {config_path} 中')
    _fsutil.write_text(config_path, pattern.sub(rf'\g<1>{value}', text, count=1))


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith('-')]
    if '--write-back' in argv:
        index = argv.index('--write-back')
        spec = parse_targets(argv[index + 1])
        knob, value = next(iter(spec.items()))
        config = _config.current().base_policy_path
        write_back(config, knob, value)
        print(f'  {knob} = {value} 已写入 {config}')
        return 0
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
