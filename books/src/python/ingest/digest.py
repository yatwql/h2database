#!/usr/bin/env python3
"""Digest a source tree into a machine-readable inventory.

The tree may be Java, Python or Rust (see ``ingest/languages/``). Languages come
from ``data/config/base.json [sources].languages``; with more than one language
the package keys are prefixed (``java:org.h2``) and ``by_language`` carries the
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
from lib import _config, _fsutil, _log

LOG = _log.get_logger('ingest')


def digest(root: str, selected: list[str] | None = None) -> dict:
    """Analyze ``root`` for every configured language and merge the result."""
    langs = selected or _config.source_languages()
    merged: dict = {
        'root': os.path.abspath(root),
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', default=None, help='source root (default: policy)')
    parser.add_argument('--out', default=None, help='inventory path (default: data/state)')
    parser.add_argument('--language', action='append', choices=sorted(languages.ANALYZERS),
                        help='restrict to one language (repeatable)')
    parser.add_argument('--json', action='store_true', help='print a summary only')
    args = parser.parse_args(argv)

    root = args.root or _config.source_tree('src_main')
    out = args.out or os.path.join(_config.BOOK_ROOT, 'data', 'state', 'source-inventory.json')
    inventory = digest(root, args.language)

    if args.json:
        print(json.dumps({'root': inventory['root'], 'languages': inventory['languages'],
                          'totals': inventory['totals'],
                          'by_language': inventory['by_language']},
                         ensure_ascii=False, indent=2))
        return 0

    _fsutil.ensure_dir(out)
    _fsutil.write_text(out, json.dumps(inventory, ensure_ascii=False, indent=2) + '\n')
    totals = inventory['totals']
    print(f"inventory -> {os.path.relpath(out, _config.BOOK_ROOT)}")
    print(f"  languages {', '.join(inventory['languages'])}  "
          f"packages {totals['packages']}  files {totals['files']}  "
          f"lines {totals['lines']:,}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
