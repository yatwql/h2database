#!/usr/bin/env python3
"""Find tests that only pass in one order: run the suite twice, compare.

Fixture state, module-level caches and patched globals leak between suites; a
test that passes alone can fail after another suite has run. This gate measures
that directly instead of guessing:

  collect()   run the suite in this process, return {test id: outcome}
  compare()   diff a normal run against a reversed one
  main        spawn both runs as subprocesses and report the difference

The two runs happen in separate processes, so one cannot pollute the other:
`python order_dependence.py --run normal|reverse --json` is the worker.

Usage:
  python order_dependence.py             # both runs + comparison
  python order_dependence.py --json      # machine readable
  python order_dependence.py --only X    # limit the module set (comma separated)

Exit codes: 0 order-independent, 1 order-dependent cases found, 2 usage error.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import unittest
from typing import Any, cast

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config

TEST_DIR = os.path.join(_config.BOOK_ROOT, 'src', 'test')
WORKER_FLAG = '--run'


def _load_modules(reverse: bool, only: list[str] | None = None):
    """Load every test module in the requested order (no pattern guessing)."""
    if TEST_DIR not in sys.path:
        sys.path.insert(0, TEST_DIR)
    loader = unittest.TestLoader()
    names = sorted(name[:-3] for name in os.listdir(TEST_DIR)
                   if name.startswith('test_') and name.endswith('.py'))
    if only:
        wanted = {item.strip() for item in only}
        names = [name for name in names if name in wanted]
    if reverse:
        names.reverse()
    suite = unittest.TestSuite()
    for name in names:
        suite.addTests(loader.loadTestsFromName(name))
    return suite


class _Collector(unittest.TextTestResult):
    """Record each test's outcome instead of printing dots."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes: dict[str, str] = {}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes[str(test)] = 'ok'

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[str(test)] = 'fail'

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes[str(test)] = 'error'

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[str(test)] = 'skip'


def collect(reverse: bool = False, only: list[str] | None = None) -> dict[str, str]:
    """Run the suite in this process and return {test id: outcome}."""
    suite = _load_modules(reverse, only)
    stream = io.StringIO()          # swallow the dots: this is a measurement
    runner = unittest.TextTestRunner(stream=stream, verbosity=0, resultclass=_Collector)
    result = runner.run(suite)
    return cast(Any, result).outcomes


def compare(normal: dict[str, str], reverse: dict[str, str]) -> dict:
    """Cases whose outcome differs between the two orders."""
    flaky = []
    for name, outcome in sorted(normal.items()):
        other = reverse.get(name)
        if other is None or other == outcome:
            continue
        if 'skip' in (outcome, other):
            continue
        flaky.append({'test': name, 'normal': outcome, 'reverse': other})
    return {'ok': not flaky, 'normal_failures': sum(1 for value in normal.values()
                                                    if value != 'ok' and value != 'skip'),
            'reverse_failures': sum(1 for value in reverse.values()
                                    if value != 'ok' and value != 'skip'),
            'order_dependent': flaky}


def _worker(reverse: bool, only: str) -> int:
    outcomes = collect(reverse, [item.strip() for item in only.split(',')] if only else None)
    print(json.dumps({'reverse': reverse, 'outcomes': outcomes}, ensure_ascii=False))
    return 0


def run_both(only: str = '', timeout: float = 1800.0) -> dict:
    """Spawn the two worker runs and compare them."""
    payloads = []
    for reverse in (False, True):
        command = [sys.executable, os.path.abspath(__file__), WORKER_FLAG,
                   'reverse' if reverse else 'normal']
        if only:
            command += ['--only', only]
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding='utf-8', errors='replace',
                                timeout=timeout, check=False)
        if result.returncode != 0:
            raise SystemExit(f'error: worker failed ({result.returncode}): '
                             f'{(result.stderr or result.stdout)[-400:]}')
        payloads.append(json.loads(result.stdout.strip().splitlines()[-1]))
    return compare(payloads[0]['outcomes'], payloads[1]['outcomes'])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(WORKER_FLAG, choices=('normal', 'reverse'),
                        help='worker mode: run the suite in this process')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--only', default='', help='comma-separated module names')
    parser.add_argument('--timeout', type=float, default=1800.0)
    args = parser.parse_args(argv)

    if args.run:
        return _worker(args.run == 'reverse', args.only)

    report = run_both(args.only, args.timeout)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['ok'] else 1
    if report['ok']:
        print(f"✅ 无顺序依赖（normal {report['normal_failures']} 失败 / "
              f"reverse {report['reverse_failures']} 失败）")
        return 0
    print(f"顺序依赖用例 {len(report['order_dependent'])} 个：")
    for item in report['order_dependent'][:20]:
        print(f"  {item['test']}  normal={item['normal']}  reverse={item['reverse']}")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
