#!/usr/bin/env python3
"""Enforce file-length budgets so files stay reviewable.

Budgets (lines, from style.json -> [limits]):
  sources    books/src/python/**   default 800, warn 600
  tests      books/src/test/**     default 1200, warn 900
  docs       books/**/*.md         default 1200, warn 900

The growth ledger (review-findings.md) is checked too: a registered row must name
an existing file with its measured length.

Exit 1 when a hard budget is exceeded or the ledger disagrees with measurement.

Usage:
  python file_length.py
  python file_length.py --json
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

DEFAULTS = {
    'sources': {'limit': 900, 'warn': 700},
    'tests': {'limit': 1200, 'warn': 900},
    'docs': {'limit': 1200, 'warn': 900},
    # narrative appendices legitimately grow beyond the doc budget
    'manuscript': {'limit': 2000, 'warn': 1500},
}

# the growth ledger in review-findings.md is a registration: every row names a file
# and its measured length, so both fall out of date together unless compared
LEDGER_REL = os.path.join('docs', 'managements', 'review-findings.md')
LEDGER_ROW_RE = re.compile(r'^\|\s*`([^`]+)`\s+(\d+)\s*行\s*\|')


def check_ledger(book_root: str | None = None) -> list[dict]:
    """Registered growth table rows state the measured length of a real file.

    The table records which files are close to their budget and how they would be
    split. A stale number there is worse than no number: it is the input to the
    next split decision.
    """
    root = book_root or _config.BOOK_ROOT
    path = os.path.join(root, LEDGER_REL)
    if not os.path.isfile(path):
        return []
    out: list[dict] = []
    for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
        match = LEDGER_ROW_RE.match(line)
        if match is None:
            continue
        name, stated = match.group(1), int(match.group(2))
        target = os.path.join(root, name)
        if not os.path.isfile(target):
            out.append({'kind': 'LEDGER', 'file': LEDGER_REL, 'line': lineno,
                        'detail': f'{name} is registered but does not exist'})
            continue
        actual = len(_fsutil.read_lines(target))
        if actual != stated:
            out.append({'kind': 'LEDGER', 'file': LEDGER_REL, 'line': lineno,
                        'detail': f'{name} registered as {stated} lines, measured {actual}'})
    return out


def budgets() -> dict:
    limits = _config.STYLE_POLICY.get('limits') or {}
    return {kind: {**values, **limits.get(kind, {})} for kind, values in DEFAULTS.items()}


def targets() -> list[tuple[str, str]]:
    root = _config.BOOK_ROOT
    out: list[tuple[str, str]] = []
    out += [(p, 'sources') for p in glob.glob(os.path.join(root, 'src', 'python', '**', '*.py'), recursive=True)]
    out += [(p, 'tests') for p in glob.glob(os.path.join(root, 'src', 'test', '**', '*.py'), recursive=True)]
    manuscript = os.path.join(root, 'data', 'manuscript')
    skip = _config.excluded_dirs()
    docs = [p for p in glob.glob(os.path.join(root, '**', '*.md'), recursive=True)
            if not p.startswith(manuscript) and not p.startswith(skip)]
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

    ledger = check_ledger()
    if args.json:
        print(json.dumps({'over': over, 'warn': warn, 'ledger': ledger},
                         ensure_ascii=False, indent=2))
        return 0 if not over and not ledger else 1

    for item in warn:
        print(f"  warn  {item['file']}  {item['lines']} 行 > 提醒线 {item['warn']}")
    for item in ledger:
        print(f"  ledger  {item['file']}:{item['line']}  {item['detail']}")
    if not over and not ledger:
        print('✅ 文件长度预算通过')
        return 0
    if over:
        print(f'超出长度上限 {len(over)} 个文件：')
        for item in over:
            print(f"  over  {item['file']}  {item['lines']} 行 > {item['limit']}（{item['kind']}）")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
