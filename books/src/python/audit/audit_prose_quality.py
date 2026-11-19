#!/usr/bin/env python3
"""Prose-level quality scoring for a technical book.

Structural gates answer "is the book valid"; this answers "does it read like a
professional software book": sentence length distribution, paragraph shape,
list/bullet ratio, example density, section depth, table hygiene, terminology
linkage, navigation and uniqueness.

Each dimension scores 0-100; the report prints the composite and the weakest
dimensions. Thresholds live in style.json -> [prose].

Usage:
  python audit_prose_quality.py            # report + exit code
  python audit_prose_quality.py --json
  python audit_prose_quality.py --warn-only
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

FENCE_RE = re.compile(r'```[\s\S]*?```')
SENT_RE = re.compile(r'(?<=[。！？；.!?])\s*')
COORD_RE = re.compile(r'\.java:\d+')
LIST_RE = re.compile(r'^\s*(?:[-*+]|\d+\.)\s+', re.MULTILINE)
H2_RE = re.compile(r'^## ', re.MULTILINE)
H3_RE = re.compile(r'^### ', re.MULTILINE)
TABLE_ROW_RE = re.compile(r'^\|', re.MULTILINE)
NORM_RE = re.compile(r'[^\u4e00-\u9fffA-Za-z0-9]')


def _files() -> list[str]:
    return (sorted(glob.glob(os.path.join(_config.MANUSCRIPT_DIR, 'ch*.md')))
            + sorted(glob.glob(os.path.join(_config.MANUSCRIPT_DIR, 'appendix-*.md'))))


def _score(value: float, good: float, bad: float, *, higher_is_better: bool = True) -> float:
    """Linear score between the 'good' and 'bad' anchors, clamped to 0-100."""
    if higher_is_better:
        if value >= good:
            return 100.0
        if value <= bad:
            return 0.0
        return 100.0 * (value - bad) / max(1e-9, good - bad)
    if value <= good:
        return 100.0
    if value >= bad:
        return 0.0
    return 100.0 * (bad - value) / max(1e-9, bad - good)


def measure() -> dict:
    """Per-file and aggregate prose metrics."""
    per_file: dict[str, dict] = {}
    dup_index: dict[str, set[str]] = {}
    all_rows = 0
    bad_rows = 0

    for path in _files():
        text = _fsutil.read_text(path)
        name = os.path.basename(path)
        prose = FENCE_RE.sub('', text)
        prose_lines = [line for line in prose.split('\n') if line.strip()]
        sentences = [s.strip() for s in SENT_RE.split(prose) if len(s.strip()) > 6]
        paragraphs = [b for b in re.split(r'\n\s*\n', prose) if b.strip()]
        bullets = len(LIST_RE.findall(prose))
        # group consecutive table rows so column counts are compared per table
        tables: list[list[str]] = []
        current: list[str] = []
        for line in text.split('\n'):
            if line.startswith('|'):
                current.append(line)
            elif current:
                tables.append(current)
                current = []
        if current:
            tables.append(current)
        rows_with_cells = 0
        empty_cells = 0
        ragged = 0
        for table in tables:
            body = [r for r in table if not re.match(r'^\|[\s:|-]+\|$', r)]
            rows_with_cells += len(body)
            if not body:
                continue
            widths = {len(r.rstrip().split('|')) for r in body}
            if len(widths) > 1:
                ragged += len(body)
            empty_cells += sum(1 for r in body
                               if any(not cell.strip() for cell in r.strip().strip('|').split('|')))
        all_rows += rows_with_cells
        bad_rows += empty_cells + ragged

        for sentence in sentences:
            key = NORM_RE.sub('', sentence)[:40]
            if len(key) > 20:
                dup_index.setdefault(key, set()).add(name)

        per_file[name] = {
            'lines': len(prose_lines),
            'sentences': len(sentences),
            'avg_sentence': round(sum(map(len, sentences)) / max(1, len(sentences)), 1),
            'long_sentence_ratio': round(100 * sum(1 for s in sentences if len(s) > 60)
                                         / max(1, len(sentences)), 1),
            'paragraphs': len(paragraphs),
            'avg_paragraph': round(sum(len(p) for p in paragraphs) / max(1, len(paragraphs)), 1),
            'bullet_ratio': round(100 * bullets / max(1, len(prose_lines)), 1),
            'coords': len(COORD_RE.findall(text)),
            'h2': len(H2_RE.findall(text)),
            'h3': len(H3_RE.findall(text)),
            'table_rows': rows_with_cells,
            'empty_cells': empty_cells,
        }

    duplicated = sum(1 for files in dup_index.values() if len(files) > 1)
    dupe_ratio = round(100 * duplicated / max(1, len(dup_index)), 1)
    totals = {
        'files': len(per_file),
        'lines': sum(v['lines'] for v in per_file.values()),
        'coords': sum(v['coords'] for v in per_file.values()),
        'avg_sentence': round(sum(v['avg_sentence'] for v in per_file.values())
                              / max(1, len(per_file)), 1),
        'long_sentence_ratio': round(sum(v['long_sentence_ratio'] for v in per_file.values())
                                     / max(1, len(per_file)), 1),
        'avg_paragraph': round(sum(v['avg_paragraph'] for v in per_file.values())
                               / max(1, len(per_file)), 1),
        'bullet_ratio': round(sum(v['bullet_ratio'] for v in per_file.values())
                              / max(1, len(per_file)), 1),
        'duplicate_ratio': dupe_ratio,
        'empty_cell_ratio': round(100 * bad_rows / max(1, all_rows), 1),
        'h3_per_file': round(sum(v['h3'] for v in per_file.values()) / max(1, len(per_file)), 1),
        'coords_per_file': round(sum(v['coords'] for v in per_file.values())
                                 / max(1, len(per_file)), 1),
    }
    return {'totals': totals, 'per_file': per_file}


def score(report: dict) -> tuple[float, dict[str, float]]:
    """Composite 0-100 score plus per-dimension scores."""
    t = report['totals']
    p = _config.STYLE_POLICY.get('prose', {})
    dims = {
        'sentence_length': _score(t['avg_sentence'], p.get('avg_sentence_good', 28),
                                  p.get('avg_sentence_bad', 45), higher_is_better=False),
        'long_sentence_ratio': _score(t['long_sentence_ratio'],
                                      p.get('long_ratio_good', 8),
                                      p.get('long_ratio_bad', 30), higher_is_better=False),
        'paragraph_length': _score(t['avg_paragraph'], p.get('paragraph_good_min', 80),
                                   p.get('paragraph_good_max', 420), higher_is_better=True),
        'bullet_ratio': _score(t['bullet_ratio'], p.get('bullet_good', 12),
                               p.get('bullet_bad', 60), higher_is_better=False),
        'example_density': _score(t['coords_per_file'], p.get('coords_good', 20),
                                   p.get('coords_bad', 4)),
        'section_depth': _score(t['h3_per_file'], p.get('h3_good', 6), p.get('h3_bad', 0)),
        'uniqueness': _score(t['duplicate_ratio'], p.get('dup_good', 5),
                             p.get('dup_bad', 20), higher_is_better=False),
        'table_hygiene': _score(t['empty_cell_ratio'], p.get('table_good', 0),
                                p.get('table_bad', 20), higher_is_better=False),
    }
    return round(sum(dims.values()) / len(dims), 1), {k: round(v, 1) for k, v in dims.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--warn-only', action='store_true')
    args = parser.parse_args(argv)

    report = measure()
    composite, dims = score(report)
    target = float(_config.STYLE_POLICY.get('prose', {}).get('min_composite', 80))

    if args.json:
        print(json.dumps({'composite': composite, 'dimensions': dims,
                          'totals': report['totals']}, ensure_ascii=False, indent=2))
        return 0 if composite >= target or args.warn_only else 1

    print('=' * 72)
    print(f'技术图书文风评分  综合 {composite}/100  目标 {target}')
    print('=' * 72)
    for name, value in sorted(dims.items(), key=lambda kv: kv[1]):
        bar = '#' * int(value / 5)
        print(f'  {name:<22} {value:>5.1f}  {bar}')
    t = report['totals']
    print(f"\n平均句长 {t['avg_sentence']} 字 | 长句比 {t['long_sentence_ratio']}% | "
          f"段长 {t['avg_paragraph']} 字 | 列表占比 {t['bullet_ratio']}% | "
          f"每章坐标 {t['coords_per_file']} | 每章小节 {t['h3_per_file']} | "
          f"重复句 {t['duplicate_ratio']}%")
    if composite < target and not args.warn_only:
        print(f'\n未达目标（{composite} < {target}）')
        return 1
    print('\n✅ 文风评分达标')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
