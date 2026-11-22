#!/usr/bin/env python3
"""Plan the manuscript outline from the source inventory (stage 1).

Reads ``books/data/state/source-inventory.json`` (produced by
``digest.py``) plus the chapter -> package mapping in
``books/data/book.toml`` and writes ``books/data/state/outline.json``:
per chapter, the packages it must cover with their size and key classes.

Usage:
  python outline.py            # write the outline
  python outline.py --json     # print it
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

INVENTORY = _config.state_path('source-inventory.json')
OUTLINE = _config.state_path('outline.json')


def ownership_conflicts(mapping: dict[str, list[str]]) -> dict[str, list[str]]:
    """Packages claimed by more than one chapter (single-owner rule)."""
    owners: dict[str, list[str]] = {}
    for chapter, packages in mapping.items():
        for package in packages:
            owners.setdefault(package, []).append(chapter)
    return {package: chapters for package, chapters in owners.items()
            if len(chapters) > 1}


def build_outline() -> dict:
    try:
        inventory = json.loads(_fsutil.read_text(INVENTORY))
    except json.JSONDecodeError as exc:
        raise SystemExit(f'error: invalid inventory {INVENTORY}: {exc}') from exc
    packages = inventory['packages']
    mapping = _config.chapter_packages()
    chapters = []
    for name in _config.chapter_names(include_cover=False):
        wanted = mapping.get(name, [])
        resolved = {}
        missing = []
        for pkg in wanted:
            entry = packages.get(pkg)
            if entry is None:
                missing.append(pkg)
                continue
            resolved[pkg] = {
                'lines': entry['lines'],
                'files': entry['files'],
                'summary': entry['summary'],
                'depends_on': entry.get('depends_on', {}),
                'key_classes': [
                    {'name': c['name'], 'lines': c['lines'], 'summary': c['summary'],
                     'public_methods': c['public_methods'],
                     'rel': c.get('rel', ''), 'api': c.get('api', []),
                     'api_lines': c.get('api_lines', {})}
                    for c in entry['classes'][:6]
                ],
            }
        chapters.append({
            'file': name,
            'packages': resolved,
            'missing_packages': missing,
            'source_lines': sum(p['lines'] for p in resolved.values()),
        })
    conflicts = ownership_conflicts(mapping)
    return {
        'ownership_conflicts': conflicts,
        'source_root': inventory['root'],
        'source_totals': inventory['totals'],
        'chapters': chapters,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true', help='print instead of writing')
    args = parser.parse_args(argv)

    if not os.path.isfile(INVENTORY):
        print(f'error: run digest.py first ({INVENTORY} missing)', file=sys.stderr)
        return 2

    outline = build_outline()
    if args.json:
        print(json.dumps(outline, ensure_ascii=False, indent=2))
        return 0

    _fsutil.ensure_dir(OUTLINE)
    _fsutil.write_text(OUTLINE, json.dumps(outline, ensure_ascii=False, indent=2) + '\n')
    print(f'outline -> {os.path.relpath(OUTLINE, _config.BOOK_ROOT)}')
    if outline['ownership_conflicts']:
        print('warning: packages claimed by several chapters:')
        for package, chapters in sorted(outline['ownership_conflicts'].items()):
            print(f'  {package}: {", ".join(chapters)}')
    for ch in outline['chapters']:
        mark = ' [missing: ' + ', '.join(ch['missing_packages']) + ']' if ch['missing_packages'] else ''
        print(f"  {ch['file']:<34} {len(ch['packages']):>2} pkgs  "
              f"{ch['source_lines']:>7,} lines{mark}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
