#!/usr/bin/env python3
"""Keep the three versions coherent: tool, analyzed source, document.

  TOOL    lib/_version.py (or base.json [sources].tool_version) — semver
  SOURCE  base.json [sources].version or the source manifest (pom/pyproject/Cargo)
  DOC     book.toml [book].version — also written into management doc headers

Checks
  VERSION   tool/doc resolve and are non-empty; source resolves (warning if not)
  DOC_HEAD  every management document declares the software version (and only
            that one): the tool version lives in lib/_version.py, the book
            version in book.toml
  NAME      the book title is the single source: the delivery-facing management
            documents are titled after it, and the display fields in the config
            carry it too
  SOFTWARE  the toolchain name is the single source: every management and user
            document names it, and no program spells it out by hand
  COVER     the cover's "版本 vX" line repeats the configured document version
  BOOKNAME  the two names stay apart: the tool documents never name one book,
            and the book never names the tool
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
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

DOC_HEAD_RE = re.compile(r'^\s*>?\s*版本\s*[:：]\s*v?([\d.]+(?:-dev)?)', re.MULTILINE)
MANIFEST_RE = re.compile(r'<!-- versions: tool=(\S+) source=(\S+) doc=(\S+) -->')


def management_docs() -> list[str]:
    """The engineering documents that carry a version header."""
    directory = os.path.join(_config.DOCS_DIR, 'managements')
    return sorted(glob.glob(os.path.join(directory, '*.md')))


def doc_versions() -> list[dict]:
    """Management documents and the version each one declares."""
    findings = []
    for path in management_docs():
        match = DOC_HEAD_RE.search(_fsutil.read_text(path))
        findings.append({'file': os.path.relpath(path, _config.BOOK_ROOT),
                         'version': match.group(1) if match else None})
    return findings


# Documents of the toolchain itself. They describe the tool, so they must not
# hardcode one book's name: the book name is data (book.toml), and the same
# documents have to serve the next book unchanged.
TOOL_DOC_DIRS = ('docs',)
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
    """The tool's documents must stay book-agnostic; the config stays coherent."""
    title = _config.TITLE
    problems: list[str] = []
    if not title:
        return ['book.toml [book].title is empty']
    for directory in TOOL_DOC_DIRS:
        root = os.path.join(_config.BOOK_ROOT, directory)
        for path in glob.glob(os.path.join(root, '**', '*.md'), recursive=True):
            if title in _fsutil.read_text(path):
                rel = os.path.relpath(path, _config.BOOK_ROOT)
                problems.append(f'{rel}: names one particular book; the tool documents '
                                f'must stay book-agnostic')
    readme = os.path.join(_config.BOOK_ROOT, 'README.md')
    if os.path.isfile(readme) and title in _fsutil.read_text(readme):
        problems.append('README.md: names one particular book; keep it in book.toml')
    # the display fields are configuration for a book, so they must agree with it
    for field in TITLE_FIELDS:
        value = _config.project(field)
        if value and title not in value:
            problems.append(f'book.toml [project].{field} = {value!r} does not carry '
                            f'the book title {title!r}')
    return problems


COVER_VERSION_RE = re.compile(r'版本\s+v([\d.]+(?:-dev)?)')


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


def artifact_text(path: str) -> str | None:
    """Readable text of a delivered artifact, or None when it cannot be read.

    A PDF is only read on its first pages: the cover and the running head live
    there, and reading the whole file would cost more than the check is worth.
    """
    if path.endswith('.html'):
        return _fsutil.read_text(path)
    if path.endswith('.pdf'):
        try:
            from pypdf import PdfReader

            reader = PdfReader(path)
        except Exception:  # noqa: BLE001 - unreadable PDF is verify_pdf's finding
            return None
        return ''.join((page.extract_text() or '') for page in reader.pages[:5])
    try:
        with zipfile.ZipFile(path) as archive:
            return ''.join(archive.read(name).decode('utf-8', 'ignore')
                           for name in archive.namelist()
                           if name.endswith(('.opf', '.xhtml', '.html')))
    except (OSError, zipfile.BadZipFile):
        return None


def book_name_problems() -> list[str]:
    """The book may carry its own name anywhere; the tool's name stays out."""
    from lib._version import APP_NAME, APP_NAME_ZH

    problems: list[str] = []
    cover = _config.manuscript('cover.md')
    if os.path.isfile(cover):
        text = _fsutil.read_text(cover)
        label = os.path.relpath(cover, _config.BOOK_ROOT)
        for name in (APP_NAME, APP_NAME_ZH):
            if name in text:
                problems.append(f'{label}: carries the software name {name!r}; '
                                f'the book speaks for itself')
    for path in (_config.merged_html(), _config.merged_epub(), _config.merged_pdf()):
        if not os.path.isfile(path):
            continue
        text = artifact_text(path)
        if text is None:
            continue
        label = os.path.relpath(path, _config.BOOK_ROOT)
        for name in (APP_NAME, APP_NAME_ZH):
            if name in text:
                problems.append(f'{label}: carries the software name {name!r}')
    return problems


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
    problems += book_name_problems()

    for header in doc_versions():
        if header['version'] is None:
            problems.append(f"{header['file']}: no \"> 版本：vX\" header "
                            f"(must carry the software version v{versions['tool']})")
        elif header['version'] != versions['tool']:
            problems.append(f"{header['file']}: header v{header['version']} is not the "
                            f"software version v{versions['tool']} "
                            f"(the book version belongs in book.toml)")

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
