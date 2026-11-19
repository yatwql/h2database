#!/usr/bin/env python3
"""Enforce the toolchain architecture constraints from docs/spec/technical.md.

Checks
  LAYER    import direction (lib <- ingest/manuscript/audit/render, no siblings)
  WRITE    audit/ and lib/ must not write to the repository
  CONFIG   scripts outside lib/ must not hardcode repository paths
  NAMING   no stdlib-clashing module names, no redundant audit prefixes,
           no underscore prefixes on CLI entry points
  EXIT     report scripts expose --json or document exit codes

Exit 1 on any finding.

Usage:
  python check_architecture.py
  python check_architecture.py --json
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

PY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAYERS = ('ingest', 'manuscript', 'audit', 'render', 'app')
STDLIB_CLASH = {'types', 'html', 'json', 'logging', 'email', 'code', 'test', 'binascii'}
PATH_LITERALS = ('books/', 'data/manuscript', 'data/config', 'data/tmpl')
WRITE_CALLS = ('write_text', 'open(')


def layer_of(path: str) -> str:
    rel = os.path.relpath(path, PY_ROOT).replace(os.sep, '/')
    return rel.split('/')[0] if '/' in rel else ''


def scripts() -> list[str]:
    return sorted(p for p in glob.glob(os.path.join(PY_ROOT, '**', '*.py'), recursive=True)
                  if '__pycache__' not in p)


def imports_of(path: str) -> list[str]:
    tree = ast.parse(_fsutil.read_text(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
            for alias in node.names:
                found.append(f'{node.module}.{alias.name}')
        elif isinstance(node, ast.Import):
            found += [alias.name for alias in node.names]
    return found


def check(path: str) -> list[str]:
    problems: list[str] = []
    rel = os.path.relpath(path, os.path.join(_config.BOOK_ROOT, '..'))
    layer = layer_of(path)
    name = os.path.basename(path)[:-3]
    source = _fsutil.read_text(path)

    # LAYER: no sibling imports, no dependencies on render from below
    for module in imports_of(path):
        head = module.split('.')[0]
        if head in LAYERS and head != layer:
            problems.append(f'{rel}: imports sibling layer "{module}"')
        if head == 'render' and layer in ('ingest', 'manuscript', 'audit', 'lib'):
            problems.append(f'{rel}: layer "{layer}" must not depend on render')

    # WRITE: gates must not modify the manuscript or artifacts (baselines excepted)
    if layer == 'audit' and 'baseline' not in source:
        for call in WRITE_CALLS:
            if call in source and 'add_note' not in source:
                if call == 'open(' and "'w'" not in source and '"w"' not in source:
                    continue
                problems.append(f'{rel}: "{layer}" layer must not write files')

    # CONFIG: no hardcoded repository paths outside lib/ (the gate defines them)
    if layer != 'lib' and name != 'check_architecture':
        for literal in PATH_LITERALS:
            if f'"{literal}' in source or f"'{literal}" in source:
                problems.append(f'{rel}: hardcodes repository path "{literal}"')

    # NAMING
    if name in STDLIB_CLASH:
        problems.append(f'{rel}: module name "{name}" shadows a stdlib module')
    if layer == 'audit' and name != 'check_architecture' \
            and (name.startswith(('audit_', 'check_')) or name.endswith('_check')):
        problems.append(f'{rel}: redundant audit/check prefix or suffix')
    in_library_pkg = (os.sep + 'languages' + os.sep) in path or (os.sep + 'lib' + os.sep) in path
    if name.startswith('_') and not in_library_pkg and not path.endswith('__init__.py'):
        problems.append(f'{rel}: CLI entry point must not start with an underscore')

    # EXIT: report scripts expose --json
    if layer in ('audit',) and 'argument' in source and '--json' not in source:
        problems.append(f'{rel}: report script should support --json')
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    problems: list[str] = []
    for path in scripts():
        try:
            problems += check(path)
        except SyntaxError as exc:  # pragma: no cover - parse failures surface elsewhere
            problems.append(f'{os.path.relpath(path, PY_ROOT)}: {exc}')

    if args.json:
        print(json.dumps({'count': len(problems), 'problems': problems},
                         ensure_ascii=False, indent=2))
        return 0 if not problems else 1

    if not problems:
        print('✅ 架构约束通过')
        return 0
    print(f'架构约束问题 {len(problems)} 处：')
    for problem in problems:
        print(f'  - {problem}')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
