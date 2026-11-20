#!/usr/bin/env python3
"""Keep the three versions coherent: tool, analyzed source, document.

  TOOL    lib/_version.py (or base.json [sources].tool_version) — semver
  SOURCE  base.json [sources].version or the source manifest (pom/pyproject/Cargo)
  DOC     book.toml [book].version — also written into management doc headers

Checks
  VERSION   tool/doc resolve and are non-empty; source resolves (warning if not)
  DOC_HEAD  management documents declaring "> 版本：vX" match the doc version
  NAME      the book title is the single source: the delivery-facing management
            documents are titled after it, and the display fields in the config
            carry it too
  SOFTWARE  the toolchain name is the single source: every management and user
            document names it, and no program spells it out by hand
  COVER     the cover's "版本 vX" line repeats the configured document version
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


# Documents that speak for the book itself; their H1 must name it.
TITLED_DOCS = ('requirements.md', 'technical.md', 'testplan.md')
# Config fields that are shown to a reader of the book and must carry the title.
TITLE_FIELDS = ('display_title_zh', 'publisher', 'running_head')


def software_problems() -> list[str]:
    """The toolchain names itself in one place; every surface repeats that name."""
    from lib._version import APP_NAME, APP_NAME_ZH

    problems: list[str] = []
    doc_dirs = (os.path.join(_config.BOOK_ROOT, 'docs', 'managements'),
                os.path.join(_config.BOOK_ROOT, 'docs', 'manuals'))
    docs = [os.path.join(_config.BOOK_ROOT, 'README.md')]
    for directory in doc_dirs:
        if os.path.isdir(directory):
            docs += sorted(glob.glob(os.path.join(directory, '*.md')))
    # a book without documentation yet (a fresh scaffold, a test fixture) has no
    # surfaces to keep in sync; only what exists is checked
    docs = [path for path in docs if os.path.isfile(path)]
    if not docs:
        return problems
    for path in docs:
        text = _fsutil.read_text(path)
        rel = os.path.relpath(path, _config.BOOK_ROOT)
        if APP_NAME not in text:
            problems.append(f'{rel}: does not name the software ({APP_NAME})')
        if APP_NAME_ZH not in text:
            problems.append(f'{rel}: does not carry the Chinese software name ({APP_NAME_ZH})')
    # No program may hardcode the name: it lives in lib/_version.py and is read
    # through _config.app_name()/app_title().
    src_root = os.path.join(_config.BOOK_ROOT, 'src', 'python')
    for path in glob.glob(os.path.join(src_root, '**', '*.py'), recursive=True):
        if path.endswith(os.path.join('lib', '_version.py')):
            continue
        if APP_NAME in _fsutil.read_text(path) or APP_NAME_ZH in _fsutil.read_text(path):
            problems.append(f'{os.path.relpath(path, _config.BOOK_ROOT)}: spells the '
                            f'software name; read it from lib._version instead')
    return problems


def title_problems() -> list[str]:
    """Every reader-facing surface uses the book title from book.toml."""
    title = _config.TITLE
    problems: list[str] = []
    if not title:
        return ['book.toml [book].title is empty']
    docs_dir = os.path.join(_config.BOOK_ROOT, 'docs', 'managements')
    if not os.path.isdir(docs_dir):
        return problems
    for name in TITLED_DOCS:
        path = os.path.join(docs_dir, name)
        if not os.path.isfile(path):
            continue
        lines = _fsutil.read_lines(path)
        first = lines[0] if lines else ''
        if not first.startswith(f'# {title}'):
            problems.append(f'docs/managements/{name}: H1 must start with "# {title}" '
                            f'(found {first[:40]!r})')
    for field in TITLE_FIELDS:
        value = _config.project(field)
        if value and title not in value:
            problems.append(f'book.toml [project].{field} = {value!r} does not carry '
                            f'the book title {title!r}')
    return problems


COVER_VERSION_RE = re.compile(r'版本\s+v([\d.]+)')


def cover_problems() -> list[str]:
    """The cover is a display surface: its version is the configured one."""
    path = _config.manuscript('cover.md')
    if not os.path.isfile(path):
        return []
    text = _fsutil.read_text(path)
    if '版本' not in text:
        return []
    label = os.path.relpath(path, _config.BOOK_ROOT)
    match = COVER_VERSION_RE.search(text)
    if match is None:
        return [f'{label}: no "版本 vX" line']
    if match.group(1) != _config.VERSION:
        return [f'{label}: shows v{match.group(1)}, config says v{_config.VERSION}']
    return []


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

    problems += title_problems()
    problems += software_problems()
    problems += cover_problems()

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
