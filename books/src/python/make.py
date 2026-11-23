#!/usr/bin/env python3
"""Single entry point for the book toolchain.

Replaces the "remember the order of 20 scripts" workflow:

  python make.py check      # quality gates only (no artifacts written)
  python make.py build      # cover stats + merged markdown + HTML
  python make.py verify     # every audit against the current manuscript
  python make.py test       # unit tests (books/tests)
  python make.py deliver    # build + PDF + EPUB (needs playwright/pandoc)
  python make.py doctor     # report optional tool availability

Options:
  --only NAME[,NAME]   run only the named steps
  --skip NAME[,NAME]   skip the named steps
  --timings            print per-step wall time
  --keep-going         run all steps, report failures at the end
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import _config, _errors, _fsutil, _log

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
COVERAGE_BASELINE_REL = os.path.join('data', 'baselines', 'coverage.json')


def book_root() -> str:
    """The active book's root, resolved when asked.

    Not a module constant: an installed toolchain has no checkout to derive a book
    from, and --book is parsed after import.
    """
    return _config.current().root
PY = sys.executable
LOG = _log.get_logger('make')


def venv_python() -> str | None:
    """Path to the project interpreter (books/.venv), None when absent."""
    for rel in (('.venv', 'bin', 'python'), ('.venv', 'Scripts', 'python.exe')):
        candidate = os.path.normpath(os.path.join(book_root(), *rel))
        if os.path.exists(candidate):
            return candidate
    return None


def interpreter_problem(expected: str | None, executable: str) -> str | None:
    """Why `executable` may not run the toolchain, or None when it may.

    Pure: the caller supplies both paths, so the rule is testable without
    patching module globals that other suites import.
    """
    if expected is None or os.environ.get('BOOK_ALLOW_SYSTEM_PYTHON') == '1':
        return None
    if os.path.realpath(executable) == os.path.realpath(expected):
        return None
    return f'interpreter {executable} is not the project virtualenv ({expected})'


def enforce_venv(expected: str | None = None, executable: str | None = None) -> None:
    """Refuse to run the toolchain outside books/.venv.

    The pins in requirements.txt decide which browser build, pypdf behaviour and
    lint rules apply. Running under a system interpreter silently swaps all three
    (a browser revision mismatch surfaces only at render time), so the entry
    point checks before it does any work.
    """
    expected = venv_python() if expected is None else expected
    executable = sys.executable if executable is None else executable
    if interpreter_problem(expected, executable) is None:
        return
    print('error: the book toolchain runs on the project virtualenv only', file=sys.stderr)
    print(f'       expected: {expected}', file=sys.stderr)
    print(f'       current : {executable}', file=sys.stderr)
    print(f'       run     : {expected} {os.path.join(TOOLS_DIR, "make.py")} ...',
          file=sys.stderr)
    print('       override: BOOK_ALLOW_SYSTEM_PYTHON=1 (not for delivery)', file=sys.stderr)
    raise SystemExit(3)


def pinned_versions() -> dict[str, str]:
    """name -> version from requirements.txt (the dependency single source)."""
    pins: dict[str, str] = {}
    path = os.path.join(book_root(), 'requirements.txt')
    try:
        with open(path, encoding='utf-8') as handle:
            lines = handle.read().splitlines()
    except OSError:
        return pins
    for line in lines:
        line = line.split('#', 1)[0].strip()
        if '==' in line:
            name, version = line.split('==', 1)
            pins[name.strip().lower().replace('_', '-')] = version.strip()
    return pins


def pin_drift() -> list[str]:
    """Installed distributions that disagree with requirements.txt."""
    from importlib import metadata

    drift: list[str] = []
    for name, want in pinned_versions().items():
        try:
            have = metadata.version(name)
        except metadata.PackageNotFoundError:
            drift.append(f'{name} missing (want {want})')
            continue
        if have != want:
            drift.append(f'{name} {have} (want {want})')
    return drift

# (name, script or None for builtin, extra args, group)
Step = tuple[str, str | None, tuple[str, ...], str]

# A step that hangs must fail fast enough for the operator to keep reading the
# report: gates are seconds, the suite is tens of seconds, so a bound with a
# wide margin still trips long before anyone gives up waiting. Both values are
# overridable in base.json [toolchain].
STEP_TIMEOUT_S = 900
TEST_TIMEOUT_S = 300
SLOW_STEPS = frozenset({'unittest', 'coverage'})


def step_timeout(name: str) -> float:
    """Wall-clock bound for one step, in seconds (config first, default second)."""
    toolchain = _config.POLICY.get('toolchain') or {}
    key = 'test_timeout_s' if name in SLOW_STEPS else 'step_timeout_s'
    fallback = TEST_TIMEOUT_S if name in SLOW_STEPS else STEP_TIMEOUT_S
    try:
        return float(toolchain.get(key) or fallback)
    except (TypeError, ValueError):
        return float(fallback)


def _step_process(cmd: list[str], limit: float) -> subprocess.CompletedProcess:
    """Run one step in its own process group; raise TimeoutExpired when over.

    The group matters: a timed-out pytest leaves chromium and pandoc behind, and
    an orphan keeps burning CPU while the next run is judged slow for a reason
    nobody can see. Killing the group takes the grandchildren with it.
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, cwd=book_root(), start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except OSError:
            proc.kill()
        proc.communicate()
        raise
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)

STEPS: list[Step] = [
    # ---- build ----
    ('cover_stats', 'manuscript/cover.py', (), 'build'),
    ('rebuild_merged', 'render/merge.py', (), 'build'),
    ('to_html', 'render/to_html.py', (), 'build'),
    ('archive', 'manuscript/archive.py', ('--kind', 'all'), 'build'),
    # ---- verify ----
    ('architecture', 'audit/check_architecture.py', (), 'verify'),
    ('llm_policy', 'audit/llm_policy.py', (), 'verify'),
    ('gate_trace', 'audit/gate_trace.py', (), 'verify'),
    ('requirement_trace', 'audit/requirement_trace.py', (), 'verify'),
    ('versions', 'audit/version_consistency.py', (), 'verify'),
    ('typecheck', 'audit/typecheck.py', (), 'verify'),
    ('portability', 'audit/portability.py', (), 'verify'),
    ('test_redundancy', 'audit/test_redundancy.py', (), 'verify'),
    ('perf_baseline', 'audit/perf_baseline.py', (), 'verify'),
    ('style_schema', 'audit/style_schema.py', (), 'verify'),
    ('file_length', 'audit/file_length.py', (), 'verify'),
    ('script_contract', 'audit/script_contract.py', (), 'verify'),
    ('traces', 'audit/traces.py', (), 'verify'),
    ('doc_drift', 'audit/doc_drift.py', (), 'verify'),
    ('doc_archive', 'audit/doc_archive.py', (), 'verify'),
    ('plan_coverage', 'audit/plan_coverage.py', (), 'verify'),
    ('audit_links', 'audit/links.py', (), 'verify'),
    ('audit_ascii', 'audit/diagrams.py', (), 'verify'),
    ('audit_smart', 'audit/smart.py', (), 'verify'),
    ('captions', 'audit/captions.py', (), 'verify'),
    ('audit_figures', 'audit/figures.py', (), 'verify'),
    ('crossrefs', 'audit/crossrefs.py', (), 'verify'),
    ('audit_exercises', 'audit/exercises.py', (), 'verify'),
    ('figure_clusters', 'audit/figure_clusters.py', (), 'verify'),
    ('audit_index_xrefs', 'audit/index_xrefs.py', (), 'verify'),
    ('balance_check', 'audit/balance.py', (), 'verify'),
    ('source_refs', 'audit/source_refs.py', (), 'verify'),
    ('readability', 'audit/readability.py', (), 'verify'),
    ('style', 'audit/style.py', (), 'verify'),
    ('style_rules', 'audit/style_rules.py', (), 'verify'),
    ('content_depth', 'audit/content_depth.py', (), 'verify'),
    ('structure', 'audit/structure.py', (), 'verify'),
    ('content_volume', 'audit/content_volume.py', (), 'verify'),
    # ---- deliver ----
    ('to_pdf', 'render/to_pdf.py', (), 'deliver'),
    ('pdf_toc_links', 'render/pdf_toc_links.py', (), 'deliver'),
    ('verify_pdf', 'render/verify_pdf.py', ('--require-toc-links',), 'deliver'),
    ('to_epub', 'render/to_epub.py', (), 'deliver'),
    ('verify_epub', 'render/verify_epub.py', (), 'deliver'),
    ('archive_release', 'manuscript/archive.py', ('--kind', 'all'), 'deliver'),
]

GROUPS = {
    'build': ('cover_stats', 'rebuild_merged', 'to_html', 'archive'),
    'verify': tuple(n for n, _s, _a, g in STEPS if g == 'verify'),
    'deliver': ('to_pdf', 'pdf_toc_links', 'verify_pdf', 'to_epub', 'verify_epub',
                'archive_release'),
}
GROUPS['check'] = GROUPS['verify']
GROUPS['test'] = ('unittest',)
GROUPS['cover'] = ('coverage',)
GROUPS['report'] = ('scorecard',)

OPTIONAL_TOOLS = {
    'pandoc': 'render/to_epub.py',
    'playwright': 'render/to_pdf.py',
    'pypdf': 'to_pdf.py, pdf_toc_links.py, verify_pdf.py',
    'defusedxml': 'verify_epub.py (optional XML hardening)',
}


def _select(args: argparse.Namespace) -> list[Step]:
    if args.only:
        wanted = {n.strip() for n in args.only.split(',') if n.strip()}
    else:
        wanted = set(GROUPS[args.command])
    skip = {n.strip() for n in (args.skip or '').split(',') if n.strip()}
    if args.command == 'test':
        return [('unittest', None, (), 'test')]
    steps = [s for s in STEPS if s[0] in wanted and s[0] not in skip]
    unknown = wanted - {s[0] for s in STEPS}
    if unknown:
        raise SystemExit(f'error: unknown step(s): {sorted(unknown)}')
    return steps


def run_step(step: Step) -> tuple[str, int, float]:
    """Execute one step; return (name, returncode, seconds)."""
    name, script, extra, _group = step
    started = time.perf_counter()
    if script is None:
        tests_dir = os.path.normpath(os.path.join(TOOLS_DIR, '..', 'test'))
        # pytest finishes; `unittest discover` deadlocks on the threaded fixtures,
        # which is how the slow tier burned 1800s in CI before failing.
        if importlib.util.find_spec('pytest'):
            marker = [] if os.environ.get('BOOK_SLOW') == '1' else ['-m', 'tier_fast']
            # --durations keeps the costliest tests in the report: the operator
            # sees which one is slow instead of waiting for a wall clock to tell.
            cmd = [PY, '-m', 'pytest', '-q', '--durations=10', *marker, tests_dir]
        else:
            cmd = [PY, '-m', 'unittest', 'discover', '-s', tests_dir, '-t', tests_dir]
    else:
        cmd = [PY, os.path.join(TOOLS_DIR, script), *extra]
    LOG.debug('run step %s: %s', name, ' '.join(cmd))
    # A gate that deadlocks must fail the run, not hang it: without a bound the
    # whole command waits forever and no step ever reports.
    limit = step_timeout(name)
    try:
        proc = _step_process(cmd, limit)
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - started
        LOG.warning('step %s timed out after %ss', name, limit)
        print(f'  FAIL {name} (timeout after {limit:g}s)')
        return name, 124, elapsed
    elapsed = time.perf_counter() - started
    if proc.returncode != 0:
        LOG.warning('step %s failed rc=%s (%.2fs)', name, proc.returncode, elapsed)
        # unittest writes its failure blocks to stderr: keep both streams
        combined = ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()
        for line in combined.splitlines()[-30:]:
            print(f'    {line}')
        print(f'  FAIL {name} (rc={proc.returncode})')
    return name, proc.returncode, elapsed


def doctor() -> int:
    print('=== toolchain doctor ===')
    print(f'  python      : {sys.version.split()[0]}')
    problems = 0
    expected = venv_python()
    on_venv = expected is not None and \
        os.path.realpath(sys.executable) == os.path.realpath(expected)
    print(f'  interpreter : {sys.executable}')
    if on_venv:
        print('  venv        : ok')
    else:
        # Advisory only: `doctor` reports the environment, `enforce_venv` is what
        # refuses to run. A diagnostic must not fail the fixture books in tests.
        print(f'  venv        : DRIFT (expected the project virtualenv: {expected}'
              ' — run scripts/bootstrap.sh)')
    drift = pin_drift()
    print(f'  pins        : {"ok" if not drift else "; ".join(drift)}')
    for module, users in OPTIONAL_TOOLS.items():
        found = importlib.util.find_spec(module) is not None
        if module == 'pandoc':
            found = shutil.which('pandoc') is not None
        status = 'ok' if found else 'MISSING'
        if not found:
            problems += 1
        print(f'  {module:<11} : {status:<7} (needed by {users})')
    print(f'  manuscript  : {_config.MANUSCRIPT_DIR}')
    print(f'  artifacts   : {_config.DIST_DIR}')
    missing = _config.missing_files()
    if missing:
        problems += 1
        print(f'  chapter gap : {", ".join(missing)}')
    return 0 if problems == 0 else 1


def report(extra: list[str] | None = None) -> int:
    """Six-dimension release scorecard; `report health` shows the debt readings."""
    extra = extra or []
    script = 'test_health.py' if extra[:1] == ['health'] else 'scorecard.py'
    if script == 'test_health.py':
        extra = extra[1:]
    proc = subprocess.run([PY, os.path.join(TOOLS_DIR, 'audit', script), *extra],
                          cwd=os.path.dirname(book_root()), check=False)
    return proc.returncode


def coverage(*, full: bool = False, update_baseline: bool = False) -> int:
    """Run the test suite under coverage and enforce the ratchet.

    The default measures the **fast** tier: that is the per-commit gate and the
    number the ratchet compares. ``full`` (``make cover --full``, or
    ``BOOK_SLOW=1``) also runs the slow tier, so the paths that need chromium or
    pandoc are measured for real instead of being reported as nobody's.
    """
    if importlib.util.find_spec('coverage') is None:
        print('coverage is not installed: pip install coverage')
        return 2
    threshold = _config.THRESHOLDS.get('coverage_fail_under', 0)
    slow = full or os.environ.get('BOOK_SLOW') == '1'
    marker = [] if slow else ['-m', 'tier_fast']
    tests = os.path.normpath(os.path.join(TOOLS_DIR, '..', 'test'))
    # pytest runs the same suite the gates run (it finishes); unittest discover
    # under coverage deadlocks on the threaded fixtures, which is how this gate
    # sat silent instead of reporting a number.
    inner = (['-m', 'pytest', '-q', *marker, tests]
             if importlib.util.find_spec('pytest') else
             ['-m', 'unittest', 'discover', '-s', tests, '-t', tests])
    try:
        run = subprocess.run(
            # --branch: a line can run while its false path never does; the
            # ratchet is only meaningful when both are counted.
            [PY, '-m', 'coverage', 'run', '--branch', '--source=books/src/python', *inner],
            cwd=os.path.dirname(book_root()), capture_output=True, text=True,
            check=False, timeout=1800)
    except subprocess.TimeoutExpired:
        print('coverage run timed out after 1800s')
        return 2
    if run.returncode != 0:
        print(run.stdout[-2000:])
        print(run.stderr[-1000:])
        return run.returncode
    report = subprocess.run(
        [PY, '-m', 'coverage', 'report', '--skip-covered',
         f'--fail-under={threshold}'],
        cwd=os.path.dirname(book_root()), capture_output=True, text=True, check=False)
    print(report.stdout)
    print(report.stderr.strip())
    print(f'coverage gate: {"fast + slow" if slow else "fast"} tier, '
          f'threshold {threshold}% -> '
          f'{"PASS" if report.returncode == 0 else "FAIL"}')
    thin = thin_files(_config.THRESHOLDS.get('coverage_min_per_file', 60))
    if thin:
        for path, percent in thin:
            print(f'  FAIL {path} ({percent}% < per-file floor)')
        return 1
    drops, baseline = coverage_ratchet(update=update_baseline)
    if update_baseline:
        print(f'coverage baseline written: {baseline}')
    for path, before, now in drops:
        print(f'  FAIL {path} ({now}% < baseline {before}%)')
    if drops:
        print('  per-file coverage dropped: restore the paths, or re-record with '
              '`make.py cover --update-baseline` after review')
        return 1
    return report.returncode


def thin_files(floor: float) -> list[tuple[str, int]]:
    """Files below the per-file floor: a new module cannot be born untested.

    The whole-repo threshold can hide a 0%-covered file behind a large, well
    covered neighbour; this floor is what catches a module added without tests.
    """
    try:
        raw = subprocess.run([PY, '-m', 'coverage', 'json', '-o', '-'],
                             cwd=os.path.dirname(book_root()), capture_output=True,
                             text=True, check=False)
        payload = json.loads(raw.stdout or '{}')
    except (OSError, ValueError):
        return []
    out: list[tuple[str, int]] = []
    for path, data in (payload.get('files') or {}).items():
        summary = data.get('summary') or {}
        statements = int(summary.get('num_statements') or 0)
        if statements < 5:
            continue
        percent = int(summary.get('percent_covered') or 0)
        if percent < float(floor):
            out.append((path, percent))
    return sorted(out, key=lambda item: item[1])


def _coverage_json() -> dict:
    """The coverage data of the last run, as the same JSON the gates read."""
    raw = subprocess.run([PY, '-m', 'coverage', 'json', '-o', '-'],
                         cwd=os.path.dirname(book_root()), capture_output=True,
                         text=True, check=False)
    try:
        return json.loads(raw.stdout or '{}')
    except ValueError:
        return {}


def _percentages(payload: dict) -> dict[str, float]:
    """Per-file branch coverage, rounded the way the report prints it."""
    out: dict[str, float] = {}
    for path, data in (payload.get('files') or {}).items():
        summary = data.get('summary') or {}
        if int(summary.get('num_statements') or 0) < 5:
            continue
        out[path] = round(float(summary.get('percent_covered') or 0.0), 1)
    return out


def coverage_ratchet(*, update: bool = False) -> tuple[list[tuple[str, float, float]], str]:
    """Per-file coverage may not drop, whatever the global total says.

    A single global threshold lets a 200-statement module sit at 73% forever: the
    gap it leaves is invisible next to a well-covered neighbour. Recording every
    file's number makes each one ratchet on its own. Files below five statements
    are left out (a two-line module swings the percentage by tens of points).
    """
    path = os.path.join(book_root(), COVERAGE_BASELINE_REL)
    current = _percentages(_coverage_json())
    if update:
        _fsutil.ensure_dir(path)
        _fsutil.dump_json(path, {
            'note': 'Per-file branch coverage of the fast tier. Only review raises '
                    'these numbers; a drop fails `make.py cover`.',
            'files': dict(sorted(current.items())),
        })
        return [], path
    if not os.path.exists(path):
        return [], path
    try:
        recorded = (_fsutil.load_json(path) or {}).get('files') or {}
    except (OSError, ValueError):
        return [], path
    drops = [(name, float(before), current[name]) for name, before in sorted(recorded.items())
             if name in current and current[name] < float(before)]
    return drops, path


def _missing_book_toml() -> str:
    """The selected book root when it holds no ``data/book/book.toml``.

    An explicit book has to fail before a single step runs: the steps are child
    processes, and each would otherwise report the same missing file as its own
    traceback. One message and status 2 is the contract every entry follows.
    """
    if not os.environ.get('BOOK_ROOT'):
        return ''
    root = os.path.abspath(os.environ['BOOK_ROOT'])
    expected = os.path.join(root, 'data', 'book', 'book.toml')
    return '' if os.path.isfile(expected) else root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command',
                        choices=['check', 'build', 'verify', 'test', 'cover',
                                 'report', 'deliver', 'doctor'])
    parser.add_argument('--only', help='comma-separated step names')
    parser.add_argument('--skip', help='comma-separated step names to skip')
    parser.add_argument('--timings', action='store_true', help='print per-step wall time')
    parser.add_argument('--keep-going', action='store_true',
                        help='run every step even after a failure')
    parser.add_argument('--full', action='store_true',
                        help='also run the slow suite (chromium/pandoc)')
    parser.add_argument('--update-baseline', action='store_true',
                        help='re-record the per-file coverage baseline (review first)')
    parser.add_argument('--book', default='',
                        help='book root for every step (default: BOOK_ROOT, then the '
                             'nearest ancestor holding data/book/book.toml)')
    parser.add_argument('--edition', default='', help='manuscript edition for every step')

    report_extras: list[str] = []
    if argv and len(argv) > 0 and argv[0] == 'report':
        args, report_extras = parser.parse_known_args(argv)
    else:
        args = parser.parse_args(argv)

    if args.book or args.edition:
        # the steps are separate processes; they read the selection from the env
        if args.book:
            os.environ['BOOK_ROOT'] = os.path.abspath(args.book)
        if args.edition:
            os.environ['BOOK_EDITION'] = args.edition
    if args.command == 'doctor':
        return doctor()
    missing = _missing_book_toml()
    if missing:
        print(f'error: 没找到 book.toml，试过 {missing}', file=sys.stderr)
        return 2
    if args.book:
        # this module bound a book at import; an explicit --book rebinds it so the
        # parent reads the same book its child steps do
        _config.reset(_config.Config(os.environ['BOOK_ROOT']))

    if args.command == 'cover':
        return coverage(full=args.full, update_baseline=args.update_baseline)

    if args.command == 'report':
        return report(report_extras)

    if args.full:
        os.environ['BOOK_SLOW'] = '1'
    steps = _select(args)
    if not steps:
        print('nothing to do')
        return 0

    failures: list[str] = []
    total = 0.0
    LOG.info('make %s start (%d step(s))', args.command, len(steps))
    print(f'=== make {args.command}: {len(steps)} step(s) ===')
    for step in steps:
        name, code, elapsed = run_step(step)
        total += elapsed
        if code != 0:
            failures.append(name)
            if not args.keep_going:
                break
        else:
            LOG.info('step %s ok (%.2fs)', name, elapsed)
            if args.timings:
                print(f'  ok   {name} ({elapsed:.2f}s)')

    if args.timings:
        print(f'  total {total:.2f}s')
    if failures:
        LOG.error('make %s failed: %s', args.command, ', '.join(failures))
        print(f'FAILED: {", ".join(failures)}')
        return 1
    LOG.info('make %s done in %.2fs', args.command, total)
    print('OK')
    return 0


if __name__ == '__main__':
    enforce_venv()
    sys.exit(_errors.run(main, sys.argv[1:]))
