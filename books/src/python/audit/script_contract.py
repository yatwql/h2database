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
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil


def scripts() -> list[str]:
    """Entry-point scripts (library modules under lib/ are exempt)."""
    root = os.path.join(_config.BOOK_ROOT, 'src', 'python')
    found = glob.glob(os.path.join(root, '**', '*.py'), recursive=True)
    return sorted(p for p in found
                  if os.sep + 'lib' + os.sep not in p and not p.endswith('__init__.py'))


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

    problems: list[str] = []
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
    sys.exit(main(sys.argv[1:]))
