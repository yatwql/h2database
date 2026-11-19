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

from lib import _config, _log

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_ROOT = _config.BOOK_ROOT
PY = sys.executable
LOG = _log.get_logger('make')

# (name, script or None for builtin, extra args, group)
Step = tuple[str, str | None, tuple[str, ...], str]

STEPS: list[Step] = [
    # ---- build ----
    ('cover_stats', 'manuscript/cover.py', (), 'build'),
    ('rebuild_merged', 'render/merge.py', (), 'build'),
    ('to_html', 'render/to_html.py', (), 'build'),
    # ---- verify ----
    ('architecture', 'audit/check_architecture.py', (), 'verify'),
    ('llm_policy', 'audit/llm_policy.py', (), 'verify'),
    ('gate_trace', 'audit/gate_trace.py', (), 'verify'),
    ('versions', 'audit/version_consistency.py', (), 'verify'),
    ('typecheck', 'audit/typecheck.py', (), 'verify'),
    ('portability', 'audit/portability.py', (), 'verify'),
    ('style_schema', 'audit/style_schema.py', (), 'verify'),
    ('file_length', 'audit/file_length.py', (), 'verify'),
    ('script_contract', 'audit/script_contract.py', (), 'verify'),
    ('traces', 'audit/traces.py', (), 'verify'),
    ('doc_drift', 'audit/doc_drift.py', (), 'verify'),
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
    # ---- deliver ----
    ('to_pdf', 'render/to_pdf.py', (), 'deliver'),
    ('verify_pdf', 'render/verify_pdf.py', ('--require-toc-links',), 'deliver'),
    ('to_epub', 'render/to_epub.py', (), 'deliver'),
    ('verify_epub', 'render/verify_epub.py', (), 'deliver'),
]

GROUPS = {
    'build': ('cover_stats', 'rebuild_merged', 'to_html'),
    'verify': tuple(n for n, _s, _a, g in STEPS if g == 'verify'),
    'deliver': ('to_pdf', 'verify_pdf', 'to_epub', 'verify_epub'),
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
        cmd = [PY, '-m', 'unittest', 'discover', '-s', tests_dir, '-t', tests_dir]
    else:
        cmd = [PY, os.path.join(TOOLS_DIR, script), *extra]
    LOG.debug('run step %s: %s', name, ' '.join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=BOOK_ROOT, check=False)
    elapsed = time.perf_counter() - started
    if proc.returncode != 0:
        LOG.warning('step %s failed rc=%s (%.2fs)', name, proc.returncode, elapsed)
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


def report(extra: list[str] | None = None) -> int:
    """Six-dimension release scorecard (book quality, code, docs, interaction)."""
    extra = extra or []
    proc = subprocess.run([PY, os.path.join(TOOLS_DIR, 'audit', 'scorecard.py'), *extra],
                          cwd=os.path.dirname(BOOK_ROOT), check=False)
    return proc.returncode


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

    report_extras: list[str] = []
    if argv and len(argv) > 0 and argv[0] == 'report':
        args, report_extras = parser.parse_known_args(argv)
    else:
        args = parser.parse_args(argv)

    if args.command == 'doctor':
        return doctor()

    if args.command == 'cover':
        return coverage()

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
    sys.exit(main(sys.argv[1:]))
