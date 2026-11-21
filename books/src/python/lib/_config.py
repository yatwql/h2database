#!/usr/bin/env python3
"""Single source of truth for the book's layout and toolchain policy.

Two layers, both read here so no script hard-codes either:

* ``books/data/tmpl/book.toml`` — content organisation: book identity, paths,
  chapter order, per-file titles/numbering/coverage, package mapping.
* ``books/data/config/base.json`` — infrastructure: source tree location,
  file suffix / package prefix, state and baseline paths, toolchain budgets.
* ``books/data/config/style.json`` — book style: display copy, section skeleton,
  caption vocabulary and presets, diagram markers, writing thresholds,
  generation caps and templates.
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import subprocess
import tomllib

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
# BOOK_ROOT may be overridden (tests, tooling, alternative checkouts).
BOOK_ROOT = os.environ.get('BOOK_ROOT') or os.path.dirname(
    os.path.dirname(os.path.dirname(TOOLS_DIR)))
CONFIG_PATH = os.path.join(BOOK_ROOT, 'data', 'tmpl', 'book.toml')
CONFIG_DIR = os.path.join(BOOK_ROOT, 'data', 'config')
# Two policy layers: infrastructure (base.json) and book style (style.json).
BASE_POLICY_PATH = os.path.join(CONFIG_DIR, 'base.json')
STYLE_POLICY_PATH = os.path.join(CONFIG_DIR, 'style.json')
# Legacy single-file policy, still honoured when the split files are absent.
POLICY_PATH = os.environ.get('BOOK_POLICY') or os.path.join(CONFIG_DIR, 'config.json')


class ConfigError(RuntimeError):
    """Raised when book.toml is missing or inconsistent."""


def _read_policy(path: str) -> dict:
    """Load one policy file; an absent file yields an empty mapping."""
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        raise ConfigError(f'invalid JSON in {path}: {exc}') from exc
    return data if isinstance(data, dict) else {}


def _load_policy() -> dict:
    """Merged view of base.json + style.json (or a single combined file)."""
    base = _read_policy(BASE_POLICY_PATH)
    style = _read_policy(STYLE_POLICY_PATH)
    if not base and not style:
        return _read_policy(POLICY_PATH)
    merged: dict = {}
    for layer in (base, style):
        for key, value in layer.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    # toolchain budgets are exposed under [thresholds] for the callers
    merged.setdefault('thresholds', {})
    merged['thresholds'] = {**merged.get('toolchain', {}), **merged['thresholds']}
    return merged


def _load_layer(path: str) -> dict:
    """Expose one policy layer (base or style) for targeted reads."""
    return _read_policy(path)


def _load() -> dict:
    try:
        with open(CONFIG_PATH, 'rb') as fh:
            return tomllib.load(fh)
    except FileNotFoundError as exc:  # pragma: no cover - broken checkout
        raise ConfigError(f'missing config: {CONFIG_PATH}') from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f'invalid TOML in {CONFIG_PATH}: {exc}') from exc


_CFG = _load()


def excluded_dirs() -> tuple[str, ...]:
    """Directories that hold artifacts or read-only history, never live content.

    `dist/` is regenerated output; `data/snapshots/` is a frozen copy of another
    book kept for comparison. Gates must judge the manuscript only.
    """
    snapshots = str(BASE_POLICY.get('paths', {}).get('snapshots', 'data/snapshots'))
    return (os.path.join(BOOK_ROOT, 'dist'), os.path.join(BOOK_ROOT, snapshots))


def _path(key: str) -> str:
    rel = _CFG.get('paths', {}).get(key)
    if not rel:
        raise ConfigError(f'book.toml: missing [paths].{key}')
    return os.path.join(BOOK_ROOT, rel)


def tmp_dir() -> str:
    """Scratch directory under the book root (gitignored, regenerated)."""
    rel = _CFG.get('paths', {}).get('tmp') or 'data/tmp'
    return os.path.join(BOOK_ROOT, rel)


def state_dir() -> str:
    """Directory for the derived state ingest rebuilds on every run."""
    rel = _CFG.get('paths', {}).get('state') or 'data/state'
    return os.path.join(BOOK_ROOT, rel)


def state_path(name: str) -> str:
    """One file inside the derived-state directory."""
    return os.path.join(state_dir(), name)


def config_path(name: str) -> str:
    """One policy file inside the configuration directory."""
    return os.path.join(CONFIG_DIR, name)


def template_dir() -> str:
    """Directory holding the book's templates and case-study pipeline."""
    rel = _CFG.get('paths', {}).get('templates') or 'data/tmpl'
    return os.path.join(BOOK_ROOT, rel)


def template_path(name: str) -> str:
    """One file inside the template directory."""
    return os.path.join(template_dir(), name)


def baseline_dir() -> str:
    """Directory holding the reviewed-issue baselines."""
    rel = _CFG.get('paths', {}).get('baselines') or 'data/baselines'
    return os.path.join(BOOK_ROOT, rel)


MANUSCRIPT_DIR = _path('manuscript')
DIST_DIR = _path('dist')
DOCS_DIR = _path('docs')

MERGED_NAME = _CFG.get('book', {}).get('merged_name', 'book')
TITLE = _CFG.get('book', {}).get('title', '')
VERSION = _CFG.get('book', {}).get('version', '')

POLICY = _load_policy()
BASE_POLICY = _load_layer(BASE_POLICY_PATH)
STYLE_POLICY = _load_layer(STYLE_POLICY_PATH)

# Thresholds come from config.json; book.toml values (fixtures) still
# win nothing — they are only used as a fallback when no policy file exists.
THRESHOLDS: dict = dict(POLICY.get('thresholds') or _CFG.get('thresholds', {}))
SECTIONS: dict = dict(_CFG.get('sections', {}))
SOURCES: dict = dict(POLICY.get('sources') or _CFG.get('sources', {}))
CAPTIONS: dict = dict(POLICY.get('captions', {}))
DIAGRAMS: dict = dict(POLICY.get('diagrams', {}))
BASELINES: dict = dict(POLICY.get('baselines', {}))
REQUIRED_SECTIONS: list[str] = list(SECTIONS.get('per_chapter', []))


PROJECT: dict = dict(_CFG.get('project', {}))


LANGUAGE_DIR = os.path.join(BOOK_ROOT, 'data', 'language')
_LAST_CHANGE: dict[str, str] = {}
LANGUAGE_CODE = os.environ.get('BOOK_LANGUAGE') or 'zh'


def language() -> dict:
    """Language pack for the current manuscript language (data/language/<code>.json)."""
    path = os.path.join(LANGUAGE_DIR, f'{LANGUAGE_CODE}.json')
    data = _read_policy(path)
    if not data:
        data = {'code': LANGUAGE_CODE,
                'sections': {k: v for k, v in SECTIONS.items() if isinstance(v, str)}}
    return data



def project(key: str, default: str = '') -> str:
    """Display copy for the renderers (title, author, running head, ...)."""
    return str(PROJECT.get(key) or default)


TEMPLATES_PATH = os.path.join(BOOK_ROOT, 'data', 'tmpl', 'templates.toml')


def templates() -> dict:
    """Prose templates (document side). Falls back to style.json for old books."""
    try:
        with open(TEMPLATES_PATH, 'rb') as fh:
            data = tomllib.load(fh)
    except FileNotFoundError:
        return dict((POLICY.get('generation') or {}).get('templates') or {})
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f'invalid TOML in {TEMPLATES_PATH}: {exc}') from exc
    return data


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


def chapter_table(name: str) -> dict:
    """One `[chapters.<name>]` table of book.toml (empty when absent)."""
    chapters = _CFG.get('chapters') or {}
    table = chapters.get(name) or {}
    return table if isinstance(table, dict) else {}


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


def chapter_titles() -> dict[str, list[str]]:
    """Chapter file -> ordered section titles contributed by that file."""
    return {k: list(v) for k, v in _CFG.get('chapters', {}).get('titles', {}).items()}


def _last_change(rel_path: str) -> str:
    """ISO date of the last change under ``rel_path`` (git first, then mtime)."""
    cached = _LAST_CHANGE.get(rel_path)
    if cached:
        return cached
    stamp = ''
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%cs', '--', rel_path],
            cwd=BOOK_ROOT, capture_output=True, text=True, timeout=20, check=False)
        stamp = (result.stdout or '').strip()
    except (OSError, subprocess.SubprocessError):
        stamp = ''
    if not stamp:
        newest = 0.0
        root = os.path.join(BOOK_ROOT, rel_path)
        for base, _dirs, files in os.walk(root):
            for name in files:
                try:
                    newest = max(newest, os.path.getmtime(os.path.join(base, name)))
                except OSError:
                    continue
        stamp = datetime.date.fromtimestamp(newest).isoformat() if newest else ''
    _LAST_CHANGE[rel_path] = stamp
    return stamp


def tool_updated() -> str:
    """Date the toolchain code last changed (version bumps are not required)."""
    return _last_change('src/python')


def book_updated() -> str:
    """Date the manuscript last changed."""
    rel = os.path.relpath(MANUSCRIPT_DIR, BOOK_ROOT)
    return _last_change(rel)


def llm_ingest_prose() -> bool:
    """Whether source -> manuscript may use the LLM for prose sections."""
    return bool((_CFG.get('llm') or {}).get('ingest_prose', False))


def key_file() -> str:
    """Local secret file (gitignored); env vars still win over it."""
    return os.path.join(BOOK_ROOT, 'data', 'config', 'llm_key.json')


def chapter_numbering() -> dict[str, list[int]]:
    """Chapter file -> H1 chapter numbers it owns (unique across files)."""
    return {k: list(v) for k, v in _CFG.get('chapters', {}).get('numbering', {}).items()}


def chapter_coverage() -> dict[str, list[int]]:
    """Chapter file -> book chapters it covers (may repeat across files)."""
    return {k: list(v) for k, v in _CFG.get('chapters', {}).get('coverage', {}).items()}


def source_languages() -> list[str]:
    """Source languages to digest (base.json [sources].languages)."""
    raw = SOURCES.get('languages') or ['java']
    return [str(item) for item in raw]


def source_suffixes() -> list[str]:
    """File suffixes for every configured source language."""
    mapping = SOURCES.get('suffixes') or {}
    langs = source_languages()
    found = [mapping[lang] for lang in langs if lang in mapping]
    if not found:
        found = [SOURCES.get('file_suffix') or '.java']
    return sorted(set(found))


def app_name() -> str:
    """Product name of the toolchain (logs, CLI, TUI, Web)."""
    from lib._version import APP_NAME
    return APP_NAME


def app_name_zh() -> str:
    """Chinese product name (shown next to the English one)."""
    from lib._version import APP_NAME_ZH
    return APP_NAME_ZH


def app_title() -> str:
    """One-line product title including the tool version."""
    from lib._version import APP_TITLE, TOOL_VERSION
    return f'{APP_TITLE} v{TOOL_VERSION}'


def tool_version() -> str:
    """The toolchain's own version (independent of book and source)."""
    from lib._version import TOOL_VERSION
    return str(SOURCES.get('tool_version') or TOOL_VERSION)


def doc_version() -> str:
    """The document/manuscript version (book.toml [book].version)."""
    return VERSION


def source_version(root: str | None = None) -> str:
    """Version of the analyzed source tree.

    Resolution order: explicit ``[sources].version`` in base.json, then the
    language manifest of the configured source root (pom.xml / pyproject.toml /
    Cargo.toml). Returns 'unknown' when nothing can be read.
    """
    explicit = SOURCES.get('version')
    if explicit:
        return str(explicit)
    base = root or os.path.join(BOOK_ROOT, SOURCES.get('src_main', ''))
    # manifests may sit next to the source root (maven) or inside it (rust/python)
    candidates: list[str] = []
    pom_root = SOURCES.get('pom_root')
    if pom_root:
        candidates.append(os.path.join(BOOK_ROOT, pom_root))
    for folder in (base, os.path.dirname(base)):
        for name in ('pom.xml', 'pyproject.toml', 'Cargo.toml'):
            candidates.append(os.path.join(folder, name))
    patterns = {
        'pom.xml': r'<version>\s*([^<\s]+)\s*</version>',
        'pyproject.toml': r'^\s*version\s*=\s*"([^"]+)"',
        'Cargo.toml': r'^\s*version\s*=\s*"([^"]+)"',
    }
    for path in candidates:
        if not os.path.isfile(path):
            continue
        detail = _source_version_from(path, patterns[os.path.basename(path)])
        if detail:
            return detail
    return 'unknown'


def _source_version_from(path: str, pattern: str) -> str:
    """First regex capture in a manifest file (empty string when absent)."""
    import re as _re
    try:
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
    except OSError:
        return ''
    match = _re.search(pattern, text, _re.MULTILINE)
    return match.group(1).strip() if match else ''


def versions() -> dict[str, str]:
    """The three versions the toolchain tracks."""
    return {'tool': tool_version(), 'source': source_version(), 'doc': doc_version()}


def missing_files() -> list[str]:
    """Configured chapter files that do not exist on disk."""
    names = list(_CFG.get('chapters', {}).get('files', []))
    return [n for n in names if not os.path.exists(manuscript(n))]
