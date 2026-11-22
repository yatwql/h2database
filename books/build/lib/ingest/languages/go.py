#!/usr/bin/env python3
"""Go analyzer: packages from `package` clauses, exported types, `import` deps."""
from __future__ import annotations

import os
import re

from ingest.languages._base import Analyzer, Module, Unit, first_sentence
from lib import _fsutil

PACKAGE_RE = re.compile(r'^\s*package\s+(\w+)', re.MULTILINE)
IMPORT_BLOCK_RE = re.compile(r'^\s*import\s*\((.*?)\)', re.MULTILINE | re.DOTALL)
IMPORT_LINE_RE = re.compile(r'^\s*import\s+(?:\w+\s+)?"([^"]+)"', re.MULTILINE)
QUOTED_RE = re.compile(r'"([^"]+)"')
TYPE_RE = re.compile(r'^\s*type\s+(\w+)\s+(?:struct|interface)\b', re.MULTILINE)
FUNC_RE = re.compile(r'^\s*func\s+(?:\([^)]*\)\s*)?(\w+)', re.MULTILINE)
DOC_RE = re.compile(r'^((?://.*\n)+)', re.MULTILINE)


def _exported(name: str) -> bool:
    """Go's visibility rule: an upper-case first letter is exported."""
    return bool(name) and name[0].isupper()


def _imports(text: str) -> list[str]:
    found: list[str] = []
    for block in IMPORT_BLOCK_RE.findall(text):
        found += QUOTED_RE.findall(block)
    found += IMPORT_LINE_RE.findall(text)
    return found


class GoAnalyzer(Analyzer):
    """Digest a Go tree (one package per directory, exported units are public)."""

    name = 'go'
    suffixes = ('.go',)

    def package_of(self, root: str, path: str) -> str:
        match = PACKAGE_RE.search(_fsutil.read_text_raw(path))
        if match:
            directory = os.path.dirname(os.path.relpath(path, root)).replace(os.sep, '/')
            return f'{match.group(1)}' if not directory else f'{directory}'
        rel = os.path.dirname(os.path.relpath(path, root))
        return rel.replace(os.sep, '/') or 'root'

    def parse(self, path: str) -> Module:
        text = _fsutil.read_text_raw(path)
        lines = text.count('\n') + 1
        summary = ''
        doc = DOC_RE.search(text)
        if doc and not doc.group(1).lstrip().startswith('//go:'):
            summary = first_sentence(' '.join(
                line.strip().lstrip('/').strip() for line in doc.group(1).split('\n')))
        names = TYPE_RE.findall(text)
        api = FUNC_RE.findall(text)
        api_lines: dict[str, int] = {}
        for lineno, line in enumerate(text.split('\n'), start=1):
            match = FUNC_RE.match(line)
            if match:
                api_lines.setdefault(match.group(1), lineno)
        rel = os.path.relpath(path)
        units = [Unit(name=name, file=os.path.basename(path), lines=lines,
                      public=_exported(name), kind='type', summary=summary,
                      api=api, api_lines=api_lines, rel=rel)
                 for name in names]
        deps: dict[str, int] = {}
        for target in _imports(text):
            deps[target] = deps.get(target, 0) + 1
        return Module(package=self.package_of('', path),
                      path=os.path.dirname(os.path.relpath(path)).replace(os.sep, '/'),
                      summary=summary, lines=lines, depends_on=deps, units=units)
