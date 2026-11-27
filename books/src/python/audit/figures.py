#!/usr/bin/env python3
"""Audit figure caption format and inline citations.

Reports:
  * total figures and inline citations (如图 X-Y 所示)
  * figures that are never cited from the prose
  * citations that point at a figure that does not exist

Exit codes: 0 clean, 1 uncited figures or dangling citations found.
"""

from __future__ import annotations

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import json
import os
import re
import sys

from lib import _config, _errors, _fsutil, _mdutil

FIG_RE = re.compile(rf'\*\*{_mdutil.FIGURE_LABEL} ({_mdutil.FIGURE_ID}):')
CITATION_RE = re.compile(rf'如图 ({_mdutil.FIGURE_ID}) 所示')

def chapter_files() -> list[str]:
    """Chapter files the book declares, in reading order (`book.toml [chapters]`)."""
    return _config.chapter_files(include_cover=False)

def audit(files: list[str]) -> dict:
    """Return figure/citation counts and the problems per file."""
    total_figs = 0
    total_citations = 0
    uncited_files: list[tuple[str, list[str]]] = []
    dangling_files: list[tuple[str, list[str]]] = []
    for path in files:
        content = _fsutil.read_text(path)
        figures = FIG_RE.findall(content)
        citations = CITATION_RE.findall(content)
        total_figs += len(figures)
        total_citations += len(citations)
        name = os.path.basename(path)
        uncited = sorted(set(figures) - set(citations))
        if uncited:
            uncited_files.append((name, uncited[:8]))
        dangling = sorted(set(citations) - set(figures))
        if dangling:
            dangling_files.append((name, dangling[:8]))
    return {
        'total_figures': total_figs,
        'total_citations': total_citations,
        'uncited': uncited_files,
        'dangling': dangling_files,
    }

def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv else list(sys.argv[1:])
    strict = '--strict' in args
    result = audit(chapter_files())
    if '--json' in args:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        problems = bool(result['uncited'] or result['dangling'])
        return 1 if (problems and strict) else 0
    print(f"Total figures: {result['total_figures']}")
    print(f"Total inline citations (如图 X-Y 所示): {result['total_citations']}")
    print(f"Files with uncited figures: {len(result['uncited'])}")
    for fname, uncited in result['uncited']:
        print(f'  {fname}: {len(uncited)} uncited - {uncited}')
    for fname, dangling in result['dangling']:
        print(f'  {fname}: dangling citations - {dangling}')
    problems = bool(result['uncited'] or result['dangling'])
    if problems and not strict:
        print('  (advisory: pass --strict to fail on these)')
        return 0
    return 1 if problems else 0

if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
