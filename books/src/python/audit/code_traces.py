#!/usr/bin/env python3
"""Reject process/history traces in code comments and docstrings.

Code should explain why it is the way it is, not which review round produced
it. Version history lives in changelog.md.

Usage:
  python code_traces.py
  python code_traces.py --json
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

TRACES: tuple[tuple[str, str], ...] = (
    ('review-round', r'第\s*\d+\s*轮|round\s*\d+|R\d+\s*[-－]\s*\d+'),
    ('retrospective', r'复盘|评审记录|评审发现'),
    ('batch', r'第\s*\d+\s*批|batch\s*\d+'),
    ('relative-time', r'本次(?:迭代|改动|提交)|上一轮|本轮|新加的|临时绕过'),
    ('phase-label', r'Phase [A-H]\b|第[0-9一二三四五六七八九十]+轮'),
    ('migration-note', r'迁移自|由.{0,12}迁移|旧版本时|以前是'),
)


def code_files() -> list[str]:
    root = os.path.join(_config.BOOK_ROOT, 'src')
    return sorted(glob.glob(os.path.join(root, '**', '*.py'), recursive=True))


def _comment_lines(text: str) -> list[tuple[int, str]]:
    out = []
    for lineno, line in enumerate(text.split('\n'), start=1):
        stripped = line.strip()
        if stripped.startswith(('#', '*')) or '"""' in line:
            out.append((lineno, stripped))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    findings = []
    for path in code_files():
        for lineno, line in _comment_lines(_fsutil.read_text(path)):
            for kind, pattern in TRACES:
                if re.search(pattern, line):
                    findings.append({'file': os.path.relpath(path, os.path.join(_config.BOOK_ROOT, '..')),
                                     'line': lineno, 'kind': kind, 'text': line[:120]})

    if args.json:
        print(json.dumps({'count': len(findings), 'findings': findings},
                         ensure_ascii=False, indent=2))
        return 0 if not findings else 1

    if not findings:
        print('✅ 代码注释无历史痕迹')
        return 0
    print(f'代码历史痕迹 {len(findings)} 处：')
    for item in findings[:40]:
        print(f"  {item['file']}:{item['line']}  [{item['kind']}] {item['text']}")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
