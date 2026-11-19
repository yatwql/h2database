#!/usr/bin/env python3
"""Single source of truth for the book's layout and toolchain policy.

Two layers, both read here so no script hard-codes either:

* ``books/data/tmpl/book.toml`` — content organisation: paths, chapter order,
  required sections, book metadata.
* ``books/data/config/config.json`` — toolchain policy: thresholds, caption
  vocabulary, source-tree locations, baseline file locations.
"""
from __future__ import annotations

import glob
import json
import os
import tomllib

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
# BOOK_ROOT may be overridden (tests, tooling, alternative checkouts).
BOOK_ROOT = os.environ.get('BOOK_ROOT') or os.path.dirname(
    os.path.dirname(os.path.dirname(TOOLS_DIR)))
CONFIG_PATH = os.path.join(BOOK_ROOT, 'data', 'tmpl', 'book.toml')
POLICY_PATH = os.environ.get('BOOK_POLICY') or os.path.join(
    BOOK_ROOT, 'data', 'config', 'config.json')


class ConfigError(RuntimeError):
    """Raised when book.toml is missing or inconsistent."""


def _load_policy() -> dict:
    """Load toolchain policy; an absent file yields an empty policy."""
    try:
        with open(POLICY_PATH, encoding='utf-8') as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise ConfigError(f'invalid JSON in {POLICY_PATH}: {exc}') from exc


def _load() -> dict:
    try:
        with open(CONFIG_PATH, 'rb') as fh:
            return tomllib.load(fh)
    except FileNotFoundError as exc:  # pragma: no cover - broken checkout
        raise ConfigError(f'missing config: {CONFIG_PATH}') from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f'invalid TOML in {CONFIG_PATH}: {exc}') from exc


_CFG = _load()


def _path(key: str) -> str:
    rel = _CFG.get('paths', {}).get(key)
    if not rel:
        raise ConfigError(f'book.toml: missing [paths].{key}')
    return os.path.join(BOOK_ROOT, rel)


MANUSCRIPT_DIR = _path('manuscript')
DIST_DIR = _path('dist')
DOCS_DIR = _path('docs')

MERGED_NAME = _CFG.get('book', {}).get('merged_name', 'h2-source-code-analysis')
TITLE = _CFG.get('book', {}).get('title', '')
VERSION = _CFG.get('book', {}).get('version', '')

POLICY = _load_policy()

# Thresholds come from config.json; book.toml values (legacy/fixtures) still
# win nothing — they are only used as a fallback when no policy file exists.
THRESHOLDS: dict = dict(POLICY.get('thresholds') or _CFG.get('thresholds', {}))
SECTIONS: dict = dict(_CFG.get('sections', {}))
SOURCES: dict = dict(POLICY.get('sources') or _CFG.get('sources', {}))
CAPTIONS: dict = dict(POLICY.get('captions', {}))
DIAGRAMS: dict = dict(POLICY.get('diagrams', {}))
BASELINES: dict = dict(POLICY.get('baselines', {}))
REQUIRED_SECTIONS: list[str] = list(SECTIONS.get('per_chapter', []))


def manuscript(*parts: str) -> str:
    """Absolute path inside manuscript/."""
    return os.path.join(MANUSCRIPT_DIR, *parts)


def dist(name: str) -> str:
    """Absolute path to a delivery artifact."""
    return os.path.join(DIST_DIR, name)


def merged_md() -> str:
    return dist(f'{MERGED_NAME}.md')


def merged_html() -> str:
    return dist(f'{MERGED_NAME}.html')


def merged_pdf() -> str:
    return dist(f'{MERGED_NAME}.pdf')


def merged_print_pdf() -> str:
    return dist(f'{MERGED_NAME}-print.pdf')


def merged_epub() -> str:
    return dist(f'{MERGED_NAME}.epub')


def chapter_files(include_cover: bool = True) -> list[str]:
    """Chapter files in reading order (absolute paths, existing files only)."""
    names = list(_CFG.get('chapters', {}).get('files', []))
    if not include_cover:
        names = [n for n in names if n != 'cover.md']
    return [manuscript(n) for n in names]


def chapter_names(include_cover: bool = True) -> list[str]:
    """Chapter file names in reading order."""
    return [os.path.basename(p) for p in chapter_files(include_cover)]


def _glob_matter(key: str) -> list[str]:
    pattern = _CFG.get('chapters', {}).get(key, '')
    if not pattern:
        return []
    return sorted(glob.glob(manuscript(pattern)))


def front_matter() -> list[str]:
    return _glob_matter('front_glob')


def back_matter() -> list[str]:
    return _glob_matter('back_glob')


def all_manuscript_files() -> list[str]:
    """Front matter + chapters + back matter, in reading order."""
    return front_matter() + chapter_files() + back_matter()


def glossary_path() -> str:
    return manuscript('back', 'glossary.md')


def index_path() -> str:
    return manuscript('back', 'index.md')


def references_path() -> str:
    return manuscript('back', 'references.md')


def policy_value(section: str, key: str, default=None):
    """Read a value from a policy section with a default."""
    return (POLICY.get(section) or {}).get(key, default)


def baseline_path(name: str) -> str:
    """Absolute path of a configured baseline file."""
    rel = BASELINES.get(name)
    if not rel:
        raise ConfigError(f'config.json: missing [baselines].{name}')
    return os.path.join(BOOK_ROOT, rel)


def source_tree(key: str) -> str:
    """Absolute path of a configured H2 source location."""
    rel = SOURCES.get(key)
    if not rel:
        raise ConfigError(f'config.json: missing [sources].{key}')
    return os.path.normpath(os.path.join(BOOK_ROOT, rel))


def chapter_packages() -> dict[str, list[str]]:
    """Chapter file -> source packages it must digest (stage-1 mapping)."""
    return dict(_CFG.get('chapters', {}).get('packages', {}))


def missing_files() -> list[str]:
    """Configured chapter files that do not exist on disk."""
    names = list(_CFG.get('chapters', {}).get('files', []))
    return [n for n in names if not os.path.exists(manuscript(n))]
