#!/usr/bin/env python3
"""Detect drift between documentation and the repository's actual contents.

Four kinds of drift are reported:

  PATH     a back-ticked repository path mentioned in a document does not exist
  SCRIPT   a script listed in the docs is not present in the toolchain
  VERSION  document versions disagree with book.toml
  CHAPTER  the documented chapter list diverges from book.toml / manuscript

Exit 1 on any finding.

Usage:
  python doc_drift.py            # report
  python doc_drift.py --json
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

REPO_ROOT = os.path.normpath(os.path.join(_config.BOOK_ROOT, '..'))
PATH_RE = re.compile(r'`((?:books|h2|\.github)/[A-Za-z0-9_./*-]+)`')
SCRIPT_RE = re.compile(r'`([a-z_]+\.py)`')
VERSION_RE = re.compile(r'v?(\d+\.\d+)')


def doc_files() -> list[str]:
    files = glob.glob(os.path.join(_config.BOOK_ROOT, 'docs', '**', '*.md'), recursive=True)
    files.append(os.path.join(_config.BOOK_ROOT, 'README.md'))
    files.append(os.path.join(REPO_ROOT, 'CLAUDE.md'))
    return sorted({os.path.normpath(p) for p in files if os.path.isfile(p)})


def _exists(rel: str) -> bool:
    if '*' in rel:
        return bool(glob.glob(os.path.join(REPO_ROOT, rel), recursive=True))
    return os.path.exists(os.path.join(REPO_ROOT, rel))


def check_paths(files: list[str]) -> list[dict]:
    out = []
    for path in files:
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            for match in PATH_RE.finditer(line):
                target = match.group(1)
                if '...' in target or '…' in target or '<' in target:
                    continue  # illustrative path
                if not _exists(target):
                    out.append({'kind': 'PATH', 'file': os.path.relpath(path, REPO_ROOT),
                                'line': lineno, 'detail': target})
    return out


def check_scripts(files: list[str]) -> list[dict]:
    available = {os.path.basename(p) for p in
                 glob.glob(os.path.join(_config.BOOK_ROOT, 'src', 'python', '**', '*.py'),
                           recursive=True)}
    out = []
    for path in files:
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            for match in SCRIPT_RE.finditer(line):
                name = match.group(1)
                if name not in available:
                    out.append({'kind': 'SCRIPT', 'file': os.path.relpath(path, REPO_ROOT),
                                'line': lineno, 'detail': name})
    return out


def check_versions(files: list[str]) -> list[dict]:
    expected = _config.VERSION
    out = []
    for path in files:
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            # only the document header line carries the document version
            if not re.match(r'^\s*>?\s*版本\s*[:：]', line):
                continue
            match = VERSION_RE.search(line)
            if match and match.group(1) != expected:
                out.append({'kind': 'VERSION', 'file': os.path.relpath(path, REPO_ROOT),
                            'line': lineno,
                            'detail': f'{match.group(1)} != {expected}'})
    return out


def check_chapters(files: list[str]) -> list[dict]:
    configured = set(_config.chapter_names())
    actual = {os.path.basename(p) for p in
              glob.glob(os.path.join(_config.MANUSCRIPT_DIR, '*.md'))}
    out = []
    for path in files:
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            for name in re.findall(r'`(ch\d[\w-]*\.md|appendix-[\w-]+\.md|cover\.md)`', line):
                if name not in configured or name not in actual:
                    out.append({'kind': 'CHAPTER', 'file': os.path.relpath(path, REPO_ROOT),
                                'line': lineno, 'detail': name})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    files = doc_files()
    findings = check_paths(files) + check_scripts(files) + check_versions(files) + check_chapters(files)

    if args.json:
        print(json.dumps({'count': len(findings), 'findings': findings},
                         ensure_ascii=False, indent=2))
        return 0 if not findings else 1

    if not findings:
        print('✅ 文档与仓库一致（无漂移）')
        return 0
    print(f'文档漂移 {len(findings)} 处：')
    for item in findings[:40]:
        print(f"  {item['file']}:{item['line']}  [{item['kind']}] {item['detail']}")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
