#!/usr/bin/env python3
"""Enforce the toolchain architecture constraints from docs/managements/technical.md.

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
LAYERS = ('core', 'ingest', 'manuscript', 'audit', 'render', 'app')
# Channels may only reach the domain through core/ (plus lib for display config).
CHANNELS = 'app'
CHANNEL_FORBIDDEN_LAYERS = ('ingest', 'manuscript', 'audit', 'render')
CHANNEL_FORBIDDEN_CALLS = ('subprocess', 'write_text', "'w'", '"w"')

# Who may import whom. Anything not listed is a violation; the matrix is the
# contract, the checks below only explain the breach.
DEPENDENCY_MATRIX: dict[str, frozenset[str]] = {
    'lib': frozenset(),
    'core': frozenset({'lib'}),
    'ingest': frozenset({'lib'}),
    'manuscript': frozenset({'lib'}),
    'audit': frozenset({'lib'}),
    'render': frozenset({'lib'}),
    'app': frozenset({'lib', 'core', 'app'}),
}
STDLIB_CLASH = {'types', 'html', 'json', 'logging', 'email', 'code', 'test', 'binascii'}
PATH_LITERALS = ('books/', 'data/manuscript', 'data/config', 'data/tmpl')
WRITE_CALLS = ('write_text', 'open(')  # kept for the human-readable rule text
WRITE_MODES = 'wax+'


def layer_of(path: str, root: str | None = None) -> str:
    rel = os.path.relpath(path, root or PY_ROOT).replace(os.sep, '/')
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


def write_calls(tree: ast.AST) -> list[int]:
    """Line numbers of calls that write files (open in a write mode, write_text)."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, 'id', None) or getattr(func, 'attr', None)
        if name == 'write_text':
            lines.append(node.lineno)
            continue
        if name != 'open' or len(node.args) < 2:
            continue
        mode = node.args[1]
        literal_write = (isinstance(mode, ast.Constant) and isinstance(mode.value, str)
                         and any(flag in mode.value for flag in WRITE_MODES))
        keyword_mode = any(kw.arg == 'mode' for kw in node.keywords)
        if literal_write or keyword_mode:
            lines.append(node.lineno)
    return lines


def check(path: str, root: str | None = None) -> list[str]:
    problems: list[str] = []
    rel = os.path.relpath(path, os.path.join(_config.BOOK_ROOT, '..'))
    layer = layer_of(path, root)
    name = os.path.basename(path)[:-3]
    source = _fsutil.read_text(path)
    tree = ast.parse(source)

    # DOCSTRING: every module says what it is (naming is not documentation)
    if ast.get_docstring(tree) is None and not path.endswith('__init__.py'):
        problems.append(f'{rel}: missing module docstring')

    # MATRIX: the dependency matrix is authoritative - allowed edges only
    allowed = DEPENDENCY_MATRIX.get(layer)
    if allowed is not None:
        for module in imports_of(path):
            head = module.split('.')[0]
            if head in DEPENDENCY_MATRIX and head != layer and head not in allowed:
                problems.append(
                    f'{rel}: layer "{layer}" may not import "{module}" '
                    f'(allowed: {sorted(allowed) or "none"})')

    # LAYER: no sibling imports, no dependencies on render from below
    for module in imports_of(path):
        head = module.split('.')[0]
        allowed_up = (layer == 'app' and head == 'core')
        if head in LAYERS and head != layer and not allowed_up:
            problems.append(f'{rel}: imports sibling layer "{module}"')
        if head == 'render' and layer in ('ingest', 'manuscript', 'audit', 'lib'):
            problems.append(f'{rel}: layer "{layer}" must not depend on render')

    # CHANNEL: channels carry no business logic - no engine imports, no writes,
    # no process spawning. They render, read keys and call core.actions.
    if layer == CHANNELS:
        for module in imports_of(path):
            head = module.split('.')[0]
            if head in CHANNEL_FORBIDDEN_LAYERS:
                problems.append(
                    f'{rel}: channel imports "{module}"; go through core.actions')
            if head in ('make',):
                problems.append(f'{rel}: channel must not drive make.py directly')
        for call in CHANNEL_FORBIDDEN_CALLS:
            if call in source:
                problems.append(f'{rel}: channel contains "{call}" (business logic)')

    # DIRECTION: core is a domain layer, it never depends on the channels
    if layer == 'core':
        for module in imports_of(path):
            if module.split('.')[0] == 'app':
                problems.append(f'{rel}: core must not depend on the channel layer')

    # WRITE: gates must not modify the manuscript or artifacts (baselines excepted)
    if layer == 'audit' and 'baseline' not in source:
        writers = write_calls(tree)
        if writers:
            problems.append(
                f'{rel}: "{layer}" layer must not write files (line {writers[0]})')

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


def check_scripts(scripts_dir: str | None = None) -> list[str]:
    """Name convention for the top-level wrappers in books/scripts/.

    `check-*` verifies (exit code decides), `eval-*` measures, `new-*` generates
    a new book; the interactive and setup entry points keep their names. One
    pattern per file, so the directory itself documents what a script is for.
    """
    directory = scripts_dir or os.path.join(_config.BOOK_ROOT, 'scripts')
    allowed = ('bookctl', 'launch', 'bootstrap', 'check', 'eval', 'new',
               'test', 'release', 'install')
    problems: list[str] = []
    if not os.path.isdir(directory):
        return problems
    try:
        entries = sorted(os.listdir(directory))
    except OSError as exc:
        return [f'scripts/: cannot list the directory: {exc}']
    for name in entries:
        path = os.path.join(directory, name)
        if not os.path.isfile(path) or name.startswith('.'):
            continue
        stem = name.rsplit('.', 1)[0]
        if not name.endswith(('.sh', '.ps1')):
            if name != 'bookctl':
                problems.append(f'scripts/{name}: unexpected file (expected .sh/.ps1)')
            continue
        if not any(stem == prefix or stem.startswith(prefix + '-') for prefix in allowed):
            problems.append(
                f'scripts/{name}: name must start with one of {", ".join(allowed)}')
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    problems: list[str] = check_scripts()
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
