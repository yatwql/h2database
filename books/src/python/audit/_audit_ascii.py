#!/usr/bin/env python3
"""Audit ASCII diagrams inside ```text fenced blocks.

Checks that no other gate covers:

  WIDE_LINE    rendered width (CJK counts as 2 columns) exceeds the print budget
  TRAILING_WS  trailing whitespace inside a diagram (invisible in editors,
               visible in print when the block wraps)
  TAB_CHAR     a tab inside a diagram (breaks column alignment)
  MIXED_BOX    one diagram mixes box-drawing borders (─│┌┐└┘├┤) with ASCII
               `+--+` borders, which renders ragged

Width budget: book.toml -> [thresholds].ascii_max_cols.

Existing violations are recorded in
``books/docs/managements/ascii-baseline.json`` so the gate only fails on NEW
ones. After deliberately fixing or adding diagrams:

  python _audit_ascii.py --update-baseline

Usage:
  python _audit_ascii.py                 # report; exit 1 on new violations
  python _audit_ascii.py --json          # machine readable
  python _audit_ascii.py --target 'ch3*.md'
  python _audit_ascii.py --update-baseline
"""

from __future__ import annotations

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import unicodedata

from lib import _config, _fsutil

BOX_CHARS = set('─│┌┐└┘├┤┬┴┼━┃┏┓┗┛┣┫┳┻╋═║╔╗╚╝╠╣╦╩╬')
BASELINE_PATH = _config.baseline_path('ascii')

_ASCII_BORDER_RE = re.compile(r'^\s*\+[-+]{2,}\+\s*$')
_ASCII_EDGE_RE = re.compile(r'^\s*\|.*\|\s*$')
_BOX_EDGE_RE = re.compile(r'^\s*[┌└├│┏┗┣╔╚╠].*[┐┘┤│┓┛┫╗╝╣]\s*$')

Violation = tuple[str, int, str, str]  # file, line, kind, detail

def display_width(text: str) -> int:
    """Print width in columns: East-Asian wide/fullwidth characters take two."""
    return sum(2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
               for ch in text)

def text_blocks(lines: list[str]) -> list[tuple[int, list[str]]]:
    """Return (1-based first line, lines) for ```text and bare ``` fences."""
    blocks: list[tuple[int, list[str]]] = []
    lang: str | None = None
    start = 0
    current: list[str] = []
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.rstrip('\n')
        if stripped.strip().startswith('```'):
            if lang is None:
                lang = stripped.strip()[3:].strip()
                start = idx + 1
                current = []
            else:
                if lang in ('', 'text'):
                    blocks.append((start, current))
                lang = None
                current = []
            continue
        if lang is not None:
            current.append(stripped)
    return blocks

def _mixes_borders(block: list[str]) -> bool:
    """True when one diagram uses both box-drawing and ASCII borders."""
    has_box = any(_BOX_EDGE_RE.match(line) for line in block)
    has_ascii = any(_ASCII_BORDER_RE.match(line) or _ASCII_EDGE_RE.match(line)
                    for line in block)
    return has_box and has_ascii

def audit_file(path: str, max_cols: int) -> list[Violation]:
    out: list[Violation] = []
    lines = _fsutil.read_lines(path)
    for start, block in text_blocks(lines):
        if _mixes_borders(block):
            out.append((path, start, 'MIXED_BOX',
                        'diagram mixes box-drawing and ASCII borders'))
        for offset, line in enumerate(block):
            lineno = start + offset
            if line != line.rstrip():
                out.append((path, lineno, 'TRAILING_WS',
                            'trailing whitespace inside diagram'))
            if '\t' in line:
                out.append((path, lineno, 'TAB_CHAR',
                            'tab character inside diagram'))
            width = display_width(line)
            if width > max_cols:
                out.append((path, lineno, 'WIDE_LINE',
                            f'width {width} > {max_cols} columns'))
    return out

def target_files(pattern: str | None) -> list[str]:
    if pattern:
        return sorted(glob.glob(os.path.join(_config.MANUSCRIPT_DIR, pattern)))
    return [p for p in _config.all_manuscript_files() if p.endswith('.md')]

def scan(pattern: str | None = None) -> list[Violation]:
    max_cols = int(_config.THRESHOLDS.get('ascii_max_cols', 100))
    violations: list[Violation] = []
    for path in target_files(pattern):
        violations.extend(audit_file(path, max_cols))
    return sorted(violations, key=lambda v: (v[0], v[1], v[2]))

def _rel(path: str) -> str:
    return os.path.relpath(path, _config.MANUSCRIPT_DIR).replace(os.sep, '/')

def _line_text(path: str, lineno: int) -> str:
    try:
        return _fsutil.read_lines(path)[lineno - 1].rstrip()
    except (SystemExit, IndexError):
        return ''

def _key(path: str, lineno: int, kind: str) -> str:
    digest = hashlib.sha256(_line_text(path, lineno).strip().encode('utf-8'))
    return f'{_rel(path)}::{kind}::{digest.hexdigest()[:12]}'

def load_baseline() -> set[str]:
    if not os.path.isfile(BASELINE_PATH):
        return set()
    try:
        with open(BASELINE_PATH, encoding='utf-8') as fh:
            return set(json.load(fh).get('accepted', []))
    except (OSError, json.JSONDecodeError, AttributeError) as exc:
        print(f'  [WARN] cannot read baseline {BASELINE_PATH}: {exc}', file=sys.stderr)
        return set()

def save_baseline(violations: list[Violation]) -> None:
    payload = {
        'note': 'Accepted ASCII diagram violations. Refresh with --update-baseline.',
        'accepted': sorted(_key(p, line, kind) for p, line, kind, _d in violations),
    }
    _fsutil.ensure_dir(BASELINE_PATH)
    _fsutil.write_text(BASELINE_PATH, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true', help='machine-readable output')
    parser.add_argument('--target', metavar='GLOB', help='restrict to matching files')
    parser.add_argument('--update-baseline', action='store_true',
                        help='record the current violations as accepted')
    args = parser.parse_args(argv)

    violations = scan(args.target)

    if args.update_baseline:
        save_baseline(violations)
        print(f'baseline updated: {len(violations)} accepted -> '
              f'{os.path.relpath(BASELINE_PATH, _config.BOOK_ROOT)}')
        return 0

    accepted = load_baseline()
    new = [v for v in violations if _key(v[0], v[1], v[2]) not in accepted]

    if args.json:
        print(json.dumps({
            'count': len(violations),
            'new': len(new),
            'violations': [
                {'file': _rel(p), 'line': line, 'kind': kind, 'detail': detail,
                 'new': _key(p, line, kind) not in accepted}
                for p, line, kind, detail in violations
            ],
        }, ensure_ascii=False, indent=2))
        return 0 if not new else 1

    if not new:
        print(f'✅ ASCII 图检查通过（已知 {len(violations)} 项在基线内）')
        return 0

    by_kind: dict[str, int] = {}
    for _p, _line, kind, _detail in new:
        by_kind[kind] = by_kind.get(kind, 0) + 1
    print('=' * 72)
    print(f'ASCII 图质量审计  新增违规：{len(new)}（已知 {len(violations) - len(new)}）  ' +
          '  '.join(f'{k}={v}' for k, v in sorted(by_kind.items())))
    print('=' * 72)
    for path, line, kind, detail in new[:60]:
        print(f'  {_rel(path)}:{line}  [{kind}] {detail}')
    if len(new) > 60:
        print(f'  ... and {len(new) - 60} more')
    print('  (review, then: --update-baseline)')
    return 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
