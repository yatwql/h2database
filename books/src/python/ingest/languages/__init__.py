"""Language analyzers: one module per supported source language.

Registry contract: every analyzer exposes ``name``, ``suffixes`` and
``analyze(root) -> inventory``. Adding a language means adding one module and
one registry entry; nothing else in the pipeline changes.
"""
from __future__ import annotations

import os

from ingest.languages._base import Analyzer, Module, Unit  # noqa: F401
from ingest.languages.java import JavaAnalyzer
from ingest.languages.python import PythonAnalyzer
from ingest.languages.rust import RustAnalyzer

ANALYZERS: dict[str, type[Analyzer]] = {
    'java': JavaAnalyzer,
    'python': PythonAnalyzer,
    'rust': RustAnalyzer,
}


def get(name: str) -> Analyzer:
    """Instantiate an analyzer by language name."""
    try:
        return ANALYZERS[name]()
    except KeyError as exc:
        raise SystemExit(f'error: unsupported language {name!r}; '
                         f'known: {", ".join(sorted(ANALYZERS))}') from exc


def detect(root: str) -> str:
    """Guess the language of ``root`` from the file suffixes it contains."""
    suffixes = {'.java': 'java', '.py': 'python', '.rs': 'rust'}
    counts: dict[str, int] = {}
    for _dirpath, _dirs, files in os.walk(root):
        for name in files:
            language = suffixes.get(os.path.splitext(name)[1])
            if language:
                counts[language] = counts.get(language, 0) + 1
    if not counts:
        raise SystemExit(f'error: no known source files under {root}')
    return max(counts, key=lambda key: counts[key])
