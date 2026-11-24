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
import contextlib
import datetime
import json
import os
import statistics
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil

HISTORY = os.path.join(_config.BOOK_ROOT, 'logs', 'perf-history.jsonl')
# The reviewed floor lives with the other baselines and is versioned; the rolling
# window is scratch. One file for both let an append-only log double as the reference
# it is measured against, so pruning the log moved the target.
BASELINE = os.path.join(_config.BOOK_ROOT, 'data', 'baselines', 'perf-baseline.json')
DEFAULT_WINDOW = 20
DEFAULT_RUNS = 200
DEFAULT_FACTOR = 1.5
DEFAULT_SLACK = 5.0


def thresholds() -> tuple[float, float]:
    quality = (_config.STYLE_POLICY.get('quality') or {}) if hasattr(_config, 'STYLE_POLICY') else {}
    factor = float(quality.get('perf_regression_factor', DEFAULT_FACTOR))
    slack = float(quality.get('perf_regression_slack_s', DEFAULT_SLACK))
    return factor, slack


def window_runs() -> int:
    """How many runs the rolling window keeps, from style.json [quality]."""
    quality = (_config.STYLE_POLICY.get('quality') or {}) if hasattr(_config, 'STYLE_POLICY') else {}
    try:
        return max(1, int(quality.get('perf_history_runs', DEFAULT_RUNS)))
    except (TypeError, ValueError):
        return DEFAULT_RUNS


def _trim(path: str) -> None:
    """Cap the rolling window, keeping the newest runs.

    A log that only grows is a log nobody reads: 11k runs and 1.6 MB answered "how
    fast was the build in March" badly and "how fast is it now" not at all. The
    window keeps enough samples for a median and is rewritten in one atomic replace,
    so a crash mid-trim cannot truncate the history.
    """
    limit = window_runs()
    try:
        with open(path, encoding='utf-8') as handle:
            lines = [line for line in handle if line.strip()]
    except OSError:
        return
    if len(lines) <= int(limit * 1.2):
        return
    tmp = path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as handle:
            handle.writelines(lines[-limit:])
        os.replace(tmp, path)
    except OSError:  # pragma: no cover - a read-only checkout still runs
        with contextlib.suppress(OSError):
            os.remove(tmp)


def record(summary: dict) -> str:
    """Append one run to the rolling window and return its path."""
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
    _trim(HISTORY)
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


def _medians(runs: list[dict]) -> dict:
    """Per-step and total medians over a set of runs, as the reference numbers."""
    per_step: dict[str, list[float]] = {}
    totals: list[float] = []
    for run in runs:
        totals.append(float(run.get('seconds', 0)))
        for step in run.get('steps') or []:
            per_step.setdefault(step.get('step', '?'), []).append(float(step.get('seconds', 0)))
    return {'steps': {name: round(statistics.median(values), 2)
                      for name, values in per_step.items() if values},
            'total': round(statistics.median(totals), 2) if totals else 0.0}


def load_baseline() -> dict:
    """The reviewed floor, or {} when none has been taken yet."""
    try:
        with open(BASELINE, encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_baseline(reviewed_by: str = '', reason: str = '',
                  window: int = DEFAULT_WINDOW) -> str:
    """Fix the current medians as the reviewed floor, with who and on what commit.

    The rolling window says how fast the build is now; the floor says how fast it was
    agreed to be. Recording the reviewer and the commit is what lets a later reader
    tell a deliberate slowdown from an accident -- the same shape as the content
    volume baseline.
    """
    runs = history(window)
    payload = {'reviewed': {'by': reviewed_by,
                            'at': datetime.datetime.now().isoformat(timespec='seconds'),
                            'commit': _git_commit(),
                            'reason': reason,
                            'runs': len(runs)},
               **_medians(runs)}
    _fsutil.ensure_dir(BASELINE)
    _fsutil.write_text(BASELINE, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    return BASELINE


def _git_commit() -> str:
    try:
        proc = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                              cwd=_config.BOOK_ROOT, capture_output=True, text=True,
                              check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - no git
        return ''
    return proc.stdout.strip() if proc.returncode == 0 else ''


def compare(window: int = DEFAULT_WINDOW) -> dict:
    """Newest run against the median of the ones before it, per step and total."""
    runs = history(window + 1)
    if len(runs) < 2:
        return {'ok': True, 'reason': 'not enough history yet', 'runs': len(runs),
                'regressions': []}
    previous, latest = runs[:-1], runs[-1]
    factor, slack = thresholds()

    # the reviewed floor when there is one, else the median of the window: a floor
    # that moves with the log cannot tell a regression from the new normal
    floor = load_baseline()
    reference = floor.get('steps') or _medians(previous)['steps']
    source = 'baseline' if floor else 'history'

    regressions = []
    for step in latest.get('steps') or []:
        name = step.get('step', '?')
        current = float(step.get('seconds', 0))
        base = float(reference.get(name, 0.0))
        if base <= 0:
            continue
        limit = base * factor + slack
        if current > limit:
            regressions.append({'step': name, 'seconds': current,
                                'median': round(base, 2), 'limit': round(limit, 2),
                                'factor': factor})
    total_base = float(floor.get('total') or
                       _medians(previous)['total'])
    total = float(latest.get('seconds', 0))
    total_limit = total_base * factor + slack
    if total_base > 0 and total > total_limit:
        regressions.append({'step': 'TOTAL', 'seconds': round(total, 2),
                            'median': round(total_base, 2), 'limit': round(total_limit, 2),
                            'factor': factor})
    return {'ok': not regressions, 'runs': len(runs), 'source': source,
            'mode': latest.get('mode', ''), 'seconds': round(total, 2),
            'regressions': regressions}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--strict', action='store_true',
                        help='exit 1 on a regression (default: advisory)')
    parser.add_argument('--window', type=int, default=DEFAULT_WINDOW)
    parser.add_argument('--update-baseline', action='store_true',
                        help='把当前窗口的中位数固化为评审基线')
    parser.add_argument('--reviewed-by', default='')
    parser.add_argument('--reason', default='')
    args = parser.parse_args(argv)

    if args.update_baseline:
        path = save_baseline(args.reviewed_by, args.reason, args.window)
        print(f'已固化性能基线：{os.path.relpath(path, _config.BOOK_ROOT)}')
        return 0

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
    sys.exit(_errors.run(main, sys.argv[1:]))
