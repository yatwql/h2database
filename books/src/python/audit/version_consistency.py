#!/usr/bin/env python3
"""Keep the three versions coherent: tool, analyzed source, document.

  TOOL    lib/_version.py (or base.json [sources].tool_version) — semver
  SOURCE  base.json [sources].version or the source manifest (pom/pyproject/Cargo)
  DOC     book.toml [book].version — also written into management doc headers

Checks
  VERSION   tool/doc resolve and are non-empty; source resolves (warning if not)
  DOC_HEAD  management documents declaring "> 版本：vX" match the doc version
  MANIFEST  the merged Markdown manifest line matches the current trio

Usage:
  python version_consistency.py
  python version_consistency.py --json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

DOC_HEAD_RE = re.compile(r'^\s*>?\s*版本\s*[:：]\s*v?([\d.]+)', re.MULTILINE)
MANIFEST_RE = re.compile(r'<!-- versions: tool=(\S+) source=(\S+) doc=(\S+) -->')


def doc_headers() -> list[dict]:
    """Management documents that declare a version header."""
    findings = []
    for path in glob.glob(os.path.join(_config.DOCS_DIR, '**', '*.md'), recursive=True):
        match = DOC_HEAD_RE.search(_fsutil.read_text(path))
        if match:
            findings.append({'file': os.path.relpath(path, _config.BOOK_ROOT),
                             'version': match.group(1)})
    return findings


def merged_manifest() -> tuple[str, str, str] | None:
    path = _config.merged_md()
    if not os.path.isfile(path):
        return None
    match = MANIFEST_RE.search(_fsutil.read_text(path)[:4096])
    return (match.group(1), match.group(2), match.group(3)) if match else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    versions = _config.versions()
    problems: list[str] = []
    warnings: list[str] = []

    for name in ('tool', 'doc'):
        if not versions.get(name) or versions[name] == 'unknown':
            problems.append(f'{name} version is not set')
    if versions.get('source') in (None, '', 'unknown'):
        warnings.append('source version could not be determined (set [sources].version)')

    for header in doc_headers():
        if header['version'] != versions['doc']:
            problems.append(f"{header['file']}: header v{header['version']} != "
                            f"doc version v{versions['doc']}")

    manifest = merged_manifest()
    if manifest:
        # the analysed source is external input: when its version cannot be
        # determined, compare only the components the book owns
        expected = (versions['tool'], versions['source'], versions['doc'])
        known = [index for index, value in enumerate(expected)
                 if value and value != 'unknown']
        mismatch = [index for index in known if manifest[index] != expected[index]]
        if mismatch:
            problems.append(f'merged Markdown manifest {manifest} != '
                            f"{tuple(expected)}")

    if args.json:
        print(json.dumps({'versions': versions, 'problems': problems,
                          'warnings': warnings}, ensure_ascii=False, indent=2))
        return 0 if not problems else 1

    print(f"tool {versions['tool']} | source {versions['source']} | doc {versions['doc']}")
    for warning in warnings:
        print(f'  warn  {warning}')
    if problems:
        print(f'版本不一致 {len(problems)} 处：')
        for problem in problems:
            print(f'  - {problem}')
        return 1
    print('✅ 三个版本一致')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
