#!/usr/bin/env python3
"""Single source of truth for one book's layout and toolchain policy.

Everything a script needs about a book is resolved by :class:`Config`, which
takes the book root and reads that book's own files. No script hard-codes a
path or a threshold:

* ``data/book/book.toml`` — content organisation: book identity, paths,
  chapter order, per-file titles/numbering/coverage, package mapping.
* ``data/config/base.json`` — infrastructure: source tree location,
  file suffix / package prefix, state and baseline paths, toolchain budgets.
* ``data/config/style.json`` — book style: display copy, section skeleton,
  caption vocabulary and presets, diagram markers, writing thresholds,
  generation caps and templates.

Callers keep using module attributes (``_config.BOOK_ROOT``,
``_config.state_path('outline.json')``): those resolve against the active
book, so one process can read several books by wrapping the work in
``with use(Config('/path/to/book')):``.
"""
from __future__ import annotations

import contextlib
import datetime
import glob
import json
import os
import subprocess
from collections.abc import Iterator

import tomllib

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


# A book is a directory that carries its configuration. Two layouts are accepted:
# the standard one (data/book/book.toml) and a flat one (book.toml at the root), so a
# config directory can hold several books, one per subdirectory.
BOOK_CONFIG = 'book.toml'
BOOK_MARKER = os.path.join('data', 'book', BOOK_CONFIG)


def config_file_of(path: str) -> str:
    """The book configuration inside ``path`` ('' when it is not a book)."""
    for candidate in (os.path.join(path, BOOK_MARKER),
                      os.path.join(path, BOOK_CONFIG)):
        if os.path.isfile(candidate):
            return candidate
    return ''


def checkout_root() -> str:
    """The checkout that holds this toolchain (last-resort book root)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(TOOLS_DIR)))


def books_in(library: str) -> list[str]:
    """Book roots directly under ``library`` (itself included when it is a book)."""
    roots: list[str] = []
    base = os.path.abspath(library)
    if config_file_of(base):
        roots.append(base)
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return roots
    for name in names:
        candidate = os.path.join(base, name)
        if config_file_of(candidate) and candidate not in roots:
            roots.append(candidate)
    return roots


def find_book_root(start: str | None = None) -> str:
    """Nearest ancestor of ``start`` holding data/book/book.toml ('' when none)."""
    current = os.path.abspath(start or os.getcwd())
    while True:
        if config_file_of(current):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return ''
        current = parent


def discover_root(start: str | None = None) -> str:
    """First look: BOOK_ROOT, then the nearest ancestor, then this checkout."""
    override = os.environ.get('BOOK_ROOT')
    if override:
        return os.path.abspath(override)
    return find_book_root(start) or checkout_root()


def resolve_book_root(explicit: str | None = None, start: str | None = None) -> str:
    """Pick the book root: an explicit ``--book``, else what this process bound to.

    The fallback is the root discovered at import, not a fresh search: a process
    that started on one book must not silently switch because the working directory
    changed or an environment variable was cleared.
    """
    if explicit:
        return os.path.abspath(explicit)
    override = os.environ.get('BOOK_ROOT')
    if override:
        return os.path.abspath(override)
    if _IMPORT_ROOT:
        return _IMPORT_ROOT
    return find_book_root(start) or checkout_root()


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


def _merge_policy(base: dict, style: dict, legacy_path: str) -> dict:
    """Merged view of base.json + style.json (or a single combined file)."""
    if not base and not style:
        return _read_policy(legacy_path)
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


def candidate_books(active: str | None = None, start: str | None = None,
                    library: str | None = None) -> list[str]:
    """Book roots the tool can offer, active one first.

    The library directory is where a book's neighbours live; it comes from
    ``library``, else the active book's ``[paths].library``, else the active book's
    parent (the layout the repository itself uses). Only directories holding
    ``data/book/book.toml`` are offered, so a stray folder never appears as a book —
    and the answer no longer depends on a directory convention nobody declared.
    """
    roots: list[str] = []

    def offer(path: str) -> None:
        path = os.path.abspath(path)
        if path not in roots and config_file_of(path):
            roots.append(path)

    current_root = os.path.abspath(active or _IMPORT_ROOT)
    offer(current_root)
    if library is None:
        try:
            library = (Config(current_root).library_dir()
                       if config_file_of(current_root)
                       else None)
        except ConfigError:
            library = None
    parent = library or os.path.dirname(current_root)
    try:
        for name in sorted(os.listdir(parent)):
            offer(os.path.join(parent, name))
    except OSError:
        pass
    found = find_book_root(start)
    if found:
        offer(found)
    return roots


class Config:
    """One book: its root, its configuration files and the values read from them."""

    def __init__(self, root: str | None = None, edition: str | None = None) -> None:
        self.root = os.path.abspath(root or resolve_book_root())
        self.config_dir = os.path.join(self.root, 'data', 'config')
        # book.toml sits at a fixed spot: it is what declares the [paths] overrides.
        self.book_toml = os.path.join(self.root, 'data', 'book', 'book.toml')
        self.base_policy_path = os.path.join(self.config_dir, 'base.json')
        self.style_policy_path = os.path.join(self.config_dir, 'style.json')
        # Legacy single-file policy, still honoured when the split files are absent.
        self.policy_path = (os.environ.get('BOOK_POLICY')
                            or os.path.join(self.config_dir, 'config.json'))
        self.cfg = self._load_book()
        self.base_policy = _read_policy(self.base_policy_path)
        self.style_policy = _read_policy(self.style_policy_path)
        self.policy = _merge_policy(self.base_policy, self.style_policy, self.policy_path)
        self._change_stamps: dict[str, str] = {}
        # book.toml values (fixtures) are only a fallback when no policy exists.
        self.thresholds = dict(self.policy.get('thresholds') or self.cfg.get('thresholds', {}))
        self.sections = dict(self.cfg.get('sections', {}))
        # shared analysis defaults from base.json, with this book's own trees on top:
        # which source a book digests is part of the book, not of the toolchain
        self.sources = {**(self.policy.get('sources') or {}),
                        **(self.cfg.get('sources') or {})}
        self.captions = dict(self.policy.get('captions', {}))
        self.diagrams = dict(self.policy.get('diagrams', {}))
        self.baselines = dict(self.policy.get('baselines', {}))
        self.required_sections = list(self.sections.get('per_chapter', []))
        self.project_map = dict(self.cfg.get('project', {}))
        self.manuscript_dir = self._path('manuscript')
        self.dist_dir = self._path('dist')
        self.docs_dir = self._path('docs')
        self.language_dir = os.path.join(self.root, 'data', 'language')
        self.templates_path = self.template_path('templates.toml')
        self.edition_tables: dict[str, dict] = {}
        self.editions: dict[str, str] = {}
        for key, value in (self.cfg.get('editions') or {}).items():
            name = str(key)
            if isinstance(value, dict):
                self.edition_tables[name] = value
                self.editions[name] = str(value.get('display') or name)
            else:
                self.editions[name] = str(value)
        self.edition = self._pick_edition(edition)
        if self.edition:
            self.manuscript_dir = os.path.join(self.manuscript_dir, self.edition)
        self.merged_name = self.cfg.get('book', {}).get('merged_name', 'book')
        if self.edition:
            named = (self.edition_tables.get(self.edition) or {}).get('merged_name')
            self.merged_name = str(named) if named else f'{self.merged_name}-{self.edition}'
        self.title = self.cfg.get('book', {}).get('title', '')
        self.version = self.cfg.get('book', {}).get('version', '')

    def _pick_edition(self, explicit: str | None) -> str:
        """The edition this Config reads: explicit, then BOOK_EDITION, then default.

        An undeclared edition is an error rather than a silent fallback: quietly
        reading the base manuscript while the caller asked for the abridged one is
        how a release ships the wrong text.
        """
        requested = str(explicit or os.environ.get('BOOK_EDITION') or '').strip()
        if not self.editions:
            if requested:
                raise ConfigError(
                    f'book.toml: [editions] 未声明，不接受版本 {requested!r}')
            return ''
        if requested:
            if requested not in self.editions:
                raise ConfigError(
                    f'book.toml: 未声明版本 {requested!r}；已声明 {sorted(self.editions)}')
            return requested
        default = str(self.cfg.get('default_edition') or '').strip()
        if default:
            if default not in self.editions:
                raise ConfigError(
                    f'book.toml: default_edition {default!r} 不在 [editions] 中')
            return default
        if len(self.editions) == 1:
            return next(iter(self.editions))
        raise ConfigError(
            'book.toml: 声明了多个版本时必须给出 default_edition，或显式传入 --edition')

    # ---- loading -----------------------------------------------------------

    def _load_book(self) -> dict:
        try:
            with open(self.book_toml, 'rb') as fh:
                return tomllib.load(fh)
        except FileNotFoundError as exc:  # pragma: no cover - broken checkout
            raise ConfigError(f'missing config: {self.book_toml}') from exc
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f'invalid TOML in {self.book_toml}: {exc}') from exc

    def _contained(self, path: str, key: str) -> str:
        """Refuse a [paths] entry that leaves the book root."""
        root = os.path.abspath(self.root)
        target = os.path.abspath(path)
        if target != root and not target.startswith(root + os.sep):
            raise ConfigError(
                f'book.toml: [paths].{key} escapes the book root: {path}')
        return path

    def _path(self, key: str) -> str:
        """A path declared in book.toml [paths]; absent keys are an error."""
        rel = (self.cfg.get('paths') or {}).get(key)
        if not rel:
            raise ConfigError(f'book.toml: missing [paths].{key}')
        return self._contained(os.path.join(self.root, rel), key)

    def _rel(self, key: str, default: str) -> str:
        """A path declared in book.toml [paths], with a fallback for new books."""
        rel = (self.cfg.get('paths') or {}).get(key) or default
        return self._contained(os.path.join(self.root, rel), key)

    # ---- directories -------------------------------------------------------

    def library_dir(self) -> str:
        """Where the other books live, in precedence order.

        ``BOOKS_DIR`` (a flag or environment override) beats ``book.toml
        [paths].library``, which beats the book's parent directory. The override
        exists so a session can point at a different library without editing any
        book's configuration.
        """
        override = os.environ.get('BOOKS_DIR')
        if override:
            return os.path.abspath(override)
        rel = (self.cfg.get('paths') or {}).get('library')
        if not rel:
            return os.path.dirname(self.root)
        return os.path.abspath(os.path.join(self.root, str(rel)))

    def book_dir(self) -> str:
        """Directory holding the files that belong to this book alone."""
        return self._rel('book', 'data/book')

    def tmp_dir(self) -> str:
        """Scratch directory under the book root (gitignored, regenerated)."""
        return self._rel('tmp', 'data/tmp')

    def state_dir(self) -> str:
        """Directory for the derived state ingest rebuilds on every run."""
        base = self._rel('state', 'data/state')
        return os.path.join(base, self.edition) if self.edition else base

    def template_dir(self) -> str:
        """Directory holding the book's prose templates."""
        return self._rel('templates', 'data/tmpl')

    def baseline_dir(self) -> str:
        """Directory holding the reviewed-issue baselines."""
        base = self._rel('baselines', 'data/baselines')
        return os.path.join(base, self.edition) if self.edition else base

    def state_path(self, name: str) -> str:
        """One file inside the derived-state directory."""
        return os.path.join(self.state_dir(), name)

    def config_path(self, name: str) -> str:
        """One policy file inside the configuration directory."""
        return os.path.join(self.config_dir, name)

    def book_path(self, name: str) -> str:
        """One book-specific file (book.toml, case-studies.toml, ...)."""
        return os.path.join(self.book_dir(), name)

    def template_path(self, name: str) -> str:
        """One file inside the template directory."""
        return os.path.join(self.template_dir(), name)

    def manuscript(self, *parts: str) -> str:
        """Absolute path inside manuscript/."""
        return os.path.join(self.manuscript_dir, *parts)

    def dist(self, name: str) -> str:
        """Absolute path to a delivery artifact."""
        return os.path.join(self.dist_dir, name)

    def excluded_dirs(self) -> tuple[str, ...]:
        """Directories that hold artifacts or read-only history, never live content.

        `dist/` is regenerated output; `data/snapshots/` is a frozen copy of
        another book kept for comparison; `data/archive/` and the report
        directory are dated evidence copies. Gates judge the manuscript and the
        authored documents only, so none of these may be scanned as content.
        """
        snapshots = str((self.base_policy.get('paths') or {}).get('snapshots', 'data/snapshots'))
        archive = str((self.base_policy.get('archive') or {}).get('dir') or 'data/archive')
        reports = str((self.base_policy.get('reports') or {}).get('dir') or 'test-reports')
        return (os.path.join(self.root, 'dist'),
                os.path.join(self.root, snapshots),
                os.path.join(self.root, archive),
                os.path.join(self.root, reports),
                self.tmp_dir())

    # ---- policy values (read once, shared like the dicts callers patch) -----

    @property
    def language_code(self) -> str:
        return os.environ.get('BOOK_LANGUAGE') or 'zh'

    def project(self, key: str, default: str = '') -> str:
        """Display copy for the renderers (title, author, running head, ...)."""
        return str(self.project_map.get(key) or default)

    def language(self) -> dict:
        """Language pack for the current manuscript language."""
        path = os.path.join(self.language_dir, f'{self.language_code}.json')
        data = _read_policy(path)
        if not data:
            data = {'code': self.language_code,
                    'sections': {k: v for k, v in self.sections.items()
                                 if isinstance(v, str)}}
        return data

    def templates(self) -> dict:
        """Prose templates (document side). Falls back to style.json for old books."""
        path = self.templates_path
        try:
            with open(path, 'rb') as fh:
                return tomllib.load(fh)
        except FileNotFoundError:
            return dict((self.policy.get('generation') or {}).get('templates') or {})
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f'invalid TOML in {path}: {exc}') from exc

    # ---- delivery artifacts ------------------------------------------------

    def merged_md(self) -> str:
        return self.dist(f'{self.merged_name}.md')

    def merged_html(self) -> str:
        return self.dist(f'{self.merged_name}.html')

    def merged_pdf(self) -> str:
        return self.dist(f'{self.merged_name}.pdf')

    def merged_print_pdf(self) -> str:
        return self.dist(f'{self.merged_name}-print.pdf')

    def merged_epub(self) -> str:
        return self.dist(f'{self.merged_name}.epub')

    # ---- manuscript organisation -------------------------------------------

    def chapters_spec(self) -> dict:
        """The chapter table this edition reads: book-level, edition override merged in."""
        base = dict(self.cfg.get('chapters') or {})
        if self.edition:
            override = (self.edition_tables.get(self.edition) or {}).get('chapters') or {}
            base.update(override)
        return base

    def chapter_files(self, include_cover: bool = True) -> list[str]:
        """Chapter files in reading order (absolute paths)."""
        names = list(self.chapters_spec().get('files', []))
        if not include_cover:
            names = [n for n in names if n != 'cover.md']
        return [self.manuscript(n) for n in names]

    def chapter_names(self, include_cover: bool = True) -> list[str]:
        """Chapter file names in reading order."""
        return [os.path.basename(p) for p in self.chapter_files(include_cover)]

    def chapter_table(self, name: str) -> dict:
        """One `[chapters.<name>]` table of book.toml (empty when absent)."""
        chapters = self.chapters_spec()
        table = chapters.get(name) or {}
        return table if isinstance(table, dict) else {}

    def _glob_matter(self, key: str) -> list[str]:
        pattern = self.chapters_spec().get(key, '')
        if not pattern:
            return []
        return sorted(glob.glob(self.manuscript(pattern)))

    def front_matter(self) -> list[str]:
        return self._glob_matter('front_glob')

    def back_matter(self) -> list[str]:
        return self._glob_matter('back_glob')

    def all_manuscript_files(self) -> list[str]:
        """Front matter + chapters + back matter, in reading order."""
        return self.front_matter() + self.chapter_files() + self.back_matter()

    def glossary_path(self) -> str:
        return self.manuscript('back', 'glossary.md')

    def index_path(self) -> str:
        return self.manuscript('back', 'index.md')

    def chapter_packages(self) -> dict[str, list[str]]:
        """Chapter file -> source packages it must digest (stage-1 mapping)."""
        return dict(self.chapters_spec().get('packages', {}))

    def chapter_titles(self) -> dict[str, list[str]]:
        """Chapter file -> ordered section titles contributed by that file."""
        return {k: list(v) for k, v in self.chapters_spec().get('titles', {}).items()}

    def chapter_numbering(self) -> dict[str, list[int]]:
        """Chapter file -> H1 chapter numbers it owns (unique across files)."""
        return {k: list(v) for k, v in self.chapters_spec().get('numbering', {}).items()}

    def chapter_numbering_for(self, edition: str | None) -> dict[str, list[int]]:
        """Numbering table for one edition; ``None`` means the book's own table."""
        base = dict(self.cfg.get('chapters') or {})
        if edition:
            override = (self.edition_tables.get(edition) or {}).get('chapters') or {}
            base = {**base, **override}
        return {k: list(v) for k, v in (base.get('numbering') or {}).items()}

    def chapter_coverage(self) -> dict[str, list[int]]:
        """Chapter file -> book chapters it covers (may repeat across files)."""
        return {k: list(v) for k, v in self.chapters_spec().get('coverage', {}).items()}

    def missing_files(self) -> list[str]:
        """Configured chapter files that do not exist on disk."""
        names = list(self.chapters_spec().get('files', []))
        return [n for n in names if not os.path.exists(self.manuscript(n))]

    # ---- source tree -------------------------------------------------------

    def baseline_path(self, name: str) -> str:
        """Absolute path of a configured baseline file."""
        rel = self.baselines.get(name)
        if not rel:
            raise ConfigError(f'config.json: missing [baselines].{name}')
        return os.path.join(self.root, rel)

    def source_roots(self) -> list[dict[str, str]]:
        """Every source tree this book digests, in declaration order.

        A single ``src_main`` is one root labelled ``main``; ``roots[]`` carries one
        entry per tree. Labels must be unique — the inventory, the coordinate report
        and the logs key on them, and two trees sharing a label is indistinguishable
        from one tree digested twice.
        """
        declared = self.sources.get('roots')
        if declared:
            roots: list[dict[str, str]] = []
            seen: set[str] = set()
            for entry in declared:
                if not isinstance(entry, dict):
                    raise ConfigError('config.json: [sources].roots 的每一项都应是对象')
                label = str(entry.get('label') or '').strip()
                path = str(entry.get('path') or '').strip()
                if not label or not path:
                    raise ConfigError('config.json: [sources].roots 需要 label 与 path')
                if label in seen:
                    raise ConfigError(f'config.json: [sources].roots 的 label 重复：{label}')
                seen.add(label)
                roots.append({'label': label, 'path': path,
                              'language': str(entry.get('language') or ''),
                              'version': str(entry.get('version') or '')})
            return roots
        rel = self.sources.get('src_main')
        if not rel:
            raise ConfigError('config.json: missing [sources].src_main')
        return [{'label': 'main', 'path': str(rel),
                 'language': '', 'version': str(self.sources.get('version') or '')}]

    def source_tree(self, key: str) -> str:
        """Absolute path of a configured source location.

        ``src_main`` means the first root, so every caller written for a single tree
        keeps working; any other key is a root label.
        """
        if key in ('src_main', 'main'):
            root = self.source_roots()[0]
            return os.path.normpath(os.path.join(self.root, root['path']))
        for root in self.source_roots():
            if root['label'] == key:
                return os.path.normpath(os.path.join(self.root, root['path']))
        rel = self.sources.get(key)
        if not rel:
            raise ConfigError(f'config.json: missing [sources].{key}')
        return os.path.normpath(os.path.join(self.root, rel))

    def source_languages(self) -> list[str]:
        """Source languages to digest (base.json [sources].languages)."""
        raw = self.sources.get('languages') or ['java']
        return [str(item) for item in raw]

    def source_suffixes(self) -> list[str]:
        """File suffixes for every configured source language."""
        mapping = self.sources.get('suffixes') or {}
        found = [mapping[lang] for lang in self.source_languages() if lang in mapping]
        if not found:
            found = [self.sources.get('file_suffix') or '.java']
        return sorted(set(found))

    def key_file(self) -> str:
        """Local secret file (gitignored); env vars still win over it."""
        return self.config_path('llm_key.json')

    def llm_ingest_prose(self) -> bool:
        """Whether source -> manuscript may use the LLM for prose sections."""
        return bool((self.cfg.get('llm') or {}).get('ingest_prose', False))

    # ---- versions ----------------------------------------------------------

    def _last_change(self, rel_path: str) -> str:
        """ISO date of the last change under ``rel_path`` (git first, then mtime)."""
        cached = self._change_stamps.get(rel_path)
        if cached:
            return cached
        stamp = ''
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%cs', '--', rel_path],
                cwd=self.root, capture_output=True, text=True, timeout=20, check=False)
            stamp = (result.stdout or '').strip()
        except (OSError, subprocess.SubprocessError):
            stamp = ''
        if not stamp:
            newest = 0.0
            root = os.path.join(self.root, rel_path)
            for base, _dirs, files in os.walk(root):
                for name in files:
                    try:
                        newest = max(newest, os.path.getmtime(os.path.join(base, name)))
                    except OSError:
                        continue
            stamp = datetime.date.fromtimestamp(newest).isoformat() if newest else ''
        self._change_stamps[rel_path] = stamp
        return stamp

    def tool_updated(self) -> str:
        """Date the toolchain code last changed (version bumps are not required)."""
        return self._last_change('src/python')

    def book_updated(self) -> str:
        """Date the manuscript last changed."""
        return self._last_change(os.path.relpath(self.manuscript_dir, self.root))

    def tool_version(self) -> str:
        """The toolchain's own version (independent of book and source)."""
        from lib._version import TOOL_VERSION
        return str(self.sources.get('tool_version') or TOOL_VERSION)

    def doc_version(self) -> str:
        """The document/manuscript version (book.toml [book].version)."""
        return self.version

    def source_versions(self) -> dict[str, str]:
        """Per-root source versions, keyed by label."""
        out: dict[str, str] = {}
        for entry in self.source_roots():
            out[entry['label']] = entry['version'] or self.source_version()
        return out

    def source_version(self, root: str | None = None) -> str:
        """Version of the analyzed source tree.

        Resolution order: explicit ``[sources].version`` in base.json, then the
        language manifest of the configured source root (pom.xml /
        pyproject.toml / Cargo.toml). Returns 'unknown' when nothing is read.
        """
        explicit = self.sources.get('version')
        if explicit:
            return str(explicit)
        base = root or os.path.join(self.root, self.sources.get('src_main', ''))
        # manifests may sit next to the source root (maven) or inside it (rust/python)
        candidates: list[str] = []
        pom_root = self.sources.get('pom_root')
        if pom_root:
            candidates.append(os.path.join(self.root, pom_root))
        for folder in (base, os.path.dirname(base)):
            for name in ('pom.xml', 'pyproject.toml', 'Cargo.toml'):
                candidates.append(os.path.join(folder, name))
        for path in candidates:
            if not os.path.isfile(path):
                continue
            detail = _source_version_from(path, _MANIFEST_PATTERNS[os.path.basename(path)])
            if detail:
                return detail
        return 'unknown'

    def versions(self) -> dict:
        """The three versions the toolchain tracks.

        ``source`` is a string while one tree is digested and a label -> version map
        once several are, which is what the callers that print it already handle.
        """
        roots = self.source_roots()
        source = (self.source_version() if len(roots) == 1
                  else self.source_versions())
        return {'tool': self.tool_version(), 'source': source, 'doc': self.doc_version()}


_MANIFEST_PATTERNS = {
    'pom.xml': r'<version>\s*([^<\s]+)\s*</version>',
    'pyproject.toml': r'^\s*version\s*=\s*"([^"]+)"',
    'Cargo.toml': r'^\s*version\s*=\s*"([^"]+)"',
}


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


# ---- the active book -------------------------------------------------------

# Resolved once at import (that is what the old constants did), but the Config
# itself is built on first use: a missing book then raises where a caller can
# catch it instead of aborting the import.
_IMPORT_ROOT = discover_root()
_ACTIVE: Config | None = None


def current() -> Config:
    """The book the module-level helpers resolve against."""
    global _ACTIVE
    if _ACTIVE is None:
        _ACTIVE = Config(_IMPORT_ROOT)
    return _ACTIVE


def reset(cfg: Config | None = None) -> None:
    """Rebind the active book for the rest of the process (None → rediscover)."""
    global _ACTIVE
    _ACTIVE = cfg


@contextlib.contextmanager
def use(cfg: Config) -> Iterator[Config]:
    """Read a different book for the duration of the block."""
    global _ACTIVE
    previous, _ACTIVE = _ACTIVE, cfg
    try:
        yield cfg
    finally:
        _ACTIVE = previous


def for_root(root: str) -> Config:
    """Load a book by its root directory."""
    return Config(root)


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


# ---- module attributes that follow the active book -------------------------

# Every public Config method is reachable as ``_config.<method>``: the module
# attribute is the active book's bound method, so tools keep the call they had
# before the book became an object.
_CALLABLES = frozenset(name for name in dir(Config) if not name.startswith('_'))

_ALIASES = {
    'BOOK_ROOT': lambda c: c.root,
    'BOOK_DIR': lambda c: c.book_dir,
    'CONFIG_PATH': lambda c: c.book_toml,
    'CONFIG_DIR': lambda c: c.config_dir,
    'BASE_POLICY_PATH': lambda c: c.base_policy_path,
    'STYLE_POLICY_PATH': lambda c: c.style_policy_path,
    'POLICY_PATH': lambda c: c.policy_path,
    'MANUSCRIPT_DIR': lambda c: c.manuscript_dir,
    'DIST_DIR': lambda c: c.dist_dir,
    'DOCS_DIR': lambda c: c.docs_dir,
    'LANGUAGE_DIR': lambda c: c.language_dir,
    'LANGUAGE_CODE': lambda c: c.language_code,
    'TEMPLATES_PATH': lambda c: c.templates_path,
    'MERGED_NAME': lambda c: c.merged_name,
    'TITLE': lambda c: c.title,
    'VERSION': lambda c: c.version,
    'POLICY': lambda c: c.policy,
    'BASE_POLICY': lambda c: c.base_policy,
    'STYLE_POLICY': lambda c: c.style_policy,
    'THRESHOLDS': lambda c: c.thresholds,
    'SECTIONS': lambda c: c.sections,
    'SOURCES': lambda c: c.sources,
    'CAPTIONS': lambda c: c.captions,
    'DIAGRAMS': lambda c: c.diagrams,
    'BASELINES': lambda c: c.baselines,
    'REQUIRED_SECTIONS': lambda c: c.required_sections,
    'PROJECT': lambda c: c.project_map,
    '_CFG': lambda c: c.cfg,
}


def __getattr__(name: str):
    """Resolve the historical constants and helpers against the active book."""
    resolver = _ALIASES.get(name)
    if resolver is not None:
        return resolver(current())
    if name in _CALLABLES:
        return getattr(current(), name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_ALIASES) | set(_CALLABLES))
