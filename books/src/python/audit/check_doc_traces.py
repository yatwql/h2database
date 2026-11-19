#!/usr/bin/env python3
"""Reject process/history traces in documentation.

Documentation must describe the current state only: no review rounds, no
"batch N", no dated iteration logs, no completed-work ledgers. Version history
belongs in changelog.md and is exempt.

Exit 1 when a trace pattern is found.

Usage:
  python check_doc_traces.py            # report
  python check_doc_traces.py --json
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

# Files that legitimately carry history.
EXEMPT = ('changelog.md',)

TRACES: tuple[tuple[str, str], ...] = (
    ('review-round', r'第\s*\d+\s*轮|R\d+\s*[-－]\s*\d+|轮次'),
    ('retrospective', r'复盘|回顾会|评审记录|评审发现'),
    ('batch', r'第\s*\d+\s*批|批\s*\d+|batch\s*\d+'),
    ('dated-plan-ref', r'2026-\d{2}-\d{2}-\d{3}'),
    ('ledger', r'已完成清单|遗留问题|未闭环|TODO\s*[（(]历史'),
    ('relative-time', r'本次(?:迭代|改动|提交)|上一轮|本轮|目前已完成'),
)


def doc_files() -> list[str]:
    """Documentation and repository-level guides (manuscript and dist are content)."""
    files = glob.glob(os.path.join(_config.BOOK_ROOT, 'docs', '**', '*.md'), recursive=True)
    files.append(os.path.join(_config.BOOK_ROOT, 'README.md'))
    files.append(os.path.join(_config.BOOK_ROOT, '..', 'CLAUDE.md'))
    return sorted({os.path.normpath(p) for p in files if os.path.isfile(p)})


def scan(path: str) -> list[tuple[int, str, str]]:
    """Return (line, kind, text) for every trace-looking line."""
    if any(path.endswith(name) for name in EXEMPT):
        return []
    hits = []
    for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
        for kind, pattern in TRACES:
            if re.search(pattern, line):
                hits.append((lineno, kind, line.strip()[:120]))
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    findings = []
    for path in doc_files():
        for lineno, kind, text in scan(path):
            findings.append({'file': os.path.relpath(path, os.path.join(_config.BOOK_ROOT, '..')),
                             'line': lineno, 'kind': kind, 'text': text})

    if args.json:
        print(json.dumps({'count': len(findings), 'findings': findings},
                         ensure_ascii=False, indent=2))
        return 0 if not findings else 1

    if not findings:
        print('✅ 文档无历史痕迹')
        return 0
    print(f'文档历史痕迹 {len(findings)} 处：')
    for item in findings[:40]:
        print(f"  {item['file']}:{item['line']}  [{item['kind']}] {item['text']}")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
