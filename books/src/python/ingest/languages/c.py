#!/usr/bin/env python3
"""C analyzer: packages from directories, units from headers, quoted includes.

C has no package declaration, so the package is the directory the file lives in
(relative to the analyzed root, `.`-joined). A header and its same-named `.c`
share one package by construction. Visibility is C's own rule, spelled out:
what the headers declare is public, what only the `.c` defines is not.

Only quoted includes (`#include "x.h"`) become dependencies; angle-bracket
includes name system headers and are dropped. Include targets are resolved
relative to the including file first, then relative to the root, so a project
that keeps `include/` beside `src/` still resolves both ways.
"""

from __future__ import annotations

import os
import re

from ingest.languages._base import Analyzer, Module, Unit, first_sentence
from lib import _fsutil

INCLUDE_RE = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.MULTILINE)
BLOCK_DOC_RE = re.compile(r"/\*(.*?)\*/", re.DOTALL)
LINE_DOC_RE = re.compile(r"^((?:\s*//.*\n)+)", re.MULTILINE)
# `struct Foo {`, `union Bar {`, `enum Baz {` — the definition, not typedef aliases.
TAGGED_TYPE_RE = re.compile(r"^\s*(struct|union|enum)\s+(\w+)\s*\{", re.MULTILINE)
# `typedef struct {...} Foo;` / `typedef enum {...} Bar;` — the alias is the name.
TYPEDEF_ALIAS_RE = re.compile(
    r"^\s*typedef\b(?:[^;{}]*\{[^}]*\})?[^;{}]*?\b(\w+)\s*;", re.MULTILINE | re.DOTALL
)
# A function prototype: `int foo(const char *bar);` — ends with `;`, has a `(`.
PROTOTYPE_RE = re.compile(
    r"^\s*(?!typedef\b|return\b|if\b|for\b|while\b|switch\b|else\b|sizeof\b)"
    r"(?:[A-Za-z_]\w*[\s\*]+)+([A-Za-z_]\w*)\s*\(([^;{)]*)\)\s*;",
    re.MULTILINE,
)
KIND_BY_TAG = {"struct": "struct", "union": "union", "enum": "enum"}


def _doc_summary(text: str) -> str:
    """First sentence of the file's leading comment block, if it has one."""
    for pattern in (BLOCK_DOC_RE, LINE_DOC_RE):
        match = pattern.search(text)
        if not match:
            continue
        body = match.group(1)
        body = " ".join(line.strip().lstrip("/*").lstrip("/").strip() for line in body.split("\n"))
        summary = first_sentence(body)
        if summary:
            return summary
    return ""


def _type_names(text: str) -> list[tuple[str, str]]:
    """(name, kind) for every type the file defines, in source order."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for tag, name in TAGGED_TYPE_RE.findall(text):
        if name not in seen:
            seen.add(name)
            found.append((name, KIND_BY_TAG.get(tag, "struct")))
    for name in TYPEDEF_ALIAS_RE.findall(text):
        if name not in seen and name not in ("struct", "union", "enum"):
            seen.add(name)
            found.append((name, "typedef"))
    return found


def _prototypes(text: str) -> dict[str, int]:
    """Declared function name → 1-based line of its prototype."""
    out: dict[str, int] = {}
    for lineno, line in enumerate(text.split("\n"), start=1):
        match = PROTOTYPE_RE.match(line)
        if match:
            out.setdefault(match.group(1), lineno)
    return out


class CAnalyzer(Analyzer):
    """Digest a C tree (one package per directory, header declarations public)."""

    name = "c"
    suffixes = (".c", ".h")

    def package_of(self, root: str, path: str) -> str:
        rel = os.path.dirname(os.path.relpath(path, root))
        return rel.replace(os.sep, ".") or "root"

    def header_surface(self, root: str) -> dict[str, tuple[set[str], dict[str, int]]]:
        """Per package: the names its headers declare, and their prototype lines.

        Public in C means "the header says so": a `.c` may define helpers the
        module keeps to itself, and the inventory must not present them as API.
        """
        surface: dict[str, tuple[set[str], dict[str, int]]] = {}
        for path in self.discover(root):
            if not path.endswith(".h"):
                continue
            text = _fsutil.read_text_raw(path)
            names, prototypes = surface.setdefault(self.package_of(root, path), (set(), {}))
            names.update(name for name, _kind in _type_names(text))
            prototypes.update(_prototypes(text))
        return surface

    def parse(self, path: str) -> Module:
        """One file on its own: units, prototypes and includes, unclassified."""
        text = _fsutil.read_text_raw(path)
        lines = text.count("\n") + 1
        summary = _doc_summary(text)
        header = path.endswith(".h")
        units = [
            Unit(
                name=name,
                file=os.path.basename(path),
                lines=lines,
                public=header,
                kind=kind,
                summary=summary,
                api=[],
                api_lines={},
                rel=os.path.relpath(path),
            )
            for name, kind in _type_names(text)
        ]
        deps: dict[str, int] = {}
        for target in INCLUDE_RE.findall(text):
            deps[target] = deps.get(target, 0) + 1
        return Module(
            package=self.package_of("", path),
            path=os.path.dirname(os.path.relpath(path)).replace(os.sep, "/"),
            summary=summary,
            lines=lines,
            depends_on=deps,
            units=units,
        )

    def include_package(self, root: str, path: str, target: str) -> str | None:
        """The package a quoted include points at, or None when it is not in the tree."""
        for base in (os.path.dirname(path), root):
            candidate = os.path.normpath(os.path.join(base, target))
            if os.path.isfile(candidate):
                return self.package_of(root, candidate)
        return None

    def analyze(self, root: str) -> dict:
        """Digest the tree, resolving includes and public surfaces across files."""
        surface = self.header_surface(root)
        modules: dict[str, Module] = {}
        for path in self.discover(root):
            package = self.package_of(root, path)
            fragment = self.parse(path)
            target = modules.setdefault(package, Module(package=package, path=fragment.path))
            target.summary = target.summary or fragment.summary
            target.files += 1
            target.lines += fragment.lines
            names, prototypes = surface.get(package, (set(), {}))
            declared = path.endswith(".h")
            text = _fsutil.read_text_raw(path) if declared else ""
            api = _prototypes(text) if declared else {}
            for unit in fragment.units:
                unit.public = declared or unit.name in names
                if unit.public and api:
                    unit.api = sorted(api)
                    unit.api_lines = dict(sorted(api.items()))
                target.units.append(unit)
            if declared and prototypes and not target.units:
                # a header with prototypes but no types still exposes an API
                target.units.append(
                    Unit(
                        name=os.path.splitext(os.path.basename(path))[0],
                        file=os.path.basename(path),
                        lines=fragment.lines,
                        public=True,
                        kind="header",
                        summary=fragment.summary,
                        api=sorted(api),
                        api_lines=dict(sorted(api.items())),
                        rel=os.path.relpath(path),
                    )
                )
            for include in INCLUDE_RE.findall(_fsutil.read_text_raw(path)):
                dep = self.include_package(root, path, include)
                if dep and dep != package:
                    target.depends_on[dep] = target.depends_on.get(dep, 0) + 1
        return {
            "root": os.path.abspath(root),
            "language": self.name,
            "totals": {
                "packages": len(modules),
                "files": sum(m.files for m in modules.values()),
                "lines": sum(m.lines for m in modules.values()),
            },
            "packages": {name: module.as_dict() for name, module in sorted(modules.items())},
        }
