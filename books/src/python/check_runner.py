#!/usr/bin/env python3
"""One entry point that runs the delivery tiers (P0 / P1 / P2).

Modelled on investor-review's test-runner: the runner owns the orchestration,
the shell wrappers only forward, and every run leaves a report behind.

  python check_runner.py --mode p0          # commit gate  (ruff, fast gates, unit suite)
  python check_runner.py --mode p1          # merge gate   (every gate, unit suite)
  python check_runner.py --mode p2          # release gate (p1 + slow suite + deliver)
  python check_runner.py --mode p0 --json   # machine readable summary

Reports land in books/logs/check-<mode>-<timestamp>.log (full output) and .json
(the summary printed to stdout), so a failed tier can be inspected later without
re-running it.

Exit codes: 0 pass, 1 a step failed, 2 usage/environment error.
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import _config, _fsutil, _log

PY = sys.executable
PY_ROOT = os.path.dirname(os.path.abspath(__file__))
BOOK_ROOT = _config.BOOK_ROOT
REPO_ROOT = os.path.dirname(BOOK_ROOT)
SRC_REL = os.path.relpath(PY_ROOT, REPO_ROOT).replace(os.sep, '/')
TEST_REL = os.path.relpath(os.path.join(BOOK_ROOT, 'src', 'test'), REPO_ROOT).replace(os.sep, '/')
LOG = _log.get_logger('check')

# Fast tier: the structural gates that never depend on prose or artifacts.
FAST_GATES = ('architecture,script_contract,style_schema,llm_policy,'
              'versions,file_length,traces,portability')

MODES = {
    'p0': ('commit gate', ('lint', 'fast-gates', 'tests')),
    'p1': ('merge gate', ('lint', 'fast-gates', 'gates', 'tests')),
    'p2': ('release gate', ('lint', 'fast-gates', 'gates', 'tests', 'slow', 'order',
                            'deliver')),
}
ALIASES = {'fast': 'p0', 'full': 'p1', 'release': 'p2'}

# Marker expression per tier, the same idea as investor-review's runner modes:
# the tier decides *which* tests run, not which assertions count.
MODE_MARKERS = {
    'p0': 'tier_fast',
    'p1': 'not tier_slow',
    'p2': '',
}


def machine_info() -> dict:
    """What the run happened on — the first thing to check when a tier differs."""
    return {
        'python': platform.python_version(),
        'platform': platform.platform(),
        'cpus': os.cpu_count(),
        'locale': os.environ.get('LC_ALL') or os.environ.get('LANG') or '',
        'book_root': BOOK_ROOT,
    }


def select_steps(steps: tuple[str, ...], only: str = '', skip: str = '') -> tuple[str, ...]:
    """Restrict a tier's steps (`--only a,b` / `--skip c`); order is preserved."""
    wanted = [name.strip() for name in only.split(',') if name.strip()]
    dropped = {name.strip() for name in skip.split(',') if name.strip()}
    chosen = tuple(step for step in steps if (not wanted or step in wanted)
                   and step not in dropped)
    unknown = ({*wanted} | dropped) - set(steps)
    if unknown:
        raise SystemExit(f'error: unknown step(s) for this tier: {sorted(unknown)}')
    return chosen


def tests_command(marker: str = '') -> list[str]:
    """Pytest command for a marker expression; unittest when pytest is absent."""
    if importlib.util.find_spec('pytest') is not None:
        command = [PY, '-m', 'pytest', TEST_REL, '-q']
        if marker:
            command += ['-m', marker]
        return command
    return [PY, os.path.join(PY_ROOT, 'make.py'), 'test']


def _command(step: str, marker: str = '') -> list[str] | None:
    """Shell command for one step (None means the step is skipped with a note)."""
    if step == 'lint':
        if shutil.which('ruff'):
            return ['ruff', 'check', SRC_REL, TEST_REL]
        if shutil.which('uvx'):
            return ['uvx', 'ruff', 'check', SRC_REL, TEST_REL]
        return None
    if step == 'fast-gates':
        return [PY, os.path.join(PY_ROOT, 'make.py'), 'check', '--only', FAST_GATES]
    if step == 'gates':
        return [PY, os.path.join(PY_ROOT, 'make.py'), 'check', '--keep-going']
    if step == 'tests':
        return tests_command(marker)
    if step == 'slow':
        return [PY, os.path.join(PY_ROOT, 'make.py'), 'test', '--full']
    if step == 'order':
        # test-order dependence: the suite runs twice, normal and reversed
        return [PY, os.path.join(PY_ROOT, 'audit', 'order_dependence.py')]
    if step == 'deliver':
        return [PY, os.path.join(PY_ROOT, 'make.py'), 'deliver']
    raise KeyError(step)


def resolve_mode(mode: str) -> str:
    """Accept p0/p1/p2 and their historical names (fast/full/release)."""
    key = ALIASES.get(mode, mode).lower()
    if key not in MODES:
        raise SystemExit(f'error: unknown mode {mode!r}; expected p0|p1|p2')
    return key


def run_step(step: str, log_path: str, timeout: float = 1800.0,
             marker: str = '') -> dict:
    """Run one step, tee its output into the report, and summarise the result."""
    command = _command(step, marker)
    started = time.perf_counter()
    if command is None:
        return {'step': step, 'code': 0, 'seconds': 0.0, 'skipped': 'tool not available'}
    env = dict(os.environ)
    if step == 'slow':
        env['BOOK_SLOW'] = '1'
    try:
        proc = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', env=env,
                              timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        elapsed = round(time.perf_counter() - started, 2)
        _append_log(log_path, f'\n=== {step}: timed out after {timeout}s ===\n')
        print(f'  FAIL {step} (timeout after {timeout}s)')
        return {'step': step, 'code': 124, 'seconds': elapsed, 'timeout': timeout}
    elapsed = round(time.perf_counter() - started, 2)
    _append_log(log_path,
                f'\n=== {step}: {" ".join(command)} '
                f'(rc={proc.returncode}, {elapsed}s) ===\n'
                f'{proc.stdout or ""}{proc.stderr or ""}')
    if proc.returncode != 0:
        tail = (proc.stdout or proc.stderr or '').strip().splitlines()[-5:]
        print(f'  FAIL {step} (rc={proc.returncode}, {elapsed}s)')
        for line in tail:
            print(f'    {line}')
    else:
        print(f'  ok   {step} ({elapsed}s)')
    return {'step': step, 'code': proc.returncode, 'seconds': elapsed}


def _record_perf(summary: dict) -> None:
    """Feed the timing history so delivery-speed regressions are visible."""
    try:
        perf = importlib.import_module('audit.perf_baseline')
    except ImportError:  # pragma: no cover - audit layer always present here
        return
    perf.record({'ts': datetime.datetime.now().isoformat(timespec='seconds'),
                 'mode': summary.get('mode', ''),
                 'seconds': summary.get('seconds', 0.0),
                 'steps': summary.get('steps', [])})


def report_paths(mode: str, stamp: str) -> tuple[str, str]:
    directory = os.path.join(BOOK_ROOT, 'logs')
    _fsutil.ensure_dir(directory)
    base = os.path.join(directory, f'check-{mode}-{stamp}')
    return base + '.log', base + '.json'


def _append_log(path: str, text: str) -> None:
    """Append to the run log; a missing directory is recreated, not fatal.

    The report is diagnostic: if it cannot be written the tier result still
    stands, so this never raises.
    """
    try:
        _fsutil.ensure_dir(path)
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write(text)
    except OSError as exc:  # pragma: no cover - disk full / permissions
        print(f'  [warn] cannot write the run log {path}: {exc}', file=sys.stderr)


def run(mode: str, *, archive: bool = True, as_json: bool = False,
        only: str = '', skip: str = '', timeout: float = 1800.0,
        marker: str = '') -> dict:
    """Run the steps of ``mode`` and return the summary (machine info included)."""
    key = resolve_mode(mode)
    label, all_steps = MODES[key]
    steps = select_steps(all_steps, only, skip)
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S')
    log_path, json_path = report_paths(key, stamp)
    if archive:
        _fsutil.write_text(log_path, f'# check mode={key} ({label}) {stamp}\n')
    print(f'=== check {key} ({label}): {len(steps)} step(s) ===')
    results = []
    started = time.perf_counter()
    active_marker = marker or MODE_MARKERS.get(key, '')
    for step in steps:
        result = run_step(step, log_path, timeout, active_marker)
        results.append(result)
        if result['code'] != 0:
            break
    elapsed = round(time.perf_counter() - started, 2)
    failed = [r for r in results if r['code'] != 0]
    summary = {'mode': key, 'label': label, 'ok': not failed,
               'seconds': elapsed, 'steps': results, 'marker': active_marker,
               'machine': machine_info(),
               'log': log_path if archive else '', 'json': json_path if archive else ''}
    if failed:
        summary['failed_step'] = failed[0]['step']
    if archive:
        payload = json.dumps(summary, ensure_ascii=False, indent=2) + '\n'
        _record_perf(summary)
        _fsutil.write_text(json_path, payload)
        _fsutil.write_text(os.path.join(BOOK_ROOT, 'logs', 'check-latest.json'), payload)
    LOG.info('check %s -> %s (%.2fs, %d steps)',
             key, 'pass' if not failed else 'fail', elapsed, len(results))
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        verdict = '✅ pass' if not failed else f"❌ fail at {failed[0]['step']}"
        print(f'{verdict}  ({elapsed}s)', end='')
        if archive:
            print(f'  → {os.path.relpath(json_path, REPO_ROOT)}')
        else:
            print()
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--mode', default='p0',
                        help='p0 (commit) | p1 (merge) | p2 (release); aliases fast/full/release')
    parser.add_argument('--json', action='store_true', help='machine-readable summary')
    parser.add_argument('--no-archive', action='store_true', help='do not write a report')
    parser.add_argument('--only', default='', help='comma-separated steps to run')
    parser.add_argument('--skip', default='', help='comma-separated steps to skip')
    parser.add_argument('--timeout', type=float, default=1800.0,
                        help='per-step timeout in seconds (default 1800)')
    parser.add_argument('--marker', default='',
                        help='pytest marker expression overriding the tier default')
    args = parser.parse_args(argv)
    summary = run(args.mode, archive=not args.no_archive, as_json=args.json,
                  only=args.only, skip=args.skip, timeout=args.timeout,
                  marker=args.marker)
    return 0 if summary['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
