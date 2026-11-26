#!/usr/bin/env python3
"""Resolve a font stack from the fonts this machine actually has.

The rules are the same on every OS, and that is the point: a family is usable only
when it (a) exists, (b) is embeddable, and (c) covers the characters the book
needs. Skipping any one of the three is what produces a 19 MB PDF out of a 7 MB
book — Chromium answers "cannot embed" with Type3 glyph procedures, one stream per
glyph.

How the rules are checked:

  existence  — the font directories of the platform are indexed by reading each
               file's name table, so no `fc-match`/registry dependency;
  embeddability — a single-face `.ttf`/`.otf` can be subset, a `.ttc`/`.otc`
               collection cannot, so collections are pushed to the back;
  coverage   — the union of the family's cmaps is compared with the required
               characters (see audit/font_coverage.py).

Nothing here names a book or a platform: the candidates come from configuration
and the index comes from the host.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import shutil
import subprocess

# Portable preference order. Latin-first, with CJK faces that ship as single files
# on the common platforms; the resolver reorders it per host anyway.
DEFAULT_SANS = ['DejaVu Sans', 'Droid Sans Fallback', 'Source Han Sans SC',
                'Noto Sans CJK SC', 'Microsoft YaHei', 'PingFang SC', 'Arial']
DEFAULT_MONO = ['DejaVu Sans Mono', 'Droid Sans Fallback', 'Consolas',
                'Noto Sans Mono CJK SC', 'Courier New', 'Menlo']
# Families that only carry CJK glyphs are appended after the Latin ones: the
# cascade then picks per character, which is what a mixed-script book needs.
DEFAULT_CJK = ['Droid Sans Fallback', 'Source Han Sans SC', 'Noto Sans CJK SC',
               'Microsoft YaHei', 'PingFang SC', 'WenQuanYi Micro Hei']

# Viewer-side roles (HTML and EPUB) are *declared*, never embedded: the device that
# renders them is not the machine that built them, so a stack resolved from this
# host's font directory would describe the wrong computer. The list is ordered by
# how widely the family is installed, so every reader falls back to something it has.
PORTABLE_SERIF = ['Source Han Serif', 'Noto Serif CJK SC', 'Songti SC', 'SimSun',
                  'DejaVu Serif']
PORTABLE_SANS = ['Source Han Sans', 'Noto Sans CJK SC', 'PingFang SC',
                 'Microsoft YaHei', 'DejaVu Sans']
# Latin mono first: it is installed almost everywhere, while a CJK mono face is
# not, and the cascade still picks the CJK face for the characters it needs
PORTABLE_MONO = ['Consolas', 'DejaVu Sans Mono', 'Menlo', 'Source Han Mono',
                 'Noto Sans Mono CJK SC']

COLLECTION_SUFFIXES = ('.ttc', '.otc')
FONT_SUFFIXES = ('.ttf', '.otf', '.ttc', '.otc')

# Name table ids that carry the family name a stylesheet would use.
FAMILY_IDS = (1, 16)


def font_dirs() -> list[str]:
    """Font directories for this platform, existing ones only."""
    home = os.path.expanduser('~')
    if os.name == 'nt':
        windir = os.environ.get('WINDIR', r'C:\Windows')
        candidates = [os.path.join(windir, 'Fonts'),
                      os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft',
                                   'Windows', 'Fonts')]
    elif os.uname().sysname == 'Darwin' if hasattr(os, 'uname') else False:
        candidates = ['/System/Library/Fonts', '/Library/Fonts',
                      os.path.join(home, 'Library', 'Fonts')]
    else:
        candidates = ['/usr/share/fonts', '/usr/local/share/fonts',
                      os.path.join(home, '.local', 'share', 'fonts'),
                      os.path.join(home, '.fonts')]
    return [path for path in candidates if os.path.isdir(path)]


def _font_files() -> list[str]:
    files: list[str] = []
    for root in font_dirs():
        for base, _dirs, names in os.walk(root):
            files.extend(os.path.join(base, name) for name in names
                         if name.lower().endswith(FONT_SUFFIXES))
    return sorted(files)


def _cache_path() -> str:
    """Where the font index lives: the book's cache, not its scratch directory.

    The index is derived data that costs a full scan of every installed face to
    rebuild, so it may outlive a build; `tmp/` carries no such promise.
    """
    from lib import _config  # noqa: PLC0415 - imported here to avoid an import cycle

    return os.path.join(_config.current().cache_dir(), 'font-index.json')


def _stamp(files: list[str]) -> str:
    digest = hashlib.sha256()
    for path in files:
        try:
            stat = os.stat(path)
        except OSError:
            continue
        digest.update(f'{path}:{stat.st_size}:{stat.st_mtime_ns}'.encode())
    return digest.hexdigest()


def _name_table(face):
    """The name table of one face, or None when it has none."""
    try:
        return face['name']
    except (KeyError, AttributeError):
        return None


def _open_face(entry: dict):
    """Load one face from the index, or None when the file no longer reads."""
    try:
        from fontTools.ttLib import TTCollection, TTFont  # noqa: PLC0415 - optional
        if entry['collection']:
            faces = TTCollection(entry['path'], lazy=True).fonts
            return faces[entry['face']] if entry['face'] < len(faces) else faces[0]
        return TTFont(entry['path'], lazy=True)
    except Exception:
        return None


def is_collection_file(path: str) -> bool:
    """True when the file is a font collection, judged by its header.

    The extension is a hint, not a fact: `.otf` files can be collections and a
    renamed file keeps its header. `ttcf` is the collection magic.
    """
    try:
        with open(path, 'rb') as handle:
            return handle.read(4) == b'ttcf'
    except OSError:
        return False


def _read_families(path: str) -> list[tuple[str, int, bool]]:
    """(family, face index, is_collection) for every face in one file."""
    try:
        from fontTools.ttLib import TTCollection, TTFont  # noqa: PLC0415 - optional
    except ImportError:
        return []
    collection = is_collection_file(path)
    rows: list[tuple[str, int, bool]] = []
    try:
        faces = TTCollection(path, lazy=True).fonts if collection else [TTFont(path, lazy=True)]
    except Exception:
        return []
    for index, face in enumerate(faces):
        names = _name_table(face)
        if names is None:
            continue
        for name_id in FAMILY_IDS:
            value = names.getDebugName(name_id)
            if value:
                rows.append((value.strip(), index, collection))
    return rows


@functools.cache
def index() -> dict[str, list[dict]]:
    """family -> [{path, face, collection}] for this host, cached on disk.

    Building it costs one name-table read per font file, so the result is stored
    under `data/tmp` and keyed by path/size/mtime: adding a font invalidates it,
    copying the book elsewhere does not.
    """
    files = _font_files()
    stamp = _stamp(files)
    cache_file = _cache_path()
    try:
        with open(cache_file, encoding='utf-8') as handle:
            cached = json.load(handle)
        if cached.get('stamp') == stamp:
            return cached['families']
    except (OSError, ValueError, KeyError):
        pass

    families: dict[str, list[dict]] = {}
    for path in files:
        for family, face, collection in _read_families(path):
            families.setdefault(family, []).append(
                {'path': path, 'face': face, 'collection': collection})
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, 'w', encoding='utf-8') as handle:
            json.dump({'stamp': stamp, 'families': families}, handle)
    except OSError:
        pass  # a read-only tree still works, the index is just rebuilt each run
    return families


def _font_file(family: str) -> str:
    """One file that provides `family`, preferring a single-face file."""
    entries = index().get(family) or []
    for entry in entries:
        if not entry['collection']:
            return entry['path']
    return entries[0]['path'] if entries else ''


def is_embeddable(family: str) -> bool:
    """True when a single-face file provides this family.

    A collection cannot be subset by Chromium, which answers with Type3 glyph
    procedures; that is a fidelity and size problem, not a cosmetic one.
    """
    return any(not entry['collection'] for entry in index().get(family) or [])


def coverage(family: str, characters) -> tuple[int, list[str]]:
    """(characters drawn, missing characters) over every face of `family`."""
    wanted = {char for char in characters if char.strip()}
    entries = index().get(family) or []
    if not entries:
        return 0, sorted(wanted)
    try:
        import fontTools  # noqa: F401, PLC0415 - availability probe only
    except ImportError:
        return 0, ['fonttools 未安装，无法校验覆盖']
    drawn: set[str] = set()
    missing: set[str] = set()
    readable = 0
    for entry in entries:
        font = _open_face(entry)
        if font is None:
            continue
        readable += 1
        cmap = font.getBestCmap() or {}
        for char in wanted - drawn:
            if ord(char) in cmap:
                drawn.add(char)
            else:
                missing.add(char)
    if not readable:
        # every face failed to load: nothing was verified, so nothing may be reported
        # as covered
        return 0, sorted(wanted)
    missing -= drawn
    return len(drawn), sorted(missing)


def _fontconfig_names() -> set[str]:
    """Fallback for hosts where the font directory walk finds nothing."""
    fc_list = shutil.which('fc-list')
    if not fc_list:
        return set()
    try:
        out = subprocess.run([fc_list, ':', 'family'], capture_output=True,
                             text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return set()
    names: set[str] = set()
    for line in out.stdout.splitlines():
        names.update(part.strip() for part in line.split(','))
    return {name for name in names if name}


@functools.cache
def resolve(candidates: tuple[str, ...], generic: str) -> str:
    """CSS stack: usable, existing and unknown families, in that order."""
    known = index() or {}
    if not known:
        installed = _fontconfig_names()
        usable = [name for name in candidates if name in installed or not installed]
    else:
        usable = [name for name in candidates if name in known]
    embeddable = [name for name in usable if is_embeddable(name)]
    others = [name for name in candidates if name not in embeddable]
    ordered = embeddable + [name for name in others if name not in embeddable]
    quoted = [f'"{name}"' if ' ' in name else name for name in ordered]
    return ', '.join(quoted + [generic])


def default_sans() -> list[str]:
    """The default sans candidates, for callers that only want to inspect them."""
    return list(DEFAULT_SANS)


PORTABLE = {'serif': (PORTABLE_SERIF, 'serif'),
            'sans': (PORTABLE_SANS, 'sans-serif'),
            'mono': (PORTABLE_MONO, 'monospace')}


def portable_stack(role: str = 'sans') -> str:
    """A stack for a document the reader renders, not this machine.

    The two rules pull in opposite directions: a PDF must name a font the build
    machine actually has, because the file embeds it; an HTML file or an EPUB must
    name fonts the *reader's* device is likely to have, because nothing is embedded.
    Both live here so a book has one place to look, and the difference is stated
    rather than repeated in two stylesheets.
    """
    families, generic = PORTABLE.get(role, PORTABLE['sans'])
    # the lists already interleave Latin and CJK in the order they should be tried,
    # so they are not re-sorted: a serif book must not fall back to a sans CJK face
    # before its own serif one
    quoted = ', '.join(f'"{name}"' if ' ' in name else name for name in families)
    return f'{quoted}, {generic}'


def sans_stack(candidates: list[str] | None = None) -> str:
    return resolve(tuple(candidates or DEFAULT_SANS), 'sans-serif')


def mono_stack(candidates: list[str] | None = None) -> str:
    return resolve(tuple(candidates or DEFAULT_MONO), 'monospace')
