#!/usr/bin/env python3
"""Test-suite hygiene: redundant, assertion-free and shadowed test cases.

Four checks, each answering one question about the test tree (adapted from
investor-review's redundancy family):

  DUPLICATE   two test methods run the identical body (copy-paste that will
              drift apart); the body is normalised before comparison
  NO-ASSERT   a test method contains no assertion at all — it can only fail by
              raising, which is not what its name promises
  TRIVIAL     the body is only `pass` or `assert True`
  DEAD        a `test_*` method sits in a class that is not a TestCase subclass,
              or a later definition silently shadows an earlier one

Usage:
  python test_redundancy.py            # report + exit code
  python test_redundancy.py --json
  python test_redundancy.py --strict   # fail on advisory (near-duplicate) findings too

Exit codes: 0 clean, 1 findings, 2 usage error.
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import re
import sys
import textwrap
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil

PY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_ROOT = os.path.join(_config.BOOK_ROOT, 'src', 'test')
ASSERT_PREFIX = 'assert'
ASSERT_CALLS = frozenset({'assertRaises', 'assertWarns', 'assertCountEqual',
                          'fail', 'assertLogs'})
TRIVIAL_BODIES = frozenset({'pass', 'assert True', 'assert 1', 'assert'})
SKIP_FILES = ('conftest.py', '__init__.py')


class Case(NamedTuple):
    """One test method as the AST sees it."""

    path: str
    class_name: str
    name: str
    lineno: int
    body: str


def test_files(root: str | None = None) -> list[str]:
    base = root or TEST_ROOT
    return sorted(p for p in glob.glob(os.path.join(base, '**', '*.py'), recursive=True)
                  if '__pycache__' not in p and os.path.basename(p) not in SKIP_FILES)


def normalise(body: str) -> str:
    """Strip comments, blank lines and indentation so copies compare equal."""
    lines = []
    for line in body.splitlines():
        stripped = line.split('#', 1)[0].rstrip()
        if stripped.strip():
            lines.append(stripped)
    # the method is indented inside its class; dedent so the body parses alone
    return textwrap.dedent('\n'.join(lines))


def has_assertion(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            return True
        if isinstance(child, ast.Call):
            func = child.func
            name = getattr(func, 'id', None) or getattr(func, 'attr', None) or ''
            if name.startswith(ASSERT_PREFIX) or name in ASSERT_CALLS:
                return True
    return False


def cases_in(path: str) -> list[Case]:
    source = _fsutil.read_text(path)
    tree = ast.parse(source)
    lines = source.splitlines()
    found: list[Case] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not (isinstance(item, ast.FunctionDef) and item.name.startswith('test_')):
                continue
            body = '\n'.join(lines[item.lineno - 1:item.end_lineno])
            found.append(Case(path, node.name, item.name, item.lineno, body))
    return found


# Base classes the suite uses (src/test/_cases.py) count as test cases even
# though the name does not end in TestCase.
KNOWN_BASES = frozenset({'TestCase', 'TempFileCase', 'FixtureCase', 'FixtureTest',
                         'ScriptTestBase', 'Base', 'DepthCase'})


def is_test_case(node: ast.ClassDef) -> bool:
    for base in node.bases:
        name = getattr(base, 'id', None) or getattr(base, 'attr', None) or ''
        if name in KNOWN_BASES or name.endswith(('TestCase', 'Case', 'Test')):
            return True
    return False


def dead_cases(path: str) -> list[dict]:
    tree = ast.parse(_fsutil.read_text(path))
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if not is_test_case(node):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                        findings.append({'kind': 'DEAD', 'file': rel(path),
                                         'line': item.lineno,
                                         'detail': f'{node.name}.{item.name} is not in a TestCase'})
            else:
                seen: dict[str, int] = {}
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                        if item.name in seen:
                            findings.append({'kind': 'DEAD', 'file': rel(path),
                                             'line': item.lineno,
                                             'detail': f'{node.name}.{item.name} shadows line {seen[item.name]}'})
                        seen[item.name] = item.lineno
    return findings


def rel(path: str) -> str:
    return os.path.relpath(path, os.path.join(_config.BOOK_ROOT, '..'))


LOOSE_RE = re.compile(r'assertIn\(\s*code\s*,\s*\(([^)]*)\)')
LOOSE_BASELINE = os.path.join('data', 'baselines', 'loose-assertions.json')


def _loose_baseline() -> set[str]:
    from lib import _config as config
    path = os.path.join(config.BOOK_ROOT, LOOSE_BASELINE)
    if not os.path.isfile(path):
        return set()
    try:
        payload = json.loads(_fsutil.read_text(path))
    except (OSError, ValueError):
        return set()
    return {str(item) for item in payload.get('accepted') or []}


CONTENT_ASSERT_RE = re.compile(
    r"assert(?:In|NotIn|Regex|Equal|True)\(\s*[^)]*?['\"]([^'\"]{3,})['\"]")


def _names_a_finding(body: str) -> bool:
    """Whether the case asserts a concrete message besides the exit code."""
    for literal in CONTENT_ASSERT_RE.findall(body):
        if literal.strip() not in ('Traceback', '\n'):
            return True
    return False


def loose_candidates(root: str | None = None) -> list[dict]:
    """Cases whose sole outcome check is a loose exit-code assertion.

    ``assertIn(code, (0, 1))`` passes whether the step worked or not, so the code
    says nothing about the outcome. A case that also asserts what the output says
    is pinned already, and is not a candidate.
    """
    findings: list[dict] = []
    for path in test_files(root):
        try:
            tree = ast.parse(_fsutil.read_text(path))
        except SyntaxError:  # pragma: no cover - reported by analyse()
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith('test_'):
                continue
            lines = _fsutil.read_text(path).split('\n')[node.lineno - 1:node.end_lineno]
            body = '\n'.join(lines)
            # A loose code check is acceptable when the case also asserts what the
            # output says: the outcome is still pinned, the code is not the subject.
            if _names_a_finding(body):
                continue
            for line in lines:
                match = LOOSE_RE.search(line)
                if not match:
                    continue
                codes = [part.strip() for part in match.group(1).split(',')]
                if '0' not in codes or '1' not in codes:
                    continue
                findings.append({'kind': 'LOOSE-ASSERT', 'file': rel(path),
                                 'line': node.lineno,
                                 'detail': f'{node.name}: assertIn(code, ({match.group(1)})) '
                                           'accepts both success and failure'})
                break
    return findings


def _loose_key(item: dict) -> str:
    """Stable key for one candidate: file plus test name."""
    return f"{item['file']}::{item['detail'].split(':')[0]}"


def analyse(root: str | None = None) -> list[dict]:
    findings: list[dict] = []
    bodies: dict[str, list[Case]] = {}
    for path in test_files(root):
        try:
            cases = cases_in(path)
        except SyntaxError as exc:  # pragma: no cover - a broken test file is loud elsewhere
            findings.append({'kind': 'SYNTAX', 'file': rel(path), 'line': exc.lineno or 0,
                             'detail': exc.msg})
            continue
        findings += dead_cases(path)
        for case in cases:
            body = normalise(case.body)
            try:
                tree = ast.parse(body or 'pass')
            except SyntaxError:      # a body that does not parse alone: skip it
                continue
            if not has_assertion(tree):
                findings.append({'kind': 'NO-ASSERT', 'file': rel(path), 'line': case.lineno,
                                 'detail': f'{case.class_name}.{case.name}'})
            elif body.splitlines()[-1] in TRIVIAL_BODIES:
                findings.append({'kind': 'TRIVIAL', 'file': rel(path), 'line': case.lineno,
                                 'detail': f'{case.class_name}.{case.name}'})
            signature = _signature(body)
            bodies.setdefault(signature, []).append(case)
    candidates = loose_candidates(root)
    accepted = _loose_baseline()
    findings += [item for item in candidates if _loose_key(item) not in accepted]
    stale = sorted(accepted - {_loose_key(item) for item in candidates})
    if stale:
        print(f'  [warn] {len(stale)} 条松散断言基线已不再命中'
              f'（已收紧，可收缩 data/baselines/loose-assertions.json）', file=sys.stderr)

    for group in sorted(bodies.values(), key=len, reverse=True):
        if len(group) < 2:
            continue
        first = group[0]
        for other in group[1:]:
            findings.append({'kind': 'DUPLICATE', 'file': rel(other.path),
                             'line': other.lineno,
                             'detail': (f'{other.class_name}.{other.name} duplicates '
                                        f'{first.class_name}.{first.name} '
                                        f'({os.path.basename(first.path)})')})
    return findings


def _signature(body: str) -> str:
    """Body without the `def` line and whitespace: copies share a key."""
    lines = normalise(body).splitlines()[1:]
    return re.sub(r'\s+', '', '\n'.join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--strict', action='store_true',
                        help='treat DUPLICATE findings as blocking (they always are)')
    args = parser.parse_args(argv)

    findings = analyse()
    blocking = [f for f in findings if f['kind'] != 'TRIVIAL']
    if args.json:
        print(json.dumps({'count': len(findings),
                          'blocking': len(blocking), 'findings': findings},
                         ensure_ascii=False, indent=2))
        return 0 if not blocking else 1

    if not findings:
        print('✅ 测试用例无冗余（无重复体、无空断言、无遮蔽）')
        return 0
    print(f'测试用例问题 {len(findings)} 处（其中阻塞 {len(blocking)}）：')
    for item in findings[:60]:
        print(f"  [{item['kind']}] {item['file']}:{item['line']}  {item['detail']}")
    return 0 if not blocking else 1


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
