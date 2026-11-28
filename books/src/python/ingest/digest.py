#!/usr/bin/env python3
"""Digest a source tree into a machine-readable inventory.

The tree may be Java, Python or Rust (see ``ingest/languages/``). Languages come
from ``data/config/base.json [sources].languages``; with more than one language
the package keys are prefixed with the language (``java:<package>``) and ``by_language`` carries the
per-language totals.

Produces ``books/data/state/source-inventory.json`` for the later stages
(outline planning, chapter rendering, coverage audits).

Usage:
  python digest.py                       # digest the configured tree
  python digest.py --language python     # force one language
  python digest.py --root ../x --out /tmp/inv.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest import languages
from lib import _config, _errors, _fsutil, _log, _source_state

LOG = _log.get_logger('ingest')


def digest(root: str, selected: list[str] | None = None) -> dict:
    """Analyze ``root`` for every configured language and merge the result."""
    langs = selected or _config.source_languages()
    merged: dict = {
        'root': os.path.abspath(root),
        'source_version': _config.source_version(root),
        'tool_version': _config.tool_version(),
        'languages': langs,
        'totals': {'packages': 0, 'files': 0, 'lines': 0},
        'by_language': {},
        'packages': {},
    }
    multi = len(langs) > 1
    for lang in langs:
        analyzer = languages.get(lang)
        inventory = analyzer.analyze(root)
        merged['by_language'][lang] = inventory['totals']
        for name, package in inventory['packages'].items():
            key = f'{lang}:{name}' if multi else name
            package['language'] = lang
            merged['packages'][key] = package
        for field in ('packages', 'files', 'lines'):
            merged['totals'][field] += inventory['totals'][field]
        LOG.info('digest %s: %d packages, %d files, %d lines', lang,
                 inventory['totals']['packages'], inventory['totals']['files'],
                 inventory['totals']['lines'])
    return merged


def merge_roots(per_root: list[tuple[str, dict]]) -> dict:
    """Combine several source trees, keeping every package under its root label.

    Packages are keyed ``<label>:<name>``: two trees may hold the same class name,
    and silently collapsing them would make the coordinate gates check one and
    report the other.
    """
    merged: dict = {
        'roots': {},
        'languages': sorted({lang for _label, inv in per_root
                             for lang in (inv.get('languages') or [])}),
        'totals': {'packages': 0, 'files': 0, 'lines': 0},
        'by_root': {},
        'packages': {},
    }
    for label, inventory in per_root:
        merged['roots'][label] = inventory
        merged['by_root'][label] = dict(inventory.get('totals') or {})
        for name, package in (inventory.get('packages') or {}).items():
            merged['packages'][f'{label}:{name}'] = {**package, 'root': label}
        for field, value in (inventory.get('totals') or {}).items():
            merged['totals'][field] = merged['totals'].get(field, 0) + int(value)
    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', default=None, help='source root (default: policy)')
    parser.add_argument('--out', default=None, help='inventory path (default: data/state)')
    parser.add_argument('--language', action='append', choices=sorted(languages.ANALYZERS),
                        help='restrict to one language (repeatable)')
    parser.add_argument('--json', action='store_true', help='print a summary only')
    args = parser.parse_args(argv)

    roots = _config.current().source_roots()
    out = args.out or _config.state_path('source-inventory.json')
    if args.root or len(roots) == 1:
        root = args.root or _config.source_tree('src_main')
        inventory = digest(root, args.language)
    else:
        inventory = merge_roots([
            (entry['label'],
             digest(_config.source_tree(entry['label']), args.language))
            for entry in roots])

    if args.json:
        print(json.dumps({'root': inventory['root'], 'languages': inventory['languages'],
                          'totals': inventory['totals'],
                          'by_language': inventory['by_language']},
                         ensure_ascii=False, indent=2))
        return 0

    _fsutil.ensure_dir(out)
    if os.path.isfile(out):
        # keep the previous result so the renderer can say whether the source
        # tree actually moved, instead of asking the operator to remember.
        _fsutil.write_text(_config.state_path('source-inventory.prev.json'),
                           _fsutil.read_text(out))
    _fsutil.write_text(out, json.dumps(inventory, ensure_ascii=False, indent=2) + '\n')
    totals = inventory['totals']
    print(f"inventory -> {os.path.relpath(out, _config.BOOK_ROOT)}")
    print(f"  {_source_state.change_line(*_source_state.state_paths())[0]}")
    print(f"  languages {', '.join(inventory['languages'])}  "
          f"packages {totals['packages']}  files {totals['files']}  "
          f"lines {totals['lines']:,}")
    return 0


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
