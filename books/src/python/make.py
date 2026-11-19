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
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import _config

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_ROOT = _config.BOOK_ROOT
PY = sys.executable

# (name, script or None for builtin, extra args, group)
Step = tuple[str, str | None, tuple[str, ...], str]

STEPS: list[Step] = [
    # ---- build ----
    ('cover_stats', 'manuscript/cover_stats.py', (), 'build'),
    ('rebuild_merged', 'render/rebuild_merged.py', (), 'build'),
    ('generate_html', 'render/generate_html.py', (), 'build'),
    # ---- verify ----
    ('doc_traces', 'audit/check_doc_traces.py', (), 'verify'),
    ('code_traces', 'audit/check_code_traces.py', (), 'verify'),
    ('doc_drift', 'audit/check_doc_drift.py', (), 'verify'),
    ('audit_links', 'audit/_audit_links.py', (), 'verify'),
    ('audit_ascii', 'audit/_audit_ascii.py', (), 'verify'),
    ('audit_smart', 'audit/_audit_smart.py', (), 'verify'),
    ('audit_captions', 'audit/_audit_captions.py', (), 'verify'),
    ('audit_figures', 'audit/_audit_figures.py', (), 'verify'),
    ('audit_crossrefs', 'audit/_audit_crossrefs.py', (), 'verify'),
    ('audit_exercises', 'audit/_audit_exercises.py', (), 'verify'),
    ('audit_figure_clusters', 'audit/_audit_figure_clusters.py', (), 'verify'),
    ('audit_index_xrefs', 'audit/_audit_index_xrefs.py', (), 'verify'),
    ('balance_check', 'audit/balance_check.py', (), 'verify'),
    ('source_freshness', 'sources/source_freshness_check.py', (), 'verify'),
    ('readability', 'audit/readability_check.py', (), 'verify'),
    ('style', 'audit/check_style.py', (), 'verify'),
    ('final_check', 'audit/final_check.py', (), 'verify'),
    # ---- deliver ----
    ('generate_pdf', 'render/generate_pdf.py', (), 'deliver'),
    ('verify_pdf', 'render/verify_pdf.py', ('--require-toc-links',), 'deliver'),
    ('generate_epub', 'render/generate_epub.py', (), 'deliver'),
    ('verify_epub', 'render/verify_epub.py', (), 'deliver'),
]

GROUPS = {
    'build': ('cover_stats', 'rebuild_merged', 'generate_html'),
    'verify': tuple(n for n, _s, _a, g in STEPS if g == 'verify'),
    'deliver': ('generate_pdf', 'verify_pdf', 'generate_epub', 'verify_epub'),
}
GROUPS['check'] = GROUPS['verify']
GROUPS['test'] = ('unittest',)
GROUPS['cover'] = ('coverage',)

OPTIONAL_TOOLS = {
    'pandoc': 'render/generate_epub.py',
    'playwright': 'render/generate_pdf.py',
    'pypdf': 'generate_pdf.py, add_pdf_toc_links.py, verify_pdf.py',
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
        cmd = [PY, '-m', 'unittest', 'discover', '-s', tests_dir, '-t', tests_dir]
    else:
        cmd = [PY, os.path.join(TOOLS_DIR, script), *extra]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=BOOK_ROOT, check=False)
    elapsed = time.perf_counter() - started
    if proc.returncode != 0:
        tail = (proc.stdout or '').strip().splitlines()[-8:]
        err = (proc.stderr or '').strip().splitlines()[-4:]
        print(f'  FAIL {name} (rc={proc.returncode})')
        for line in tail + err:
            print(f'    {line}')
    return name, proc.returncode, elapsed


def doctor() -> int:
    print('=== toolchain doctor ===')
    print(f'  python      : {sys.version.split()[0]}')
    problems = 0
    for module, users in OPTIONAL_TOOLS.items():
        found = importlib.util.find_spec(module) is not None
        if module == 'pandoc':
            found = bool(subprocess.run(['which', 'pandoc'], capture_output=True,
                                        check=False).stdout.strip())
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


def coverage() -> int:
    """Run the test suite under coverage and enforce the ratchet."""
    if importlib.util.find_spec('coverage') is None:
        print('coverage is not installed: pip install coverage')
        return 2
    threshold = _config.THRESHOLDS.get('coverage_fail_under', 0)
    tests = os.path.normpath(os.path.join(TOOLS_DIR, '..', 'test'))
    run = subprocess.run(
        [PY, '-m', 'coverage', 'run', '--source=books/src/python',
         '-m', 'unittest', 'discover', '-s', tests, '-t', tests],
        cwd=os.path.dirname(BOOK_ROOT), capture_output=True, text=True, check=False)
    if run.returncode != 0:
        print(run.stdout[-2000:])
        print(run.stderr[-1000:])
        return run.returncode
    report = subprocess.run(
        [PY, '-m', 'coverage', 'report', '--skip-covered',
         f'--fail-under={threshold}'],
        cwd=os.path.dirname(BOOK_ROOT), capture_output=True, text=True, check=False)
    print(report.stdout)
    print(report.stderr.strip())
    print(f'coverage gate: threshold {threshold}% -> '
          f'{"PASS" if report.returncode == 0 else "FAIL"}')
    return report.returncode


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command',
                        choices=['check', 'build', 'verify', 'test', 'cover',
                                 'deliver', 'doctor'])
    parser.add_argument('--only', help='comma-separated step names')
    parser.add_argument('--skip', help='comma-separated step names to skip')
    parser.add_argument('--timings', action='store_true', help='print per-step wall time')
    parser.add_argument('--keep-going', action='store_true',
                        help='run every step even after a failure')
    parser.add_argument('--full', action='store_true',
                        help='also run the slow suite (chromium/pandoc)')
    args = parser.parse_args(argv)

    if args.command == 'doctor':
        return doctor()

    if args.command == 'cover':
        return coverage()

    if args.full:
        os.environ['BOOK_SLOW'] = '1'
    steps = _select(args)
    if not steps:
        print('nothing to do')
        return 0

    failures: list[str] = []
    total = 0.0
    print(f'=== make {args.command}: {len(steps)} step(s) ===')
    for step in steps:
        name, code, elapsed = run_step(step)
        total += elapsed
        if code != 0:
            failures.append(name)
            if not args.keep_going:
                break
        elif args.timings:
            print(f'  ok   {name} ({elapsed:.2f}s)')

    if args.timings:
        print(f'  total {total:.2f}s')
    if failures:
        print(f'FAILED: {", ".join(failures)}')
        return 1
    print('OK')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
