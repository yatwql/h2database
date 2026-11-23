#!/usr/bin/env python3
"""Pick a font stack from what the build host actually has.

Why this is a module and not a constant: a stylesheet that names a family the
host lacks makes Chromium fall back, and every fallback path it can take costs
either fidelity or file size — a `.ttc` collection and a synthesised bold face
cannot be embedded, so the whole text is exported as Type3 glyph procedures
(one stream per glyph: 19 MB instead of 7 MB for the same pages). Only a plain
`.ttf`/`.otf` file with real faces embeds cleanly.

The preference list is configuration (`[render] font_stack_sans` / `_mono`), so
another book, or another machine, resolves its own answer; the defaults below are
just the portable order.
"""
from __future__ import annotations

import functools
import shutil
import subprocess

DEFAULT_SANS = ['Droid Sans Fallback', 'Source Han Sans SC', 'Noto Sans CJK SC',
                'Microsoft YaHei', 'PingFang SC', 'DejaVu Sans']
DEFAULT_MONO = ['DejaVu Sans Mono', 'Droid Sans Fallback', 'Consolas',
                'Noto Sans Mono CJK SC', 'Courier New']

# Fonts whose files are collections or are known to be absent from Linux hosts;
# naming them first is what caused the Type3 blow-up.
_COLLECTION_SUFFIXES = ('.ttc', '.otc')


def _font_file(family: str) -> str:
    """Path of the file fontconfig would use for `family`, or '' when unknown."""
    fc_match = shutil.which('fc-match')
    if not fc_match:
        return ''
    try:
        out = subprocess.run([fc_match, '-f', '%{file}', family],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ''
    return out.stdout.strip() if out.returncode == 0 else ''


def is_embeddable(family: str) -> bool:
    """True when the resolved file is a single-face font Chromium can subset.

    A collection (`.ttc`) is not: Skia cannot subset it and emits Type3 glyph
    outlines instead. A missing family is not embeddable either, because the
    fallback may be another collection.
    """
    path = _font_file(family)
    return bool(path) and not path.lower().endswith(_COLLECTION_SUFFIXES)


@functools.cache
def resolve(candidates: tuple[str, ...], generic: str) -> str:
    """CSS font stack: embeddable families first, then the rest, then `generic`."""
    if not shutil.which('fc-match'):
        # no fontconfig: keep the caller's order, the host may still resolve it
        return ', '.join([f'"{name}"' for name in candidates] + [generic])
    embeddable = [n for n in candidates if is_embeddable(n)]
    others = [n for n in candidates if n not in embeddable]
    ordered = embeddable + others
    quoted = [f'"{name}"' if ' ' in name else name for name in ordered]
    return ', '.join(quoted + [generic])


def default_sans() -> list[str]:
    """The default sans candidates, for callers that only want to inspect them."""
    return list(DEFAULT_SANS)


def sans_stack(candidates: list[str] | None = None) -> str:
    return resolve(tuple(candidates or DEFAULT_SANS), 'sans-serif')


def mono_stack(candidates: list[str] | None = None) -> str:
    return resolve(tuple(candidates or DEFAULT_MONO), 'monospace')
