#!/usr/bin/env python3
"""Turn a unittest/pytest log into a compact failure list.

CI logs are long; the interesting part is which case failed and why. This reads
a saved log (or stdin) and prints one line per failure, or JSON for tooling.

  python failure_extract.py books/logs/check-p0-*.log
  python failure_extract.py --json < log.txt
  python failure_extract.py --summary < log.txt

Exit codes: 0 no failures found, 1 failures found, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _errors

FAIL_RE = re.compile(r'^(?:FAIL|ERROR):\s+(\S+)\s+\(([^)]+)\)')
ASSERT_RE = re.compile(r'^(AssertionError|Assertion|ModuleNotFoundError|ImportError|'
                       r'KeyError|TypeError|ValueError|AttributeError|RuntimeError|'
                       r'SystemExit|FileNotFoundError|UnicodeDecodeError):?\s*(.*)$')
SUBTEST_RE = re.compile(r'\(([a-z_]+)=([^)]+)\)')


def parse(text: str) -> list[dict]:
    """Collect (case, module, reason) for every failure block."""
    failures: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        head = FAIL_RE.match(line.strip())
        if head:
            if current:
                failures.append(current)
            name, module = head.group(1), head.group(2)
            subtest = dict(SUBTEST_RE.findall(line))
            current = {'name': name, 'class': module.rsplit('.', 1)[-1],
                       'reason': '', 'subtest': subtest}
            continue
        if current is None:
            continue
        reason = ASSERT_RE.match(line.strip())
        if reason and not current['reason']:
            current['reason'] = f'{reason.group(1)}: {reason.group(2)}'.strip()
    if current:
        failures.append(current)
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('log', nargs='?', help='log file (default: stdin)')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--summary', action='store_true', help='counts only')
    args = parser.parse_args(argv)

    if args.log:
        try:
            with open(args.log, encoding='utf-8', errors='replace') as fh:
                text = fh.read()
        except OSError as exc:
            print(f'error: cannot read {args.log}: {exc}', file=sys.stderr)
            return 2
    else:
        text = sys.stdin.read()

    failures = parse(text)
    if args.json:
        print(json.dumps({'count': len(failures), 'failures': failures},
                         ensure_ascii=False, indent=2))
        return 0 if not failures else 1
    if args.summary:
        print(f'{len(failures)} failure(s)')
        for item in failures:
            print(f"  {item['class']}.{item['name']}")
        return 0 if not failures else 1
    if not failures:
        print('✅ 日志中没有失败用例')
        return 0
    print(f'失败用例 {len(failures)} 个：')
    for item in failures:
        sub = f"  {item['subtest']}" if item['subtest'] else ''
        print(f"  {item['class']}.{item['name']}{sub}")
        if item['reason']:
            print(f'    {item["reason"]}')
    return 1


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
