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
  python file_length.py --update-ledger   # write the measured lengths back
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil

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
LEDGER_ROW_RE = re.compile(r'^(\|\s*`)([^`]+)(`\s+)(\d+)(\s*行\s*\|)', re.MULTILINE)

# The last measurement the ledger was written from. Keeping it here means the gate
# compares growth against reality instead of against a number a person had to
# transcribe by hand: a row that drifted by a line is not news, a file that grew
# past the threshold without the ledger following is.
STATE_NAME = 'file-length.json'
GROWTH_DEFAULT = 10


def growth_limit() -> int:
    """Lines a registered file may grow before the ledger has to be updated."""
    raw = (_config.STYLE_POLICY.get('thresholds') or {}).get('ledger_growth', GROWTH_DEFAULT)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return GROWTH_DEFAULT


def measured(book_root: str | None = None) -> dict[str, int]:
    """Measured length of every file the ledger registers."""
    root = book_root or _config.BOOK_ROOT
    path = os.path.join(root, LEDGER_REL)
    out: dict[str, int] = {}
    if not os.path.isfile(path):
        return out
    for line in _fsutil.read_lines(path):
        match = LEDGER_ROW_RE.match(line)
        if match is None:
            continue
        target = os.path.join(root, match.group(2))
        if os.path.isfile(target):
            out[match.group(2)] = len(_fsutil.read_lines(target))
    return out


def read_state(path: str) -> dict[str, int]:
    """The lengths the ledger was last written from; empty when unreadable."""
    try:
        payload = json.loads(_fsutil.read_text(path))
    except (OSError, json.JSONDecodeError, _errors.ToolError):
        return {}
    files = payload.get('files') if isinstance(payload, dict) else None
    return {str(k): int(v) for k, v in (files or {}).items()
            if isinstance(v, (int, float))}


def write_state(book_root: str | None, lengths: dict[str, int]) -> str:
    """Record what the ledger now says; returns the path written."""
    path = _state_path(book_root)
    _fsutil.ensure_dir(path)
    _fsutil.write_text(path, json.dumps({'files': dict(sorted(lengths.items()))},
                                        ensure_ascii=False, indent=2) + '\n')
    return path


def _state_path(book_root: str | None = None) -> str:
    if book_root:
        return os.path.join(book_root, 'data', 'state', STATE_NAME)
    return _config.state_path(STATE_NAME)


def check_ledger(book_root: str | None = None) -> list[dict]:
    """Registered growth table rows stay true, and growth is not silently absorbed.

    Two questions, deliberately separate: a registered file that is gone is a broken
    ledger, and a file that has grown past the threshold since the ledger was last
    written is an out-of-date one. A row that disagrees by a few lines is neither —
    comparing every row against its exact count is what made this check demand a
    manual transcription on every run.
    """
    root = book_root or _config.BOOK_ROOT
    path = os.path.join(root, LEDGER_REL)
    if not os.path.isfile(path):
        return []
    limit = growth_limit()
    state = read_state(_state_path(book_root))
    out: list[dict] = []
    for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
        match = LEDGER_ROW_RE.match(line)
        if match is None:
            continue
        name, stated = match.group(2), int(match.group(4))
        target = os.path.join(root, name)
        if not os.path.isfile(target):
            out.append({'kind': 'LEDGER', 'file': LEDGER_REL, 'line': lineno,
                        'detail': f'{name} is registered but does not exist'})
            continue
        actual = len(_fsutil.read_lines(target))
        baseline = state.get(name, stated)
        if actual - baseline > limit:
            out.append({'kind': 'LEDGER', 'file': LEDGER_REL, 'line': lineno,
                        'detail': f'{name} 较登记时增长 {actual - baseline} 行'
                                  f'（登记 {stated} / 实测 {actual}），'
                                  '跑 --update-ledger 写回'})
    return out


def update_ledger(book_root: str | None = None) -> int:
    """Rewrite every registered length with the measurement; returns rows updated.

    The ledger stays hand-written prose — only the numbers a person should not be
    copying move, and the state file records what they were set from.
    """
    root = book_root or _config.BOOK_ROOT
    path = os.path.join(root, LEDGER_REL)
    if not os.path.isfile(path):
        return 0
    lengths = measured(book_root)
    updated = 0

    def rewrite(match: re.Match) -> str:
        nonlocal updated
        name = match.group(2)
        if name not in lengths:
            return match.group(0)
        updated += 1
        return f'{match.group(1)}{name}{match.group(3)}{lengths[name]}{match.group(5)}'

    _fsutil.write_text(path, LEDGER_ROW_RE.sub(rewrite, _fsutil.read_text(path)))
    write_state(book_root, lengths)
    return updated


def budgets() -> dict:
    limits = _config.STYLE_POLICY.get('limits') or {}
    return {kind: {**values, **limits.get(kind, {})} for kind, values in DEFAULTS.items()}


def check_declared_budgets() -> list[dict]:
    """Every budget kind declares its limit in the config, not only in a default.

    A default nobody restated is a threshold living in code, which is what the
    configuration rule forbids; it also leaves the documented numbers with nothing
    to point a reader at.
    """
    limits = _config.STYLE_POLICY.get('limits') or {}
    return [{'kind': 'BUDGET', 'detail': f'{kind} budget has no [limits] entry'}
            for kind in DEFAULTS if kind not in limits]


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


def scan(limits: dict) -> tuple[list[dict], list[dict]]:
    """Files over their budget, and files only past the warning line."""
    over, warn = [], []
    for path, kind in targets():
        lines = len(_fsutil.read_lines(path))
        name = os.path.relpath(path, os.path.join(_config.BOOK_ROOT, '..'))
        if lines > limits[kind]['limit']:
            over.append({'file': name, 'kind': kind, 'lines': lines,
                         'limit': limits[kind]['limit']})
        elif lines > limits[kind]['warn']:
            warn.append({'file': name, 'kind': kind, 'lines': lines,
                         'warn': limits[kind]['warn']})
    return over, warn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--update-ledger', action='store_true',
                        help='把台账里的行数写回为实测值（同时记下基线）')
    args = parser.parse_args(argv)

    if args.update_ledger:
        print(f'已更新台账 {update_ledger()} 行')
        return 0

    over, warn = scan(budgets())
    ledger = check_ledger()
    undeclared = check_declared_budgets()
    code = 0 if not over and not ledger and not undeclared else 1
    if args.json:
        print(json.dumps({'over': over, 'warn': warn, 'ledger': ledger,
                          'undeclared': undeclared},
                         ensure_ascii=False, indent=2))
        return code

    for item in warn:
        print(f"  warn  {item['file']}  {item['lines']} 行 > 提醒线 {item['warn']}")
    for item in ledger:
        print(f"  ledger  {item['file']}:{item['line']}  {item['detail']}")
    for item in undeclared:
        print(f"  budget  {item['detail']}")
    if not code:
        print('✅ 文件长度预算通过')
        return 0
    if over:
        print(f'超出长度上限 {len(over)} 个文件：')
        for item in over:
            print(f"  over  {item['file']}  {item['lines']} 行 > {item['limit']}（{item['kind']}）")
    return 1


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
