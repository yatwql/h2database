#!/usr/bin/env python3
"""Detect drift between documentation, configuration and the repository.

Each fact is declared once and must point at something real:

  PATH     a back-ticked repository path mentioned in a document does not exist
  SCRIPT   a script listed in the docs is not present in the toolchain
  CHAPTER  a chapter file name mentioned in a document is not a manuscript file
  CONFIG   a book.toml table names a chapter the chapter list does not carry
  LEVEL    a gate level is declared outside the testplan tables that own it

Version agreement is not checked here: `version_consistency` owns it.

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
PATH_RE = re.compile(r'`((?:books|h2|\.github|src|scripts|data|docs)/[A-Za-z0-9_./*-]+)`')
SCRIPT_RE = re.compile(r'`([a-z_]+\.py)`')
CHAPTER_RE = re.compile(r'(?<![\w/-])((?:ch\d[\w-]*|appendix-[\w-]+|cover)\.md)')
LEVEL_RE = re.compile(r'^\**P[0-3]\**$')
# files whose job is to record what changed may name files that no longer exist
LEDGER_DOCS = ('changelog.md', 'review-findings.md')
# testplan headings that own the gate-level axis; everywhere else the level is
# repeated, and a repeated level drifts from the one that is checked
LEVEL_SECTIONS = ('2.1', '2.2')
CHAPTER_TABLES = ('packages', 'titles', 'numbering', 'coverage')
MANAGEMENTS = os.path.join('docs', 'managements')


def doc_files() -> list[str]:
    files = glob.glob(os.path.join(_config.BOOK_ROOT, 'docs', '**', '*.md'), recursive=True)
    files.append(os.path.join(_config.BOOK_ROOT, 'README.md'))
    files.append(os.path.join(REPO_ROOT, 'CLAUDE.md'))
    return sorted({os.path.normpath(p) for p in files if os.path.isfile(p)})


def _repo_root(explicit: str | None = None) -> str:
    return explicit or REPO_ROOT


def _generated_prefixes() -> tuple[str, ...]:
    """Repository-relative prefixes of paths that exist only after setup/run.

    Books are built (`dist/`), set up (`.venv/`) and produce logs
    (`logs/`); none of those are in a fresh checkout, yet documentation may
    legitimately point at them.
    """
    repo = os.path.dirname(_config.BOOK_ROOT)
    logging_cfg = _config.POLICY.get('logging') or {}
    candidates = (
        _config.DIST_DIR,
        os.path.join(_config.BOOK_ROOT, '.venv'),
        os.path.join(_config.BOOK_ROOT, logging_cfg.get('dir', 'logs')),
    )
    prefixes = []
    for path in candidates:
        rel = os.path.relpath(path, repo).replace(os.sep, '/').rstrip('/')
        prefixes.append(rel + '/')
    return tuple(prefixes)


def _exists(rel: str, repo_root: str | None = None) -> bool:
    # generated / runtime paths are absent from a fresh checkout; a reference may
    # name the directory itself (`books/.venv`) or something inside it
    for prefix in _generated_prefixes():
        if rel == prefix.rstrip('/') or rel.startswith(prefix):
            return True
    # paths inside the tool's own book resolve from books/, the rest from the repo
    book_relative = rel.split('/', 1)[0] in ('src', 'scripts', 'data', 'docs')
    root = _config.BOOK_ROOT if book_relative else _repo_root(repo_root)
    if '*' in rel:
        return bool(glob.glob(os.path.join(root, rel), recursive=True))
    return os.path.exists(os.path.join(root, rel))


DIMENSION_RE = re.compile(r'^>\s*维度：\**(.+?)\**\s*$', re.MULTILINE)
MANAGEMENTS_REF_RE = re.compile(r'(?:\.\./managements/|managements/)[\w-]+\.md')
# a management document is registered either as an index-table row or as a line in
# the directory tree that folder.md owns; both surfaces must name the same set
INDEX_ROW_RE = re.compile(r'^\|\s*`([\w-]+\.md)`\s*\|')
TREE_ROW_RE = re.compile(r'^\s{2,}([\w-]+\.md)\s+#')
# the two ledgers number their entries and publish the next free number
NEXT_RE = re.compile(r'\b(plan|rf)-next\s*=\s*(\d+)')
ENTRY_RE = re.compile(r'\b(plan|rf)-(\d+)\b')


def management_files(managements_dir: str | None = None) -> list[str]:
    directory = managements_dir or os.path.join(_config.BOOK_ROOT, 'docs', 'managements')
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(directory, '*.md')))


def _registered(path: str, pattern: re.Pattern) -> tuple[list[str], list[dict]]:
    """Registered names, plus a finding for every name registered twice."""
    names: list[str] = []
    out: list[dict] = []
    for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
        match = pattern.match(line)
        if match is None:
            continue
        name = match.group(1)
        if name in names:
            out.append({'kind': 'INDEX', 'file': os.path.relpath(path, REPO_ROOT),
                        'line': lineno, 'detail': f'{name} registered twice'})
            continue
        names.append(name)
    return names, out


def _surface_findings(label: str, path: str, registered: list[str],
                      actual: list[str], out: list[dict]) -> None:
    rel = os.path.relpath(path, REPO_ROOT)
    for name in registered:
        if name not in actual:
            out.append({'kind': 'INDEX', 'file': rel, 'line': 1,
                        'detail': f'{label} names {name}, which does not exist'})
    for name in actual:
        if name not in registered:
            out.append({'kind': 'INDEX', 'file': rel, 'line': 1,
                        'detail': f'{label} does not register {name}'})


def check_managements(directory: str | None = None) -> list[dict]:
    """The management directory and its two registries name the same set.

    Two surfaces claim to describe the same directory: the index table in
    README.md and the tree in folder.md. Neither used to be compared with the
    directory itself, so a document could exist unlisted, be listed twice, or
    stay listed after it was gone.
    """
    base = directory or os.path.join(_config.BOOK_ROOT, 'docs', 'managements')
    actual = management_files(base)
    out: list[dict] = []
    for label, filename in (('index', 'README.md'), ('tree', 'folder.md')):
        path = os.path.join(base, filename)
        if not os.path.isfile(path):
            continue
        pattern = INDEX_ROW_RE if label == 'index' else TREE_ROW_RE
        registered, duplicate_rows = _registered(path, pattern)
        out += duplicate_rows
        _surface_findings(f'{filename} {label}', path, registered, actual, out)
    return out


def check_numbering(files: list[str] | None = None) -> list[dict]:
    """The published next-entry number is really the next one.

    A marker that falls behind hands out a number already used; one that runs
    ahead leaves a gap the ledger cannot explain. Both are silent until a
    reference collides.
    """
    docs = files or doc_files()
    used: dict[str, int] = {'plan': 0, 'rf': 0}
    markers: list[tuple[str, int, str, int]] = []
    for path in docs:
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            for family, value in NEXT_RE.findall(line):
                markers.append((family, int(value), path, lineno))
                continue
            for family, value in ENTRY_RE.findall(line):
                used[family] = max(used[family], int(value))
    out = []
    for family, value, path, lineno in markers:
        expected = used[family] + 1
        if value != expected:
            out.append({'kind': 'NUMBERING', 'file': os.path.relpath(path, REPO_ROOT),
                        'line': lineno,
                        'detail': f'{family}-next = {value}, expected {expected} '
                                  f'(max used {used[family]})'})
    return out


def check_manual_scope(manual_dir: str | None = None) -> list[dict]:
    """User documents state their dimension once, and do not quote the design.

    A manual answers "how do I use this"; each one owns a single dimension so two
    manuals cannot drift into covering the same ground, and none of them leans on
    the requirements or the design documents to explain itself.
    """
    directory = manual_dir or os.path.join(_config.BOOK_ROOT, 'docs', 'manuals')
    out: list[dict] = []
    seen: dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(directory, '*.md'))):
        rel = os.path.relpath(path, REPO_ROOT)
        text = _fsutil.read_text(path)
        match = DIMENSION_RE.search(text)
        if match is None:
            out.append({'kind': 'SCOPE', 'file': rel, 'line': 1,
                        'detail': 'manuals must declare "> 维度：" '})
            continue
        dimension = match.group(1).strip()
        if dimension in seen:
            out.append({'kind': 'SCOPE', 'file': rel, 'line': 1,
                        'detail': f'dimension duplicates {seen[dimension]}'})
        else:
            seen[dimension] = rel
        for lineno, line in enumerate(text.split('\n'), start=1):
            for ref in MANAGEMENTS_REF_RE.finditer(line):
                out.append({'kind': 'SCOPE', 'file': rel, 'line': lineno,
                            'detail': f'user document refers to the design docs: {ref.group(0)}'})
    return out


def check_paths(files: list[str], repo_root: str | None = None) -> list[dict]:
    out = []
    for path in files:
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            for match in PATH_RE.finditer(line):
                target = match.group(1)
                if '...' in target or '…' in target or '<' in target:
                    continue  # illustrative path
                if not _exists(target, repo_root):
                    out.append({'kind': 'PATH', 'file': os.path.relpath(path, REPO_ROOT),
                                'line': lineno, 'detail': target})
    return out


def check_scripts(files: list[str], book_root: str | None = None) -> list[dict]:
    base = book_root or _config.BOOK_ROOT
    # documented scripts live in the toolchain, and a contract may point at the
    # test that enforces it, so both trees count as known names
    available = set()
    for tree in ('python', 'test'):
        available |= {os.path.basename(p) for p in
                      glob.glob(os.path.join(base, 'src', tree, '**', '*.py'),
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


def check_chapters(files: list[str]) -> list[dict]:
    configured = set(_config.chapter_names())
    actual = {os.path.basename(p) for p in
              glob.glob(os.path.join(_config.MANUSCRIPT_DIR, '*.md'))}
    out = []
    for path in files:
        if os.path.basename(path) in LEDGER_DOCS:
            continue  # the changelog and the findings ledger cite old names on purpose
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            # a chapter name is wrong whether or not it is written in back-ticks:
            # a directory tree in a document names files just like prose does
            for name in CHAPTER_RE.findall(line):
                if name not in configured or name not in actual:
                    out.append({'kind': 'CHAPTER', 'file': os.path.relpath(path, REPO_ROOT),
                                'line': lineno, 'detail': name})
    return out


def check_config() -> list[dict]:
    """Every chapter keyed in a book.toml table must be in the chapter list.

    A table that names a file the reading order does not carry is a dead key: the
    renderer never reaches it, so the mapping it expresses is a lie nobody sees.
    """
    files = set(_config.chapter_names())
    config_rel = os.path.relpath(_config.CONFIG_PATH, REPO_ROOT)
    out = []
    for table in CHAPTER_TABLES:
        for key in _config.chapter_table(table):
            if key not in files:
                out.append({'kind': 'CONFIG', 'file': config_rel,
                            'line': 1,
                            'detail': f'[chapters.{table}] names {key}, '
                                      f'which [chapters] files does not carry'})
    return out


def check_levels(files: list[str]) -> list[dict]:
    """A gate level is declared in one table only.

    The level of a check has one owner: the testplan's own gate tables. A second
    table that restates levels drifts from that one silently, because nothing
    compares the two.
    """
    out = []
    for path in files:
        if os.path.basename(os.path.dirname(path)) != 'managements':
            continue
        owner = os.path.basename(path) == 'testplan.md'
        heading = ''
        for lineno, line in enumerate(_fsutil.read_lines(path), start=1):
            if line.startswith('#'):
                heading = line.lstrip('#').strip()
                continue
            if not line.lstrip().startswith('|'):
                continue
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if not any(LEVEL_RE.match(cell) for cell in cells):
                continue
            if owner and heading.startswith(LEVEL_SECTIONS):
                continue
            out.append({'kind': 'LEVEL', 'file': os.path.relpath(path, REPO_ROOT),
                        'line': lineno,
                        'detail': 'gate level belongs to testplan §2.1/§2.2: '
                                  + line.strip()[:48]})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    files = doc_files()
    findings = (check_paths(files) + check_scripts(files) + check_chapters(files)
                + check_config() + check_levels(files) + check_manual_scope()
                + check_managements() + check_numbering(files))

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
