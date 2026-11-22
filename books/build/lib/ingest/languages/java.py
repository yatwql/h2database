#!/usr/bin/env python3
"""Java analyzer: package structure, Javadoc summaries, public API surface."""
from __future__ import annotations

import os
import re

from ingest.languages._base import Analyzer, Module, Unit, first_sentence
from lib import _fsutil

PACKAGE_RE = re.compile(r'^\s*package\s+([\w.]+)\s*;', re.MULTILINE)
IMPORT_RE = re.compile(r'^\s*import\s+(?:static\s+)?(org\.h2\.[\w.]+?)(?:\.\w+)?\s*;', re.MULTILINE)
TYPE_RE = re.compile(r'^\s*public\s+(?:final\s+|abstract\s+|sealed\s+|non-sealed\s+)*'
                     r'(?:class|interface|enum|record)\s+(\w+)', re.MULTILINE)
ANY_TYPE_RE = re.compile(r'^\s*(?:public\s+)?(?:final\s+|abstract\s+)*'
                         r'(?:class|interface|enum|record)\s+(\w+)', re.MULTILINE)
METHOD_RE = re.compile(r'^\s*public\s+(?:static\s+|final\s+|synchronized\s+|native\s+|'
                       r'default\s+|abstract\s+)*[\w<>\[\],.?\s]+\s+(\w+)\s*\(', re.MULTILINE)
DOC_RE = re.compile(r'/\*\*([\s\S]*?)\*/\s*$')
TAG_RE = re.compile(r'<[^>]+>')


class JavaAnalyzer(Analyzer):
    """Digest a Java tree (packages from the package declaration)."""

    name = 'java'
    suffixes = ('.java',)

    def package_of(self, root: str, path: str) -> str:
        text = _fsutil.read_text_raw(path)
        match = PACKAGE_RE.search(text)
        return match.group(1) if match else 'default'

    def parse(self, path: str) -> Module:
        text = _fsutil.read_text_raw(path)
        package = self.package_of('', path)
        lines = text.count('\n') + 1
        summary = ''
        doc = DOC_RE.search(text)
        if doc:
            summary = first_sentence(TAG_RE.sub(' ', doc.group(1)).replace('*', ' '))
        names = TYPE_RE.findall(text) or ANY_TYPE_RE.findall(text)
        api = METHOD_RE.findall(text)
        api_lines: dict[str, int] = {}
        for lineno, line in enumerate(text.split('\n'), start=1):
            match = METHOD_RE.match(line)
            if match:
                api_lines.setdefault(match.group(1), lineno)
        rel = os.path.relpath(path)
        units = [Unit(name=name, file=os.path.basename(path), lines=lines,
                      public=bool(TYPE_RE.findall(text)), kind='type',
                      summary=summary, api=api, api_lines=api_lines, rel=rel)
                 for name in names[:1]]
        deps: dict[str, int] = {}
        for target in IMPORT_RE.findall(text):
            parent = target.rsplit('.', 1)[0]
            deps[parent] = deps.get(parent, 0) + 1
        return Module(package=package, path=os.path.dirname(os.path.relpath(path)).replace(os.sep, '/'),
                      summary=summary, lines=lines, depends_on=deps, units=units)
