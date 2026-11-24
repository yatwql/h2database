#!/usr/bin/env python3
"""One entry point that runs the delivery tiers (P0 / P1 / P2).

Modelled on investor-review's test-runner: the runner owns the orchestration,
the shell wrappers only forward, and every run leaves a report behind.

  python check_runner.py --mode docs        # documentation/ manuscript only
  python check_runner.py --mode code        # toolchain source only
  python check_runner.py --mode tests       # test sources only
  python check_runner.py --mode quick       # local edit: only what the diff can break
  python check_runner.py --mode p0          # commit gate  (ruff, fast gates, unit suite)
  python check_runner.py --mode p1          # merge gate   (every gate, unit suite)
  python check_runner.py --mode p2          # release gate (p1 + slow suite + deliver)
  python check_runner.py --mode p0 --json   # machine readable summary

Reports land in books/logs/, one pair per mode per day:
check-<mode>-<YYYYMMDD>.log is the day's journal (every run appended, each with a
header) and check-<mode>-<YYYYMMDD>.jsonl holds one summary line per run. A second
granularity per-run file turned a working day into a pile of fragments, and the run
someone wants to look at is never the newest one.

Exit codes: 0 pass, 1 a step failed, 2 usage/environment error.
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import _config, _errors, _fsutil, _log, status

PY = sys.executable
PY_ROOT = os.path.dirname(os.path.abspath(__file__))


def book_root() -> str:
    """Active book root, resolved per call (see make.book_root)."""
    return _config.current().root


def repo_root() -> str:
    return os.path.dirname(book_root())
def src_rel() -> str:
    return os.path.relpath(PY_ROOT, repo_root()).replace(os.sep, '/')
def test_rel() -> str:
    return os.path.relpath(os.path.join(book_root(), 'src', 'test'),
                           repo_root()).replace(os.sep, '/')
LOG = _log.get_logger('check')

# Fast tier: the structural gates that never depend on prose or artifacts.
FAST_GATES = ('architecture,script_contract,style_schema,llm_policy,'
              'versions,file_length,traces,portability')

MODES = {
    # Domain modes: a docs-only edit never pays for the code suite, a tests-only
    # edit never pays for the manuscript gates. The tier still decides what counts
    # as correct; these only decide what is worth running now.
    'docs': ('documentation edit', ('lint-changed', 'gates-changed')),
    'code': ('code edit', ('lint-changed', 'gates-changed', 'tests-changed')),
    'tests': ('test edit', ('lint-changed', 'tests-changed')),
    'quick': ('local edit', ('lint-changed', 'fast-gates', 'gates-changed',
                             'tests-changed')),
    'p0': ('commit gate', ('lint', 'fast-gates', 'tests')),
    'p1': ('merge gate', ('lint', 'fast-gates', 'gates', 'tests')),
    'p2': ('release gate', ('lint', 'fast-gates', 'gates', 'tests', 'slow', 'order',
                            'deliver')),
}
# Tests that spawn a runner process: correct at commit time, too slow to scope.
SPAWNING_TESTS = ('test_check_runner_flow',)

ALIASES = {'fast': 'p0', 'full': 'p1', 'release': 'p2', 'q': 'quick',
           'd': 'docs', 'c': 'code', 't': 'tests'}

# Which files belong to which domain. 'docs' also covers the manuscript, the
# config and the templates: they are prose and policy, not programs.
MODE_DOMAINS = {
    'docs': ('docs',),
    'code': ('code',),
    'tests': ('tests',),
}

# A changed path selects the gates and tests that can actually be wrong. The
# mapping is deliberately coarse: it narrows a run, it never narrows what counts
# as correct (p0/p1 always run everything). Path prefixes come from the config so
# a renamed directory cannot turn the mapping into a silent no-op.
def path_scopes() -> tuple[tuple[str, str, str], ...]:
    """(path fragment, domain, gates) for every book area a change can touch.

    One table with two readers: the classifier asks which domain a path is in,
    the scoped runner asks which gates that area can invalidate. Two tables would
    drift the moment a directory moves.
    """
    def rel(path: str) -> str:
        return os.path.relpath(path, repo_root()).replace(os.sep, '/') + '/'

    return (
        (rel(os.path.join(book_root(), 'src', 'test')), 'tests', ''),
        (rel(os.path.join(book_root(), 'src', 'python')), 'code',
         'architecture,script_contract'),
        (rel(_config.MANUSCRIPT_DIR), 'docs',
         'structure,captions,content_volume,audit_exercises,content_depth,style_rules'),
        (rel(_config.CONFIG_DIR), 'docs', 'style_schema,style_rules,content_volume'),
        (rel(os.path.join(book_root(), 'data')), 'docs', 'structure,versions'),
        (rel(os.path.join(book_root(), 'docs')), 'docs',
         'doc_drift,doc_archive,plan_coverage,traces,audit_links'),
        (rel(os.path.join(book_root(), 'data', 'baselines')), 'docs', 'content_volume'),
        (rel(os.path.join(repo_root(), '.github')), 'infra', ''),
        (rel(os.path.join(book_root(), 'scripts')), 'infra', ''),
    )


def domain_rows() -> tuple[tuple[str, str], ...]:
    """(path fragment, domain) for the change classifier."""
    return tuple((fragment, domain) for fragment, domain, _gates in path_scopes())


def domain_of(path: str) -> str:
    for fragment, domain in domain_rows():
        if path.startswith(fragment) or fragment.strip('/') in path:
            return domain
    if _inside_another_book(path):
        return 'other-book'
    return 'infra'


def _inside_another_book(path: str) -> bool:
    """Whether a path belongs to a neighbour book rather than to this one.

    Books sit side by side. A commit that touches only the other book says
    nothing about this book's toolchain, so it must not be classified as
    infrastructure — that classification is what pulls every gate into a run.
    """
    target = os.path.realpath(path if os.path.isabs(path)
                              else os.path.join(repo_root(), path))
    active = os.path.realpath(book_root())
    for root in _config.candidate_books(active):
        real = os.path.realpath(root)
        if real == active:
            continue
        if target == real or target.startswith(real + os.sep):
            return True
    return False


def scoped_changes(domains: tuple[str, ...] | None = None) -> list[str]:
    changed = changed_files()
    if domains is None:
        return changed
    return [path for path in changed if domain_of(path) in domains]


def gates_for_table() -> tuple[tuple[str, str], ...]:
    """(path fragment, gates) for the scoped runner, from the same table."""
    return tuple((fragment, gates) for fragment, _domain, gates in path_scopes() if gates)


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
        'book_root': book_root(),
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
        command = [PY, '-m', 'pytest', test_rel(), '-q']
        if marker:
            command += ['-m', marker]
        return command
    return [PY, os.path.join(PY_ROOT, 'make.py'), 'test']


def changed_files() -> list[str]:
    """Paths touched in the working tree, staged or not (repo-relative)."""
    try:
        diff = subprocess.run(['git', 'diff', '--name-only', 'HEAD'],
                              cwd=repo_root(), capture_output=True, text=True, check=False)
        untracked = subprocess.run(
            ['git', 'ls-files', '--others', '--exclude-standard'],
            cwd=repo_root(), capture_output=True, text=True, check=False)
    except OSError:
        return []
    paths = set()
    for block in (diff.stdout, untracked.stdout):
        paths.update(line.strip() for line in block.splitlines() if line.strip())
    return sorted(paths)


def gates_for_change(changed: list[str]) -> str:
    """The gates a set of changed paths can influence (comma separated)."""
    wanted: list[str] = []
    table = gates_for_table()
    for path in changed:
        for fragment, gates in table:
            if fragment in path:
                wanted += [gate for gate in gates.split(',') if gate not in wanted]
    return ','.join(wanted)


def tests_for_change(changed: list[str]) -> list[str]:
    """Test modules that exercise the touched source modules (empty = none).

    Modules that spawn the runner itself are excluded: they re-run whole tiers as
    subprocesses, which turns a scoped run into a full one. p0/p1 still run them.
    """
    test_dir = os.path.join(book_root(), 'src', 'test')
    try:
        available = {name[:-3] for name in os.listdir(test_dir)
                     if name.startswith('test_') and name.endswith('.py')}
    except OSError:
        return []
    picked: set[str] = set()
    for path in changed:
        if not path.endswith('.py'):
            continue
        if '/src/test/' in path:
            picked.add(os.path.basename(path)[:-3])
            continue
        if '/src/python/' not in path:
            continue
        rel = path.split('/src/python/', 1)[1][:-3]
        parts = rel.split('/')
        stem = parts[-1]
        prefixes = [f'test_{stem}', f'test_{parts[0]}_{stem}' if len(parts) > 1 else '']
        for name in available:
            if any(name == prefix or name.startswith(prefix + '_')
                   for prefix in prefixes if prefix):
                picked.add(name)
    return sorted(picked - set(SPAWNING_TESTS))


def _command(step: str, marker: str = '',
             domains: tuple[str, ...] | None = None) -> list[str] | None:
    """Shell command for one step (None means the step is skipped with a note)."""
    if step == 'lint':
        # The pinned ruff in books/.venv is the authority; a ruff from PATH may be
        # a different version with different rules (same reason the toolchain runs
        # on .venv only).
        if importlib.util.find_spec('ruff') is not None:
            return [PY, '-m', 'ruff', 'check', src_rel(), test_rel()]
        if shutil.which('ruff'):
            return ['ruff', 'check', src_rel(), test_rel()]
        if shutil.which('uvx'):
            return ['uvx', 'ruff', 'check', src_rel(), test_rel()]
        return None
    if step == 'lint-changed':
        files = [path for path in scoped_changes(domains) if path.endswith('.py')]
        if not files:
            return None
        if importlib.util.find_spec('ruff') is not None:
            return [PY, '-m', 'ruff', 'check', *files]
        return None
    if step == 'gates-changed':
        gates = gates_for_change(scoped_changes(domains))
        if not gates:
            return None
        return [PY, os.path.join(PY_ROOT, 'make.py'), 'check', '--only', gates]
    if step == 'tests-changed':
        modules = tests_for_change(scoped_changes(domains))
        if not modules:
            return None
        tests_dir = os.path.relpath(os.path.join(book_root(), 'src', 'test'), repo_root())
        # Same tier filter as p0: a scoped run must stay in the fast tier,
        # otherwise it can pull in the slow suites that spawned this selection.
        return [PY, '-m', 'pytest', '-q', '-m', 'tier_fast',
                *(os.path.join(tests_dir, f'{name}.py') for name in modules)]
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
        raise SystemExit(f'error: unknown mode {mode!r}; expected quick|p0|p1|p2')
    return key


def run_step(step: str, log_path: str, timeout: float = 1800.0,
             marker: str = '', domains: tuple[str, ...] | None = None) -> dict:
    """Run one step, tee its output into the report, and summarise the result."""
    command = _command(step, marker, domains)
    started = time.perf_counter()
    if command is None:
        return {'step': step, 'code': 0, 'seconds': 0.0, 'argv': [],
                'skipped': 'tool not available'}
    env = dict(os.environ)
    if step == 'slow':
        env['BOOK_SLOW'] = '1'
    try:
        proc = subprocess.run(command, cwd=repo_root(), capture_output=True, text=True,
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
    result = {'step': step, 'code': proc.returncode, 'seconds': elapsed,
              'argv': command}
    counts = pytest_counts(f'{proc.stdout or ""}{proc.stderr or ""}')
    if counts:
        result['counts'] = counts
    return result


def pytest_counts(output: str) -> dict:
    """Passed/failed/skipped the suite reported, so a run is readable as numbers.

    The summary says a step failed; how much of the suite ran is only in the log
    text. These counts make "the gate caught one failure out of 1100" visible from
    the record alone.
    """
    counts = {}
    for name in ('passed', 'failed', 'skipped', 'errors', 'deselected'):
        match = re.search(r'(\d+)\s+' + name + r'\b', output)
        if match:
            counts[name.rstrip('s')] = int(match.group(1))
    return counts


def git_state(root: str) -> dict:
    """The revision the gate judged, and whether the tree was dirty.

    A gate run answers "is this tree good"; without the revision the record cannot
    say which tree it meant, and a later reader has no way to reproduce it.
    """
    def run(*args: str) -> str:
        try:
            proc = subprocess.run(['git', *args], cwd=root, capture_output=True,
                                  text=True, encoding='utf-8', check=False, timeout=10)
        except (OSError, subprocess.SubprocessError):  # pragma: no cover - no git
            return ''
        return proc.stdout.strip() if proc.returncode == 0 else ''

    return {'commit': run('rev-parse', '--short', 'HEAD'),
            'dirty': bool(run('status', '--porcelain'))}


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


# A day is the unit a person looks back at, so the day is the file: the run log is
# appended to, and each run's summary is one line in the jsonl beside it. There is
# nothing to delete when a run passes — and nothing to lose when one fails: the
# failing run keeps its own section inside the same day's log.
def _prune_logs(logs: str, now: datetime.datetime) -> None:
    """Delete run reports and rollups older than the configured retention."""
    # one retention governs every log: the rotating file and these reports
    days = _log.retention_days()
    cutoff = (now - datetime.timedelta(days=days)).date()
    try:
        names = os.listdir(logs)
    except OSError:
        return  # no directory, nothing to prune
    for name in names:
        # `check-<mode>-<date>.<ext>`: ISO today, the compact form from older runs
        match = re.match(r'check-(?:[a-z0-9-]*?-)?(\d{4}-\d{2}-\d{2}|\d{8})(?:-|\.)', name)
        if match is None:
            continue
        token, fmt = match.group(1), ('%Y-%m-%d' if '-' in match.group(1) else '%Y%m%d')
        try:
            stamp = datetime.datetime.strptime(token, fmt).date()
        except ValueError:
            continue
        if stamp >= cutoff:
            continue
        try:
            os.remove(os.path.join(logs, name))
        except OSError as exc:  # pragma: no cover - already gone
            LOG.debug('could not prune %s: %s', name, exc)


def report_paths(mode: str, when: datetime.datetime) -> tuple[str, str]:
    """The day's journal for this mode: one log and one jsonl, appended per run.

    The date is ISO (`2026-11-24`), as in the archive and the snapshots: a filename a
    person can read, and a lexicographic order that is still chronological.
    """
    directory = os.path.join(book_root(), 'logs')
    _fsutil.ensure_dir(directory)
    base = os.path.join(directory, f'check-{mode}-{when:%Y-%m-%d}')
    return base + '.log', base + '.jsonl'


def _log_size(path: str) -> int:
    """Bytes already in the journal; 0 when it does not exist yet."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


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
    if key == 'quick':
        timeout = min(timeout, 300.0)
    steps = select_steps(all_steps, only, skip)
    now = datetime.datetime.now()
    log_path, jsonl_path = report_paths(key, now)
    log_offset = _log_size(log_path) if archive else 0
    if archive:
        _append_log(log_path, f'\n# ===== {now:%Y-%m-%d %H:%M:%S} mode={key} ({label}) '
                              f'{len(steps)} step(s) =====\n')
    print(f'=== check {key} ({label}): {len(steps)} step(s) ===')
    results = []
    started = time.perf_counter()
    active_marker = marker or MODE_MARKERS.get(key, '')
    domains = MODE_DOMAINS.get(key)
    for step in steps:
        result = run_step(step, log_path, timeout, active_marker, domains)
        results.append(result)
        if result['code'] != 0:
            break
    elapsed = round(time.perf_counter() - started, 2)
    failed = [r for r in results if r['code'] != 0]
    summary = {'mode': key, 'label': label, 'ok': not failed,
               'started_at': now.isoformat(timespec='seconds'),
               'seconds': elapsed, 'steps': results, 'marker': active_marker,
               'machine': machine_info(), 'git': git_state(repo_root()),
               'log': log_path if archive else '', 'json': jsonl_path if archive else ''}
    report = ''
    if failed:
        summary['failed_step'] = failed[0]['step']
    if archive:
        summary['log_offset'] = log_offset
        summary['log_len'] = max(0, _log_size(log_path) - log_offset)
        _record_perf(summary)
        _append_log(jsonl_path, json.dumps(summary, ensure_ascii=False) + '\n')
        _prune_logs(os.path.join(book_root(), 'logs'), now)
        report = log_path
    else:
        report = ''
    LOG.info('check %s -> %s (%.2fs, %d steps)',
             key, 'pass' if not failed else 'fail', elapsed, len(results))
    for line in status.render(not failed, f'check {key}（{label}）', elapsed,
                              results[-1]['code'] if results else 0).splitlines():
        LOG.info('  %s', line)
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        verdict = '✅ pass' if not failed else f"❌ fail at {failed[0]['step']}"
        print(f'{verdict}  ({elapsed}s)', end='')
        if archive and report:
            print(f'  → {os.path.relpath(report, repo_root())}')
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
    sys.exit(_errors.run(main, sys.argv[1:]))
