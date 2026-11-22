#!/usr/bin/env python3
"""Trace each requirement to the check that proves it.

`requirements.md` states what the tool must do; the testplan states how each
statement is judged. Nothing compared the two lists, so a requirement could sit
unverified and a judgement row could outlive its requirement. Both directions are
reported here, together with a carrier that does not exist on disk.

A trace row either names its carriers in back-ticks (a script, a workflow, a test)
or says `人工复核` / `CI 编排` when no single file can prove it.

Usage:
  python requirement_trace.py
  python requirement_trace.py --json

Exit 1 on any finding, 2 on a usage error.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

ID_RE = re.compile(r'^\|\s*((?:FR|IR|NFR)-\d{2})\s*\|')
CARRIER_RE = re.compile(r'`([A-Za-z0-9_.][A-Za-z0-9_./-]*\.(?:py|sh|yml|toml|json))`')
MANUAL_MARKERS = ('人工复核', 'CI 编排')
REQUIREMENT_DOC = 'requirements.md'
TRACE_DOC = 'testplan.md'


def managements_dir() -> str:
    return os.path.join(_config.BOOK_ROOT, 'docs', 'managements')


def requirement_ids(path: str | None = None) -> list[str]:
    """Requirement identifiers in declaration order."""
    target = path or os.path.join(managements_dir(), REQUIREMENT_DOC)
    out: list[str] = []
    for line in _fsutil.read_lines(target):
        match = ID_RE.match(line)
        if match is not None and match.group(1) not in out:
            out.append(match.group(1))
    return out


def trace_rows(path: str | None = None) -> list[tuple[str, str, int]]:
    """(identifier, judgement cell, line) for every trace row in the testplan."""
    target = path or os.path.join(managements_dir(), TRACE_DOC)
    out: list[tuple[str, str, int]] = []
    for lineno, line in enumerate(_fsutil.read_lines(target), start=1):
        match = ID_RE.match(line)
        if match is None:
            continue
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        out.append((match.group(1), ' | '.join(cells[1:]), lineno))
    return out


def known_carriers() -> set[str]:
    """Every script name the toolchain actually ships, plus repo-relative paths."""
    book = _config.BOOK_ROOT
    repo = os.path.dirname(book)
    names = set()
    for root, pattern in ((book, 'src/**/*.py'), (book, 'scripts/*'),
                          (repo, '.github/workflows/*')):
        for path in glob.glob(os.path.join(root, pattern), recursive=True):
            if os.path.isfile(path):
                names.add(os.path.basename(path))
                names.add(os.path.relpath(path, book).replace(os.sep, '/'))
                names.add(os.path.relpath(path, repo).replace(os.sep, '/'))
    return names


PARTS_RE = re.compile(r'^([A-Z]+)-(\d+)$')


def gaps(declared: list[str]) -> list[str]:
    """Identifiers that the numbering skipped, per family.

    A requirement row that silently fails to get written leaves no trace at all:
    `check` compares declared against traced, so an id nobody declares is invisible.
    Gaps make that visible — IR-01..IR-13 with IR-12 missing is a hole, not a gap in
    the numbering scheme.
    """
    families: dict[str, list[int]] = {}
    for identifier in declared:
        match = PARTS_RE.match(identifier)
        if match is None:
            continue
        families.setdefault(match.group(1), []).append(int(match.group(2)))
    missing: list[str] = []
    for family, numbers in sorted(families.items()):
        present = set(numbers)
        missing += [f'{family}-{number:02d}'
                    for number in range(1, max(present) + 1) if number not in present]
    return missing


def check(requirements: list[str] | None = None,
          rows: list[tuple[str, str, int]] | None = None,
          carriers: set[str] | None = None) -> list[dict]:
    declared = requirements if requirements is not None else requirement_ids()
    traced = rows if rows is not None else trace_rows()
    available = carriers if carriers is not None else known_carriers()
    rel = os.path.join('docs', 'managements', TRACE_DOC)
    out: list[dict] = []
    seen: dict[str, int] = {}
    for identifier, cell, lineno in traced:
        if identifier in seen:
            out.append({'kind': 'TRACE', 'file': rel, 'line': lineno,
                        'detail': f'{identifier} traced twice'})
            continue
        seen[identifier] = lineno
        if identifier not in declared:
            out.append({'kind': 'TRACE', 'file': rel, 'line': lineno,
                        'detail': f'{identifier} is traced but not declared in {REQUIREMENT_DOC}'})
            continue
        named = CARRIER_RE.findall(cell)
        if not named and not any(marker in cell for marker in MANUAL_MARKERS):
            out.append({'kind': 'TRACE', 'file': rel, 'line': lineno,
                        'detail': f'{identifier} names no carrier and no manual marker'})
            continue
        for name in named:
            if name not in available:
                out.append({'kind': 'TRACE', 'file': rel, 'line': lineno,
                            'detail': f'{identifier} names {name}, which does not exist'})
    if requirements is None:
        # only the real document has to number contiguously; synthetic lists in tests do not
        for identifier in gaps(declared):
            out.append({'kind': 'GAP',
                        'file': os.path.join('docs', 'managements', REQUIREMENT_DOC),
                        'line': 0, 'detail': f'{identifier} is missing from the numbering'})
    for identifier in declared:
        if identifier not in seen:
            out.append({'kind': 'TRACE', 'file': rel, 'line': 1,
                        'detail': f'{identifier} has no judgement row'})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    declared = requirement_ids()
    if not declared:
        print(f'❌ {REQUIREMENT_DOC} 里没有读到任何需求编号', file=sys.stderr)
        return 2
    findings = check(declared)

    if args.json:
        print(json.dumps({'count': len(findings), 'requirements': declared,
                          'findings': findings}, ensure_ascii=False, indent=2))
        return 0 if not findings else 1

    if not findings:
        print(f'✅ 需求判据可追溯（{len(declared)} 条需求，各一条判据）')
        return 0
    print(f'需求追溯问题 {len(findings)} 处：')
    for item in findings[:40]:
        print(f"  {item['file']}:{item['line']}  {item['detail']}")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
