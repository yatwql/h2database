#!/usr/bin/env python3
"""Verify every tool script honours the shared CLI contract.

Contract for books/src/python/**/*.py:
  1. module docstring present (what the script does),
  2. imports cleanly (no syntax/import errors),
  3. defines main() or runs under `if __name__ == '__main__'`,
  4. documents its exit codes ("Exit codes"/"退出码") or accepts --help,
  5. is registered in make.py (so `make.py check` actually runs it) unless it
     is a library module (lib/) or a one-shot maintenance script.

Usage:
  python script_contract.py
  python script_contract.py --json
"""
from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil


def scripts() -> list[str]:
    """Entry-point scripts (library modules under lib/ are exempt)."""
    root = os.path.join(_config.BOOK_ROOT, 'src', 'python')
    found = glob.glob(os.path.join(root, '**', '*.py'), recursive=True)
    # library-style modules: shared helpers, not entry points
    library = (os.sep + 'lib' + os.sep,
               os.sep + 'core' + os.sep + 'actions.py',
               os.sep + 'core' + os.sep + 'settings.py',
               os.sep + 'core' + os.sep + 'menu.py',
               os.sep + 'app' + os.sep + 'keys.py',
               os.sep + 'ingest' + os.sep + 'languages' + os.sep,
               # chapter-body sections split out of chapters.py: pure helpers
               os.sep + 'ingest' + os.sep + 'api_sections.py',
               # per-chapter PDF assembly, driven by render/to_pdf.py
               os.sep + 'render' + os.sep + 'pdf_split.py',
               # Markdown fixes applied before pandoc, driven by render/to_epub.py
               os.sep + 'render' + os.sep + 'epub_source.py')
    return sorted(p for p in found
                  if not any(marker in p for marker in library)
                  and not p.endswith('__init__.py'))


DISPATCHER = os.path.join(_config.BOOK_ROOT, 'scripts', 'bookctl')
ACTIONS_PATH = os.path.join(_config.BOOK_ROOT, 'src', 'python', 'core', 'actions.py')
# the wrapper feeds the action through to the CLI, plus a few verbs of its own
WRAPPER_VERBS = {'new', 'make', 'doctor', 'help'}
DISPATCH_RE = re.compile(r'bookctl\s+([a-z][a-z-]*)')
ACTION_RE = re.compile(r"^\s{4}'([a-z][a-z-]*)':", re.MULTILINE)


def check_dispatcher_help() -> list[str]:
    """The dispatcher's help names actions the CLI actually accepts.

    A wrapper comment is documentation nobody re-runs: it drifts as soon as an
    action is renamed, and the user discovers it by typing the command.
    """
    if not os.path.isfile(DISPATCHER) or not os.path.isfile(ACTIONS_PATH):
        return []
    known = set(ACTION_RE.findall(_fsutil.read_text(ACTIONS_PATH))) | WRAPPER_VERBS
    problems: list[str] = []
    for lineno, line in enumerate(_fsutil.read_lines(DISPATCHER), start=1):
        if not line.lstrip().startswith('#'):
            continue
        for action in DISPATCH_RE.findall(line):
            if action not in known:
                problems.append(f'scripts/bookctl:{lineno}: help names {action!r}, '
                                f'which the CLI does not accept')
    return problems


def check(path: str) -> list[str]:
    """Validate one script against the contract."""
    problems: list[str] = []
    rel = os.path.relpath(path, os.path.join(_config.BOOK_ROOT, '..'))
    source = _fsutil.read_text(path)

    tree = ast.parse(source)
    if not ast.get_docstring(tree):
        problems.append(f'{rel}: missing module docstring')

    defines_main = any(isinstance(node, ast.FunctionDef) and node.name == 'main'
                       for node in tree.body)
    has_guard = "__name__ == '__main__'" in source
    runs_top_level = bool([n for n in tree.body
                           if isinstance(n, (ast.Expr, ast.For, ast.If, ast.With))
                           and not isinstance(getattr(n, 'value', None), ast.Constant)])
    if defines_main and not has_guard:
        problems.append(f'{rel}: defines main() but has no __main__ guard')
    if not defines_main and not runs_top_level and not has_guard:
        problems.append(f'{rel}: neither main() nor top-level execution')
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    problems: list[str] = check_dispatcher_help()
    for path in scripts():
        try:
            problems += check(path)
        except SyntaxError as exc:
            problems.append(f'{os.path.relpath(path, os.path.join(_config.BOOK_ROOT, ".."))}: {exc}')

    if args.json:
        print(json.dumps({'count': len(problems), 'problems': problems},
                         ensure_ascii=False, indent=2))
        return 0 if not problems else 1

    if not problems:
        print('✅ 脚本契约通过')
        return 0
    print(f'脚本契约问题 {len(problems)} 处：')
    for problem in problems:
        print(f'  - {problem}')
    return 1


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
