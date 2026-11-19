#!/usr/bin/env python3
"""Delivery-speed baseline: keep step timings and flag regressions.

The tier runner appends one line per run to `books/logs/perf-history.jsonl`
(gitignored). This gate compares the newest run against the rolling median of
the previous ones, per step, and reports a regression when a step grows beyond
the configured factor plus a small absolute slack.

  compare()            newest run vs history (default: last 20 runs)
  record(summary)      append one run (called by check_runner)
  main --json          machine-readable report
  main --strict        exit 1 on a regression (default: advisory, exit 0)

Thresholds live in style.json [quality] as `perf_regression_factor` and
`perf_regression_slack_s`; defaults are 1.5x and 5s.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

HISTORY = os.path.join(_config.BOOK_ROOT, 'logs', 'perf-history.jsonl')
DEFAULT_WINDOW = 20
DEFAULT_FACTOR = 1.5
DEFAULT_SLACK = 5.0


def thresholds() -> tuple[float, float]:
    quality = (_config.STYLE_POLICY.get('quality') or {}) if hasattr(_config, 'STYLE_POLICY') else {}
    factor = float(quality.get('perf_regression_factor', DEFAULT_FACTOR))
    slack = float(quality.get('perf_regression_slack_s', DEFAULT_SLACK))
    return factor, slack


def record(summary: dict) -> str:
    """Append one run to the history file and return its path."""
    line = json.dumps({'ts': summary.get('ts') or '',
                       'mode': summary.get('mode', ''),
                       'seconds': summary.get('seconds', 0.0),
                       'steps': summary.get('steps', [])}, ensure_ascii=False)
    try:
        _fsutil.ensure_dir(HISTORY)
        with open(HISTORY, 'a', encoding='utf-8') as fh:
            fh.write(line + '\n')
    except OSError as exc:  # pragma: no cover - a read-only checkout still runs
        print(f'  [warn] cannot record the perf baseline: {exc}', file=sys.stderr)
    return HISTORY


def history(window: int = DEFAULT_WINDOW) -> list[dict]:
    if not os.path.isfile(HISTORY):
        return []
    runs = []
    try:
        with open(HISTORY, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    runs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return runs[-window:]


def compare(window: int = DEFAULT_WINDOW) -> dict:
    """Newest run against the median of the ones before it, per step and total."""
    runs = history(window + 1)
    if len(runs) < 2:
        return {'ok': True, 'reason': 'not enough history yet', 'runs': len(runs),
                'regressions': []}
    previous, latest = runs[:-1], runs[-1]
    factor, slack = thresholds()

    def median(values: list[float]) -> float:
        return statistics.median(values) if values else 0.0

    regressions = []
    per_step: dict[str, list[float]] = {}
    for run in previous:
        for step in run.get('steps') or []:
            per_step.setdefault(step.get('step', '?'), []).append(float(step.get('seconds', 0)))
    for step in latest.get('steps') or []:
        name = step.get('step', '?')
        current = float(step.get('seconds', 0))
        base = median(per_step.get(name, []))
        if base <= 0:
            continue
        limit = base * factor + slack
        if current > limit:
            regressions.append({'step': name, 'seconds': current,
                                'median': round(base, 2), 'limit': round(limit, 2),
                                'factor': factor})
    total_base = median([float(run.get('seconds', 0)) for run in previous])
    total = float(latest.get('seconds', 0))
    total_limit = total_base * factor + slack
    if total_base > 0 and total > total_limit:
        regressions.append({'step': 'TOTAL', 'seconds': round(total, 2),
                            'median': round(total_base, 2), 'limit': round(total_limit, 2),
                            'factor': factor})
    return {'ok': not regressions, 'runs': len(runs), 'mode': latest.get('mode', ''),
            'seconds': round(total, 2), 'regressions': regressions}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--strict', action='store_true',
                        help='exit 1 on a regression (default: advisory)')
    parser.add_argument('--window', type=int, default=DEFAULT_WINDOW)
    args = parser.parse_args(argv)

    report = compare(args.window)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if (args.strict and not report['ok']) else 0
    if report.get('reason'):
        print(f'ℹ️  {report["reason"]}（{report["runs"]} 次记录）')
        return 0
    if report['ok']:
        print(f'✅ 交付速度稳定（{report["runs"]} 次记录，最近 {report["seconds"]}s）')
        return 0
    print(f'交付速度回退 {len(report["regressions"])} 处：')
    for item in report['regressions']:
        print(f"  {item['step']:<12} {item['seconds']}s vs 中位 {item['median']}s "
              f"（阈值 {item['limit']}s）")
    return 1 if args.strict else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
