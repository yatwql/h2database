#!/usr/bin/env python3
"""Validate data/config/style.json before it can silently misconfigure the book.

Checks
  KEYS      only known top-level sections (a typo would otherwise be ignored)
  SHAPE     required keys present with the right types
  RANGE     thresholds are sane (min < max, ratios 0-100, positive budgets)

Exit 1 on any finding.

Usage:
  python style_schema.py
  python style_schema.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

STYLE_PATH = os.path.join(_config.BOOK_ROOT, 'data', 'config', 'style.json')
KNOWN_TOP = {'_note', '_schema', 'project', 'sections', 'captions', 'diagrams',
             'quality', 'prose', 'generation', 'limits', 'thresholds'}
REQUIRED = {
    'sections': ('per_chapter',),
    'captions': ('leading_verbs', 'vague_trailing', 'presets'),
    'quality': ('min_coords_per_chapter', 'min_chapter_lines', 'max_chapter_lines',
                'max_table_rows', 'max_duplicate_ratio'),
    'prose': ('avg_sentence_good', 'avg_sentence_bad', 'min_composite'),
    'generation': ('exercises_per_chapter', 'checklist_items'),
    'limits': ('sources', 'tests', 'docs'),
}


def load() -> dict:
    try:
        return json.loads(_fsutil.read_text(STYLE_PATH))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f'error: cannot read {STYLE_PATH}: {exc}') from exc


def validate(style: dict) -> list[str]:
    problems: list[str] = []
    unknown = set(style) - KNOWN_TOP
    if unknown:
        problems.append(f'unknown top-level keys: {sorted(unknown)}')
    for section, keys in REQUIRED.items():
        payload = style.get(section)
        if not isinstance(payload, dict):
            problems.append(f'[{section}] missing or not an object')
            continue
        for key in keys:
            if key not in payload:
                problems.append(f'[{section}].{key} missing')

    presets = (style.get('captions') or {}).get('presets') or {}
    for name in ('strict', 'normal', 'loose'):
        preset = presets.get(name)
        if not isinstance(preset, dict):
            problems.append(f'[captions.presets].{name} missing')
            continue
        low, high = preset.get('min_chars'), preset.get('max_chars')
        if not isinstance(low, int) or not isinstance(high, int) or low >= high:
            problems.append(f'[captions.presets].{name}: min_chars must be < max_chars')
        if not isinstance(preset.get('fail_at'), int) or preset['fail_at'] < 0:
            problems.append(f'[captions.presets].{name}: fail_at must be >= 0')

    quality = style.get('quality') or {}
    if isinstance(quality.get('min_chapter_lines'), int) and \
            isinstance(quality.get('max_chapter_lines'), int) and \
            quality['min_chapter_lines'] >= quality['max_chapter_lines']:
        problems.append('[quality]: min_chapter_lines must be < max_chapter_lines')
    ratio = quality.get('max_duplicate_ratio')
    if not isinstance(ratio, (int, float)) or not 0 <= ratio <= 100:
        problems.append('[quality].max_duplicate_ratio must be within 0-100')

    prose = style.get('prose') or {}
    for good, bad in (('avg_sentence_good', 'avg_sentence_bad'),
                      ('dup_good', 'dup_bad'), ('bullet_good', 'bullet_bad')):
        if good in prose and bad in prose and prose[good] > prose[bad]:
            problems.append(f'[prose].{good} must be <= {bad}')
    composite = prose.get('min_composite')
    if not isinstance(composite, (int, float)) or not 0 < composite <= 100:
        problems.append('[prose].min_composite must be within (0, 100]')

    for kind, values in (style.get('limits') or {}).items():
        if not isinstance(values, dict) or 'limit' not in values:
            problems.append(f'[limits].{kind} needs limit/warn')
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    problems = validate(load())
    if args.json:
        print(json.dumps({'count': len(problems), 'problems': problems},
                         ensure_ascii=False, indent=2))
        return 0 if not problems else 1

    if not problems:
        print('✅ style.json 结构合规')
        return 0
    print(f'style.json 结构问题 {len(problems)} 处：')
    for problem in problems:
        print(f'  - {problem}')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
