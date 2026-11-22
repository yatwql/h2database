#!/usr/bin/env python3
"""Find tests that only pass in one order: run the suite twice, compare.

Fixture state, module-level caches and patched globals leak between suites; a
test that passes alone can fail after another suite has run. This gate measures
that directly instead of guessing:

  collect()   run the suite in this process, return {test id: outcome}
  compare()   diff a normal run against a reversed one
  bisect()    given one known-bad case, shrink the preceding modules to the
              smallest set that still makes it fail (the polluting prefix)
  main        spawn both runs as subprocesses and report the difference, or
              bisect one case with --bisect

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
    try:
        names = sorted(name[:-3] for name in os.listdir(TEST_DIR)
                       if name.startswith('test_') and name.endswith('.py'))
    except OSError as exc:
        raise SystemExit(f'error: cannot list {TEST_DIR}: {exc}') from exc
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
        self.outcomes[test.id()] = 'ok'

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcomes[test.id()] = 'fail'

    def addError(self, test, err):
        super().addError(test, err)
        self.outcomes[test.id()] = 'error'

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[test.id()] = 'skip'


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


def run_prefix(modules: list[str], target: str) -> str | None:
    """Outcome of ``target`` when the given modules run before it."""
    if TEST_DIR not in sys.path:
        sys.path.insert(0, TEST_DIR)
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in modules:
        try:
            suite.addTests(loader.loadTestsFromName(name))
        except (ImportError, ValueError):
            continue
    try:
        suite.addTests(loader.loadTestsFromName(target))
    except (ImportError, ValueError):
        return None
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=0, resultclass=_Collector)
    result = runner.run(suite)
    outcomes = cast(Any, result).outcomes
    for name, outcome in outcomes.items():
        if name.startswith(target + '.'):
            return outcome
    return None


def _all_modules() -> list[str]:
    """Every test module name in the suite directory, sorted."""
    try:
        return [name[:-3] for name in sorted(os.listdir(TEST_DIR))
                if name.startswith('test_') and name.endswith('.py')]
    except OSError as exc:
        raise SystemExit(f'error: cannot list {TEST_DIR}: {exc}') from exc


def bisect(target_module: str, max_steps: int = 20,
           pool: list[str] | None = None) -> dict:
    """Shrink the modules that run before ``target_module`` to the polluting set.

    Preconditions: the target passes alone and fails when the whole suite runs
    before it. The result names the smallest prefix (to the bisection's
    resolution) that still makes the target fail.

    ``pool`` bounds the modules considered as the prefix. The default is the
    whole suite, which re-runs every slow module just to answer a question about
    one test; a caller that only needs the mechanism passes its own small pool.
    """
    modules = list(pool) if pool is not None else _all_modules()
    if target_module not in modules:
        modules.append(target_module)
    others = [name for name in modules if name != target_module]

    alone = run_prefix([], target_module)
    if alone != 'ok':
        return {'ok': False, 'reason': f'{target_module} does not pass on its own '
                                       f'(outcome={alone}); not order-dependent',
                'prefix': []}
    full = run_prefix(others, target_module)
    if full == 'ok':
        return {'ok': True, 'reason': 'target passes in the full order too',
                'prefix': []}

    low, high = 0, len(others)
    steps = 0
    while low + 1 < high and steps < max_steps:
        steps += 1
        mid = (low + high) // 2
        if run_prefix(others[:mid], target_module) == 'ok':
            low = mid
        else:
            high = mid
    culprit = others[:high]
    return {'ok': True, 'target': target_module, 'failing_outcome': full,
            'prefix': culprit, 'prefix_size': len(culprit), 'steps': steps}


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
        try:
            payloads.append(json.loads(result.stdout.strip().splitlines()[-1]))
        except (IndexError, json.JSONDecodeError) as exc:
            raise SystemExit(f'error: worker printed no JSON: {exc}') from exc
    return compare(payloads[0]['outcomes'], payloads[1]['outcomes'])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(WORKER_FLAG, choices=('normal', 'reverse'),
                        help='worker mode: run the suite in this process')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--only', default='', help='comma-separated module names')
    parser.add_argument('--timeout', type=float, default=1800.0)
    parser.add_argument('--bisect', metavar='MODULE',
                        help='shrink the modules that make MODULE fail')
    parser.add_argument('--pool', default='',
                        help='comma-separated modules to consider as the prefix '
                             '(default: the whole suite, which re-runs every slow module)')
    args = parser.parse_args(argv)

    if args.run:
        return _worker(args.run == 'reverse', args.only)

    if args.bisect:
        pool = [name.strip() for name in args.pool.split(',') if name.strip()] or None
        result = bisect(args.bisect, pool=pool)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result['ok'] else 2
        if not result['ok']:
            print(f"无法二分：{result['reason']}")
            return 2
        if not result.get('prefix_size'):
            print(f"目标 {args.bisect} 在完整顺序下仍然通过，无需二分")
            return 0
        print(f"目标 {args.bisect} 失败时，最小前置集合 "
              f"（{result['prefix_size']} 个模块，{result['steps']} 步）：")
        for name in result['prefix']:
            print(f'  {name}')
        return 0

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
