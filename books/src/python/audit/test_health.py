#!/usr/bin/env python3
"""Test and structure health: the numbers behind the coverage ratchet.

The gates answer pass/fail; this report answers "where is the debt". It gathers
the readings that otherwise live in four different commands — the coverage of
the last run, the files furthest from their baseline, the files carrying the
most half-taken branches, the loose assertions the suite still accepts, and the
functions too long to test properly.

Usage:
  python test_health.py            # table
  python test_health.py --json

Readings only: nothing here fails a build. Thresholds come from
`base.json [toolchain]`, so the view and the gates never disagree about a number.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

PY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.normpath(os.path.join(_config.BOOK_ROOT, '..'))
TOP = 5


def _run(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(args, capture_output=True, text=True, cwd=REPO_ROOT, check=False)
    return proc.returncode, proc.stdout or ''


def coverage_snapshot() -> dict:
    """Coverage of the last run: total, thinnest files, branch-heavy files."""
    code, out = _run([sys.executable, '-m', 'coverage', 'json', '-o', '-'])
    if code != 0:
        return {}
    try:
        payload = json.loads(out)
    except ValueError:
        return {}
    totals = payload.get('totals') or {}
    files = []
    for name, data in (payload.get('files') or {}).items():
        summary = data.get('summary') or {}
        if int(summary.get('num_statements') or 0) < 5:
            continue
        files.append({'file': name,
                      'percent': round(float(summary.get('percent_covered') or 0.0), 1),
                      'statements': int(summary.get('num_statements') or 0),
                      'half_branches': int(summary.get('num_partial_branches') or 0),
                      'missing': int(summary.get('missing_lines') or 0)})
    return {
        'total_percent': round(float(totals.get('percent_covered') or 0.0), 1),
        'statements': int(totals.get('num_statements') or 0),
        'missing': int(totals.get('missing_lines') or 0),
        'half_branches': int(totals.get('num_partial_branches') or 0),
        'thinnest': sorted(files, key=lambda item: (item['percent'], -item['statements']))[:TOP],
        'branch_heavy': sorted(files, key=lambda item: -item['half_branches'])[:TOP],
        'files': files,
    }


def below_baseline(coverage: dict) -> list[dict]:
    """Files under the per-file baseline the coverage gate enforces."""
    path = os.path.join(_config.BOOK_ROOT, 'data', 'baselines', 'coverage.json')
    if not os.path.isfile(path) or not coverage:
        return []
    try:
        recorded = (_fsutil.load_json(path) or {}).get('files') or {}
    except (OSError, ValueError):
        return []
    current = {item['file']: item['percent'] for item in coverage['files']}
    return [{'file': name, 'baseline': float(before), 'now': current[name]}
            for name, before in sorted(recorded.items())
            if name in current and current[name] < float(before)]


def long_functions(threshold: int) -> list[dict]:
    """Functions past the length where branches stop being testable one by one."""
    found: list[dict] = []
    for folder, _, names in os.walk(PY_ROOT):
        for name in sorted(names):
            if not name.endswith('.py'):
                continue
            path = os.path.join(folder, name)
            try:
                tree = ast.parse(_fsutil.read_text(path))
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                length = (node.end_lineno or node.lineno) - node.lineno
                if length >= threshold:
                    found.append({'file': os.path.relpath(path, REPO_ROOT).replace(os.sep, '/'),
                                  'name': node.name, 'lines': length})
    return sorted(found, key=lambda item: -item['lines'])


def loose_assertions() -> int:
    """Cases whose only outcome check accepts both success and failure."""
    sys.path.insert(0, PY_ROOT)
    try:
        from audit import test_redundancy
        return len(test_redundancy.loose_candidates())
    except (ImportError, OSError):
        return -1


def collect() -> dict:
    threshold = int(_config.THRESHOLDS.get('function_length_warn', 60))
    coverage = coverage_snapshot()
    long_fns = long_functions(threshold)
    return {
        'coverage': coverage,
        'coverage_threshold': _config.THRESHOLDS.get('coverage_fail_under', 0),
        'below_baseline': below_baseline(coverage),
        'function_length_warn': threshold,
        'long_functions': long_fns,
        'loose_assertions': loose_assertions(),
    }


def render(payload: dict) -> None:
    coverage = payload['coverage']
    print('=' * 66)
    print('测试与结构健康（读数，不判红）')
    print('=' * 66)
    if not coverage:
        print('  覆盖率       无数据：先跑 `make.py cover`')
    else:
        print(f"  覆盖率       {coverage['total_percent']}%  "
              f"(阈值 {payload['coverage_threshold']}%；未覆盖 "
              f"{coverage['missing']}/{coverage['statements']} 语句，"
              f"{coverage['half_branches']} 个半分支)")
        print('  最薄的模块')
        for item in coverage['thinnest']:
            print(f"    {item['percent']:>5}%  {item['statements']:>4} 语句  {item['file']}")
        print('  半分支最多')
        for item in coverage['branch_heavy']:
            print(f"    {item['half_branches']:>4} 分支  {item['file']}")
    for item in payload['below_baseline']:
        print(f"  低于基线     {item['file']} {item['now']}% < {item['baseline']}%")
    loose = payload['loose_assertions']
    print(f"  松散断言     {'不可读' if loose < 0 else f'{loose} 条'}"
          '（基线内的已接受，新增会阻塞）')
    print(f"  ≥{payload['function_length_warn']} 行函数   {len(payload['long_functions'])} 个")
    for item in payload['long_functions'][:TOP]:
        print(f"    {item['lines']:>4} 行  {item['file']}::{item['name']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    payload = collect()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    render(payload)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
