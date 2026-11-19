#!/usr/bin/env python3
"""Enforce file-length budgets so files stay reviewable.

Budgets (lines, from style.json -> [limits]):
  sources    books/src/python/**   default 800, warn 600
  tests      books/src/test/**     default 1200, warn 900
  docs       books/**/*.md         default 1200, warn 900

Exit 1 when a hard budget is exceeded.

Usage:
  python file_length.py
  python file_length.py --json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

DEFAULTS = {
    'sources': {'limit': 900, 'warn': 700},
    'tests': {'limit': 1200, 'warn': 900},
    'docs': {'limit': 1200, 'warn': 900},
    # narrative appendices legitimately grow beyond the doc budget
    'manuscript': {'limit': 2000, 'warn': 1500},
}


def budgets() -> dict:
    limits = _config.STYLE_POLICY.get('limits') or {}
    return {kind: {**values, **limits.get(kind, {})} for kind, values in DEFAULTS.items()}


def targets() -> list[tuple[str, str]]:
    root = _config.BOOK_ROOT
    out: list[tuple[str, str]] = []
    out += [(p, 'sources') for p in glob.glob(os.path.join(root, 'src', 'python', '**', '*.py'), recursive=True)]
    out += [(p, 'tests') for p in glob.glob(os.path.join(root, 'src', 'test', '**', '*.py'), recursive=True)]
    manuscript = os.path.join(root, 'data', 'manuscript')
    docs = [p for p in glob.glob(os.path.join(root, '**', '*.md'), recursive=True)
            if not p.startswith(manuscript) and os.sep + 'dist' + os.sep not in p]
    out += [(p, 'docs') for p in docs]
    out += [(p, 'manuscript') for p in glob.glob(os.path.join(manuscript, '**', '*.md'), recursive=True)]
    return sorted(set(out))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    limits = budgets()
    over, warn = [], []
    for path, kind in targets():
        lines = len(_fsutil.read_lines(path))
        if lines > limits[kind]['limit']:
            over.append({'file': os.path.relpath(path, os.path.join(_config.BOOK_ROOT, '..')),
                         'kind': kind, 'lines': lines, 'limit': limits[kind]['limit']})
        elif lines > limits[kind]['warn']:
            warn.append({'file': os.path.relpath(path, os.path.join(_config.BOOK_ROOT, '..')),
                         'kind': kind, 'lines': lines, 'warn': limits[kind]['warn']})

    if args.json:
        print(json.dumps({'over': over, 'warn': warn}, ensure_ascii=False, indent=2))
        return 0 if not over else 1

    for item in warn:
        print(f"  warn  {item['file']}  {item['lines']} 行 > 提醒线 {item['warn']}")
    if not over:
        print('✅ 文件长度预算通过')
        return 0
    print(f'超出长度上限 {len(over)} 个文件：')
    for item in over:
        print(f"  over  {item['file']}  {item['lines']} 行 > {item['limit']}（{item['kind']}）")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
