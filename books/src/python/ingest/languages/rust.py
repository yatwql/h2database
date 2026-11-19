#!/usr/bin/env python3
"""Rust analyzer: modules from files, `pub` items, `use crate::…` dependencies."""
from __future__ import annotations

import os
import re

from ingest.languages._base import Analyzer, Module, Unit, first_sentence
from lib import _fsutil

ITEM_RE = re.compile(r'^\s*pub(?:\([^)]*\))?\s+(?:struct|enum|trait|union)\s+(\w+)', re.MULTILINE)
ANY_ITEM_RE = re.compile(r'^\s*(?:struct|enum|trait|union)\s+(\w+)', re.MULTILINE)
FN_RE = re.compile(r'^\s*pub(?:\([^)]*\))?\s+(?:async\s+)?fn\s+(\w+)', re.MULTILINE)
USE_RE = re.compile(r'^\s*use\s+(?:crate|super|self)::(\w+)', re.MULTILINE)
DOC_RE = re.compile(r'^((?:///.*\n)+)', re.MULTILINE)


class RustAnalyzer(Analyzer):
    """Digest a Rust tree (modules from directories, units from item headers)."""

    name = 'rust'
    suffixes = ('.rs',)

    def package_of(self, root: str, path: str) -> str:
        rel = os.path.dirname(os.path.relpath(path, root))
        return rel.replace(os.sep, '::') or 'root'

    def parse(self, path: str) -> Module:
        text = _fsutil.read_text_raw(path)
        lines = text.count('\n') + 1
        summary = ''
        doc = DOC_RE.search(text)
        if doc:
            summary = first_sentence(' '.join(
                line.strip().lstrip('/').strip() for line in doc.group(1).split('\n')))
        names = ITEM_RE.findall(text) or ANY_ITEM_RE.findall(text)
        api = FN_RE.findall(text)
        api_lines: dict[str, int] = {}
        for lineno, line in enumerate(text.split('\n'), start=1):
            match = FN_RE.match(line)
            if match:
                api_lines.setdefault(match.group(1), lineno)
        rel = os.path.relpath(path)
        units = [Unit(name=name, file=os.path.basename(path), lines=lines,
                      public=bool(ITEM_RE.findall(text)), kind='item',
                      summary=summary, api=api, api_lines=api_lines, rel=rel)
                 for name in names[:1]]
        deps: dict[str, int] = {}
        for target in USE_RE.findall(text):
            deps[target] = deps.get(target, 0) + 1
        return Module(package=self.package_of('', path),
                      path=os.path.dirname(os.path.relpath(path)).replace(os.sep, '/'),
                      summary=summary, lines=lines, depends_on=deps, units=units)
