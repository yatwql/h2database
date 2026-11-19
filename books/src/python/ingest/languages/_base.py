#!/usr/bin/env python3
"""Language-agnostic contract for source digests.

An analyzer turns one source tree into the inventory shape the rest of the
pipeline consumes:

    {package/module: {path, summary, files, lines, depends_on,
                      classes: [{name, file, lines, public, kind, summary,
                                 public_methods, api}]}}

Analyzers only read the tree; parsing is per language and never shared.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

FIRST_SENTENCE = re.compile(r'(?<=[.!?])\s+')


def first_sentence(text: str, limit: int = 220) -> str:
    """First sentence of a doc comment, whitespace-normalised."""
    body = ' '.join(text.split())
    if not body:
        return ''
    return FIRST_SENTENCE.split(body)[0][:limit]


@dataclass
class Unit:
    """One declared type (class / struct / trait / enum)."""

    name: str
    file: str
    lines: int
    public: bool
    kind: str
    summary: str = ''
    api: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            'name': self.name, 'file': self.file, 'lines': self.lines,
            'public': self.public, 'kind': self.kind, 'summary': self.summary,
            'public_methods': len(self.api), 'api': sorted(set(self.api))[:24],
        }


@dataclass
class Module:
    """One package (Java) or module directory (Python/Rust)."""

    package: str
    path: str
    summary: str = ''
    files: int = 0
    lines: int = 0
    depends_on: dict[str, int] = field(default_factory=dict)
    units: list[Unit] = field(default_factory=list)

    def as_dict(self) -> dict:
        units = [u.as_dict() for u in sorted(self.units, key=lambda u: -u.lines)]
        return {
            'path': self.path, 'summary': self.summary, 'files': self.files,
            'lines': self.lines, 'depends_on': dict(sorted(self.depends_on.items(),
                                                            key=lambda kv: -kv[1])[:8]),
            'classes': units,
            'public_classes': [u['name'] for u in units if u['public']],
        }


class Analyzer:
    """Base analyzer: subclasses implement the language-specific hooks."""

    name = 'base'
    suffixes: tuple[str, ...] = ()

    def package_of(self, root: str, path: str) -> str:
        """Package/module name for a file (default: its directory path)."""
        rel = os.path.dirname(os.path.relpath(path, root))
        return rel.replace(os.sep, '.') or 'root'

    def parse(self, path: str) -> Module:
        """Parse one file into a Module fragment."""
        raise NotImplementedError

    def analyze(self, root: str) -> dict:
        """Digest the whole tree into the inventory structure."""
        modules: dict[str, Module] = {}
        for path in self.discover(root):
            fragment = self.parse(path)
            # the package/module name is resolved against the analyzed root
            key = self.package_of(root, path) or fragment.package
            target = modules.setdefault(key, Module(package=key, path=fragment.path))
            target.summary = target.summary or fragment.summary
            target.files += 1
            target.lines += fragment.lines
            target.units.extend(fragment.units)
            for dep, count in fragment.depends_on.items():
                if dep != key:
                    target.depends_on[dep] = target.depends_on.get(dep, 0) + count
        return {
            'root': os.path.abspath(root),
            'language': self.name,
            'totals': {'packages': len(modules),
                       'files': sum(m.files for m in modules.values()),
                       'lines': sum(m.lines for m in modules.values())},
            'packages': {name: module.as_dict() for name, module in sorted(modules.items())},
        }

    def discover(self, root: str) -> list[str]:
        """Every source file under ``root`` with a recognised suffix."""
        found: list[str] = []
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                if name.endswith(self.suffixes):
                    found.append(os.path.join(dirpath, name))
        return sorted(found)
