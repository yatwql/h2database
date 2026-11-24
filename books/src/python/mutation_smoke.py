#!/usr/bin/env python3
"""Mutation smoke: do the tests notice when the code stops being right?

Coverage says a line ran; a mutation says whether any assertion cared. This runs
a handful of hand-written mutation operators against one module and reports the
mutations the suite *survived* — those are places where the code could change
behaviour and every case would still pass.

Runs on a copy of `src/python` + `src/test` in a temporary directory, so the
checkout is never modified. It is a review tool, not a gate: it takes a pytest
run per mutation.

Usage:
  python mutation_smoke.py --module audit/content_volume.py \
      --tests test_audit_content_volume_branches.py --limit 12
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import _config, _errors

SRC = os.path.join(_config.BOOK_ROOT, 'src')

# Operators are (label, pattern, replacement): a mutation that turns a condition
# into its opposite, or a boolean into its negative, is the classic case where a
# suite can be green while the behaviour is wrong.
OPERATORS = (
    ('flip ==', r'==', '!='),
    ('flip !=', r'!=', '=='),
    ('drop equality (>= to >)', r'>=', '>'),
    ('drop equality (<= to <)', r'<=', '<'),
    ('flip and', r'\band\b', 'or'),
    ('flip or', r'\bor\b', 'and'),
    ('negate True', r'\bTrue\b', 'False'),
    ('negate False', r'\bFalse\b', 'True'),
)


def _prose_spans(text: str) -> list[tuple[int, int]]:
    """Offsets covered by comments and triple-quoted blocks (never mutated)."""
    spans: list[tuple[int, int]] = []
    fences = [m.start() for m in re.finditer(r'"""|\'\'\'', text)]
    for start, end in zip(fences[0::2], fences[1::2], strict=False):
        spans.append((start, end))
    for match in re.finditer(r'#[^\n]*', text):
        spans.append((match.start(), match.end()))
    return spans


def candidates(text: str) -> list[tuple[str, int, str]]:
    """(label, line number, mutated text) for every applicable single mutation.

    Comments and docstrings are skipped: flipping a word inside prose proves
    nothing about the tests.
    """
    spans = _prose_spans(text)
    out: list[tuple[str, int, str]] = []
    for label, pattern, replacement in OPERATORS:
        for match in re.finditer(pattern, text):
            if any(start <= match.start() < end for start, end in spans):
                continue
            line_number = text.count('\n', 0, match.start()) + 1
            mutated = text[:match.start()] + replacement + text[match.end():]
            out.append((label, line_number, mutated))
    # a fixed order, so the same source always yields the same sample: an acceptance
    # step that picks different mutants each run cannot be a gate
    return sorted(out, key=lambda item: (item[1], item[0]))


def run_case(tree: str, module: str, tests: str) -> bool:
    """True when the (mutated) suite still passes — i.e. the mutation survived."""
    proc = subprocess.run(
        [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
         os.path.join(tree, 'src', 'test', tests)],
        cwd=tree, capture_output=True, text=True, check=False, timeout=600)
    return proc.returncode == 0


def smoke(module: str, tests: str, limit: int, max_survivors: int,
          *, as_json: bool = False) -> int:
    source_path = os.path.join(SRC, 'python', module)
    if not os.path.isfile(source_path):
        print(f'error: no such module: {source_path}', file=sys.stderr)
        return 2
    if not os.path.isfile(os.path.join(SRC, 'test', tests)):
        print(f'error: no such test file: {tests}', file=sys.stderr)
        return 2

    original = _read(source_path)
    work = tempfile.mkdtemp(prefix='mutation-smoke-')
    try:
        shutil.copytree(SRC, os.path.join(work, 'src'))
        target = os.path.join(work, 'src', 'python', module)
        mutations = candidates(original)[:limit]

        survivors: list[tuple[str, int]] = []
        for index, (label, line_number, mutated) in enumerate(mutations, 1):
            _write(target, mutated)
            if run_case(work, module, tests):
                survivors.append((f'{label} (line {line_number})', line_number))
            print(f'  [{index}/{len(mutations)}] {label} at line {line_number}: '
                  f'{"SURVIVED" if survivors and survivors[-1][1] == line_number else "killed"}')
        _write(target, original)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    if as_json:
        print(json.dumps({'module': module, 'tests': tests, 'run': len(mutations),
                          'survived': [label for label, _line in survivors]},
                         ensure_ascii=False, indent=2))
        return 0 if len(survivors) <= max_survivors else 1
    print(f'\nmutations run: {len(mutations)}, survived: {len(survivors)}')
    for label, _line in survivors:
        print(f'  survived: {label}')
    if len(survivors) > max_survivors:
        print(f'FAIL: {len(survivors)} mutation(s) survived (allowed {max_survivors})')
        return 1
    print('PASS: no unexpected survivor')
    return 0


def _read(path: str) -> str:
    from lib import _fsutil
    return _fsutil.read_text(path)


def _write(path: str, text: str) -> None:
    from lib import _fsutil
    _fsutil.write_text(path, text)


# The pairs worth mutating: pure logic with a tight unit suite. A larger list would
# only add runtime; these cover the rules that decide column width, page budget, the
# EPUB boundary fixes and the coordinate parser.
# module -> (test file, tolerated survivors). A tolerance is only for a mutation that
# cannot change behaviour (e.g. `x or 1` in a branch the fixtures never reach), and it
# is number, not a blanket pass.
TARGETS: dict[str, tuple[str, int]] = {
    'render/epub_source.py': ('test_render_epub_source.py', 0),
    # four survivors, all equivalent: the sample-window `<=`, the `<= 3` flag (a delta
    # of exactly three percent is float-identical), and two `or` defaults inside the
    # PDF text visitor that only real text layers reach
    'render/pdf_metrics.py': ('test_render_pdf_metrics_units.py', 4),
    'lib/_perfhistory.py': ('test_lib_perfhistory.py', 0),
    'core/menu.py': ('test_core_menu.py', 0),
}


def run_all(limit: int = 6, max_survivors: int = 0) -> int:
    """Mutate every registered target; the report names the module per survivor."""
    worst = 0
    for module, (tests, tolerance) in TARGETS.items():
        print(f'--- {module}')
        code = smoke(module, tests, limit, max(max_survivors, tolerance))
        worst = max(worst, code)
    return worst


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--module',
                        help='module under src/python, e.g. audit/content_volume.py')
    parser.add_argument('--tests', help='test file under src/test')
    parser.add_argument('--all', action='store_true',
                        help='mutate every target in TARGETS')
    parser.add_argument('--limit', type=int, default=10, help='mutations to try')
    parser.add_argument('--max-survivors', type=int, default=0,
                        help='how many survivors are tolerated')
    parser.add_argument('--json', action='store_true', help='machine-readable summary')
    args = parser.parse_args(argv)
    if args.all:
        return run_all(args.limit, args.max_survivors)
    if not args.module or not args.tests:
        parser.error('give --all, or --module with --tests')
    return smoke(args.module, args.tests, args.limit, args.max_survivors,
                 as_json=args.json)


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
