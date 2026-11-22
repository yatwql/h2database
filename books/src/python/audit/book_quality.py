#!/usr/bin/env python3
"""Book-level quality metrics for a generated manuscript.

Complements the structural gates with the metrics that decide whether the
manuscript reads like a technical book: boilerplate duplication across
chapters, fact density, the four-layer information ladder, table size, sentence
length, terminology linkage, cross references and exercise spread.

Thresholds live in books/data/config/config.json -> [quality].

Usage:
  python book_quality.py            # report + exit code
  python book_quality.py --json     # machine-readable
  python book_quality.py --warn-only  # never fail
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

LADDER = ('模块版图', '核心类型', '关键 API 与源码坐标', '阅读路径')
COORD_RE = re.compile(r'\.java:\d+')
EXERCISE_RE = re.compile(r'^\*\*\d+\.\s*([🟢🔵🟠])(★+)', re.MULTILINE)
H2_RE = re.compile(r'^## \d+\.(\d+)\s+(.+)$', re.MULTILINE)
SENT_SPLIT = re.compile(r'(?<=[。！？；.!?])\s*')
NORMALIZE = re.compile(r'[^\u4e00-\u9fffA-Za-z0-9]')


def _files() -> list[str]:
    """Chapters plus appendices, in the configured reading order."""
    return _config.chapter_files(include_cover=False)


def _sentences(text: str) -> list[str]:
    body = re.sub(r'```[\s\S]*?```', '', text)
    prose = '\n'.join(line for line in body.split('\n')
                      if not line.lstrip().startswith(('|', '>')))
    return [s.strip() for s in SENT_SPLIT.split(prose) if len(s.strip()) > 8]


def measure() -> dict:
    """Compute the metrics for the current manuscript."""
    terms = [t.strip() for t in re.findall(
        r'^- \*\*([^*]+)\*\*', _fsutil.read_text(_config.glossary_path()), re.MULTILINE)]
    dup_index: dict[str, set[str]] = {}
    per_file: dict[str, dict] = {}
    lines: list[str] = []
    sentences: list[str] = []

    for path in _files():
        enabled = os.path.isfile(path)
        if not enabled:
            continue
        text = _fsutil.read_text(path)
        name = os.path.basename(path)
        file_lines = [line for line in text.split('\n') if line.strip()]
        lines += file_lines
        file_sentences = _sentences(text)
        sentences += file_sentences
        for sentence in file_sentences:
            key = NORMALIZE.sub('', sentence)[:40]
            if len(key) > 20:
                dup_index.setdefault(key, set()).add(name)
        tables = [len(re.findall(r'^\| ', block, re.MULTILINE)) - 2
                  for block in re.split(r'\n\n', text)]
        per_file[name] = {
            'lines': len(file_lines),
            'coords': len(COORD_RE.findall(text)),
            'ladder': sum(bool(re.search(rf'## \d+\.\d+ {stage}', text)) for stage in LADDER),
            'max_table_rows': max(tables or [0]),
            'cross_refs': len(re.findall(r'详见第\d+章', text)),
            'exercises': len(EXERCISE_RE.findall(text)),
            'terms': sum(1 for term in terms if term in text),
            'h2': len(H2_RE.findall(text)),
        }

    duplicated = sum(1 for key, files in dup_index.items() if len(files) > 1)
    return {
        'totals': {
            'files': len(per_file),
            'lines': len(lines),
            'sentences': len(sentences),
            'avg_sentence_chars': round(sum(map(len, sentences)) / max(1, len(sentences)), 1),
            'long_lines': sum(1 for line in lines if len(line) > 160),
            'coords': sum(v['coords'] for v in per_file.values()),
            'duplicate_sentences': duplicated,
            'duplicate_ratio': round(100 * duplicated / max(1, len(dup_index)), 1),
            'exercises': sum(v['exercises'] for v in per_file.values()),
            'table_rows': sum(v['max_table_rows'] for v in per_file.values()),
        },
        'per_file': per_file,
    }


def failures(report: dict) -> list[str]:
    """Threshold checks from config.json -> [quality]."""
    q = _config.POLICY.get('quality', {})
    totals, per_file = report['totals'], report['per_file']
    problems: list[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        if not ok:
            problems.append(f'{name}: {detail}')

    body = {n: v for n, v in per_file.items() if n.startswith('ch')}
    check('duplicate_ratio', totals['duplicate_ratio'] <= q.get('max_duplicate_ratio', 12),
          f"{totals['duplicate_ratio']}% > {q.get('max_duplicate_ratio', 12)}%")
    check('avg_sentence_chars', totals['avg_sentence_chars'] <= q.get('max_avg_sentence', 45),
          f"{totals['avg_sentence_chars']} > {q.get('max_avg_sentence', 45)}")
    check('long_lines', totals['long_lines'] <= q.get('max_long_lines', 40),
          f"{totals['long_lines']} > {q.get('max_long_lines', 40)}")
    if body:
        check('chapter_coords', min(v['coords'] for v in body.values()) >= q.get('min_coords_per_chapter', 15),
              f"min {min(v['coords'] for v in body.values())}")
        check('chapter_ladder', all(v['ladder'] == 4 for v in body.values()),
              'a body chapter misses a ladder layer')
        lines_min = q.get('min_chapter_lines', 150)
        lines_max = q.get('max_chapter_lines', 450)
        check('chapter_length', all(lines_min <= v['lines'] <= lines_max for v in body.values()),
              f"outside {lines_min}-{lines_max}: "
              f"{[n for n, v in body.items() if not lines_min <= v['lines'] <= lines_max]}")
        check('table_rows', max(v['max_table_rows'] for v in per_file.values()) <= q.get('max_table_rows', 20),
              f"max {max(v['max_table_rows'] for v in per_file.values())}")
        check('cross_refs', all(v['cross_refs'] >= 1 for v in per_file.values()),
              'a file has no cross reference')
        check('terms', min(v['terms'] for v in per_file.values()) >= q.get('min_terms_per_chapter', 5),
              f"min {min(v['terms'] for v in per_file.values())}")
        check('exercises', min(v['exercises'] for v in per_file.values()) >= q.get('min_exercises_per_chapter', 4),
              f"min {min(v['exercises'] for v in per_file.values())}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true', help='machine-readable output')
    parser.add_argument('--warn-only', action='store_true', help='always exit 0')
    args = parser.parse_args(argv)

    report = measure()
    problems = failures(report)

    if args.json:
        print(json.dumps({'report': report, 'problems': problems}, ensure_ascii=False, indent=2))
        return 0 if (not problems or args.warn_only) else 1

    t = report['totals']
    print('=' * 72)
    print(f"技术图书质量度量  文件 {t['files']}  行 {t['lines']}  坐标 {t['coords']}  "
          f"重复句 {t['duplicate_sentences']}（{t['duplicate_ratio']}%）")
    print('=' * 72)
    for name, v in report['per_file'].items():
        print(f"  {name:<34} 行 {v['lines']:>4}  坐标 {v['coords']:>3}  阶梯 {v['ladder']}/4  "
              f"表 {v['max_table_rows']:>2}  引用 {v['cross_refs']}  练习 {v['exercises']}  术语 {v['terms']}")
    if problems:
        print('\n未达标：')
        for problem in problems:
            print(f'  - {problem}')
        if not args.warn_only:
            return 1
    else:
        print('\n✅ 技术图书质量度量全部达标')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
