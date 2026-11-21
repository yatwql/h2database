#!/usr/bin/env python3
"""Kotlin analyzer: packages from `package` lines, public types, `import` deps."""
from __future__ import annotations

import os
import re

from ingest.languages._base import Analyzer, Module, Unit, first_sentence
from lib import _fsutil

PACKAGE_RE = re.compile(r'^\s*package\s+([\w.]+)', re.MULTILINE)
IMPORT_RE = re.compile(r'^\s*import\s+([\w.]+)', re.MULTILINE)
TYPE_RE = re.compile(r'^\s*(?:public\s+|internal\s+|private\s+)?'
                     r'(?:data\s+|sealed\s+|abstract\s+|open\s+|inner\s+)*'
                     r'(?:class|interface|object|enum\s+class|annotation\s+class)\s+(\w+)',
                     re.MULTILINE)
PUBLIC_TYPE_RE = re.compile(r'^\s*(?:public\s+|(?!private\b|internal\b))'
                            r'(?:data\s+|sealed\s+|abstract\s+|open\s+)*'
                            r'(?:class|interface|object|enum\s+class)\s+(\w+)',
                            re.MULTILINE)
FUN_RE = re.compile(r'^\s*(?:public\s+|internal\s+)?fun\s+(?:<[^>]+>\s*)?(\w+)',
                    re.MULTILINE)
DOC_RE = re.compile(r'/\*\*(.*?)\*/', re.DOTALL)
LINE_DOC_RE = re.compile(r'^((?:\s*///.*\n)+)', re.MULTILINE)


class KotlinAnalyzer(Analyzer):
    """Digest a Kotlin tree (packages from `package`, units from type headers)."""

    name = 'kotlin'
    suffixes = ('.kt', '.kts')

    def package_of(self, root: str, path: str) -> str:
        match = PACKAGE_RE.search(_fsutil.read_text_raw(path))
        if match:
            return match.group(1)
        rel = os.path.dirname(os.path.relpath(path, root))
        return rel.replace(os.sep, '.') or 'root'

    def parse(self, path: str) -> Module:
        text = _fsutil.read_text_raw(path)
        lines = text.count('\n') + 1
        summary = ''
        doc = DOC_RE.search(text) or LINE_DOC_RE.search(text)
        if doc:
            summary = first_sentence(' '.join(
                line.strip().lstrip('/*').lstrip('/').strip()
                for line in doc.group(1).split('\n')))
        names = TYPE_RE.findall(text)
        public = set(PUBLIC_TYPE_RE.findall(text))
        api = FUN_RE.findall(text)
        api_lines: dict[str, int] = {}
        for lineno, line in enumerate(text.split('\n'), start=1):
            match = FUN_RE.match(line)
            if match:
                api_lines.setdefault(match.group(1), lineno)
        rel = os.path.relpath(path)
        units = [Unit(name=name, file=os.path.basename(path), lines=lines,
                      public=name in public, kind='type', summary=summary,
                      api=api, api_lines=api_lines, rel=rel)
                 for name in names[:1]]
        deps: dict[str, int] = {}
        for target in IMPORT_RE.findall(text):
            package = target.rsplit('.', 1)[0]
            deps[package] = deps.get(package, 0) + 1
        return Module(package=self.package_of('', path),
                      path=os.path.dirname(os.path.relpath(path)).replace(os.sep, '/'),
                      summary=summary, lines=lines, depends_on=deps, units=units)
