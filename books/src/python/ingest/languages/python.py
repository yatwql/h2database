#!/usr/bin/env python3
"""Python analyzer: AST-based modules, classes/functions, docstrings, imports."""
from __future__ import annotations

import ast
import os

from ingest.languages._base import Analyzer, Module, Unit, first_sentence
from lib import _fsutil


class PythonAnalyzer(Analyzer):
    """Digest a Python tree (modules from directories, units from the AST)."""

    name = 'python'
    suffixes = ('.py',)

    def package_of(self, root: str, path: str) -> str:
        rel = os.path.dirname(os.path.relpath(path, root))
        return rel.replace(os.sep, '.') or 'root'

    def parse(self, path: str) -> Module:
        try:
            text = _fsutil.read_text_raw(path)
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            return Module(package='unparsed', path=os.path.dirname(path), summary='unparsed')
        module_doc = first_sentence(ast.get_docstring(tree) or '')
        units: list[Unit] = []
        deps: dict[str, int] = {}
        lines = text.count('\n') + 1
        for node in tree.body:
            rel = os.path.relpath(path)
            if isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                           and not n.name.startswith('_')]
                method_lines = {n.name: n.lineno for n in node.body
                                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                units.append(Unit(name=node.name, file=os.path.basename(path),
                                  lines=(getattr(node, 'end_lineno', node.lineno) - node.lineno + 1),
                                  public=not node.name.startswith('_'), kind='class',
                                  summary=first_sentence(ast.get_docstring(node) or ''),
                                  api=methods, api_lines=method_lines, rel=rel))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith('_'):
                    continue
                units.append(Unit(name=node.name, file=os.path.basename(path),
                                  lines=(getattr(node, 'end_lineno', node.lineno) - node.lineno + 1),
                                  public=True, kind='function',
                                  summary=first_sentence(ast.get_docstring(node) or ''),
                                  api_lines={node.name: node.lineno}, rel=rel))
            elif isinstance(node, ast.ImportFrom) and node.module:
                head = node.module.split('.')[0]
                deps[head] = deps.get(head, 0) + 1
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    head = alias.name.split('.')[0]
                    deps[head] = deps.get(head, 0) + 1
        return Module(package=self.package_of('', path),
                      path=os.path.dirname(os.path.relpath(path)).replace(os.sep, '/'),
                      summary=module_doc, lines=lines, depends_on=deps, units=units)
