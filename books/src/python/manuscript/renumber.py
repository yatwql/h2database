#!/usr/bin/env python3
"""Renumber an edition's chapters and keep the cross-references in step.

An edition that drops chapters cannot keep the old numbers: ``structure.py`` wants
H1 numbers to run ``1..N``. So the surviving chapters are renumbered, the mapping
is written to ``state/<edition>/renumber.json``, and every reference that names a
chapter — ``详见第X章《…》``, the glossary's chapter pointer, index entries — is
rewritten through that mapping. The mapping is the record: a cross-version
comparison reads it instead of guessing.

Usage::

    python manuscript/renumber.py --write        # derive and store the mapping
    python manuscript/renumber.py --apply        # rewrite references in the edition
    python manuscript/renumber.py --dry-run      # show what would change
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

_sys = sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil  # noqa: E402

REF_RE = re.compile(r'详见第(\d+)章《([^》]+)》')
BARE_RE = re.compile(r'(第)(\d+)(章)')
MAPPING_NAME = 'renumber.json'


def mapping_of(base: dict[str, list[int]],
               target: dict[str, list[int]]) -> dict[int, int]:
    """Old chapter number -> new chapter number, per surviving chapter file."""
    out: dict[int, int] = {}
    for name, new_numbers in target.items():
        for old, new in zip(base.get(name) or [], new_numbers, strict=False):
            try:
                old_number, new_number = int(old), int(new)
            except (TypeError, ValueError):
                continue
            if old_number != new_number:
                out[old_number] = new_number
    return out


def mapping_for(edition: str) -> dict[int, int]:
    """Mapping for one edition of the active book."""
    cfg = _config.current()
    return mapping_of(cfg.chapter_numbering_for(None), cfg.chapter_numbering_for(edition))


def mapping_path() -> str:
    """Where the mapping lives for the active edition."""
    return _config.state_path(MAPPING_NAME)


def _as_int(value: str) -> int:
    """A regex-captured number; a malformed capture counts as zero."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def rewrite_refs(text: str, mapping: dict[int, int]) -> str:
    """Rewrite every chapter reference through ``mapping``."""
    if not mapping:
        return text

    def by_chapter(match: re.Match) -> str:
        old = _as_int(match.group(1))
        return f'详见第{mapping.get(old, old)}章《{match.group(2)}》'

    def bare(match: re.Match) -> str:
        old = _as_int(match.group(2))
        return f'{match.group(1)}{mapping.get(old, old)}{match.group(3)}'

    return BARE_RE.sub(bare, REF_RE.sub(by_chapter, text))


def edition_files() -> list[str]:
    """Manuscript files that belong to the active edition, in reading order."""
    return _config.current().all_manuscript_files()


def apply(dry_run: bool = False) -> dict:
    """Write the mapping and rewrite references; returns what changed."""
    cfg = _config.current()
    if not cfg.edition:
        raise SystemExit('error: 未选版本；先用 [editions] 声明并用 --edition 指定')
    mapping = mapping_for(cfg.edition)
    report = {'edition': cfg.edition, 'mapping': mapping, 'files': 0, 'refs': 0,
              'dry_run': dry_run}
    if mapping and not dry_run:
        _fsutil.ensure_dir(mapping_path())
        _fsutil.write_text(mapping_path(),
                           json.dumps({str(k): v for k, v in sorted(mapping.items())},
                                      ensure_ascii=False, indent=2) + '\n')
    for path in edition_files():
        if not os.path.isfile(path):
            continue
        text = _fsutil.read_text(path)
        updated = rewrite_refs(text, mapping)
        if updated == text:
            continue
        report['files'] += 1
        report['refs'] += len(REF_RE.findall(text)) + len(BARE_RE.findall(text))
        if not dry_run:
            _fsutil.write_text(path, updated)
    return report


def main(argv: list[str] | None = None) -> int:
    _fsutil.pin_stdout_utf8()
    parser = argparse.ArgumentParser(description='重编号版本的章号并改写引用')
    parser.add_argument('--apply', action='store_true', help='改写正文引用')
    parser.add_argument('--write', action='store_true', help='只写章号映射')
    parser.add_argument('--dry-run', action='store_true', help='只打印动作')
    parser.add_argument('--json', action='store_true', help='机器可读输出')
    args = parser.parse_args(argv)
    if not (args.apply or args.write):
        parser.error('需要 --write 或 --apply')
    try:
        report = apply(dry_run=args.dry_run or args.write and not args.apply)
    except SystemExit as exc:
        print(exc)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(f"版本 {report['edition']}：映射 {len(report['mapping'])} 条，"
              f"改写 {report['files']} 个文件、{report['refs']} 处引用"
              + ('（dry-run）' if report['dry_run'] else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
