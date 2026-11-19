#!/usr/bin/env python3
"""Digest a Java source tree into a machine-readable inventory.

Produces ``books/data/state/source-inventory.json``: per package file counts,
line counts, class-level javadoc summaries, public types and their public
methods. Every later stage (outline planning, chapter generation, coverage
audit) reads this instead of re-parsing the tree.

Usage:
  python digest_source.py                     # digest the configured source tree
  python digest_source.py --root ../h2/src/main --out /tmp/inv.json
  python digest_source.py --json              # print a compact summary
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

PKG_RE = re.compile(r'^\s*package\s+([\w.]+)\s*;', re.MULTILINE)
PUBLIC_TYPE_RE = re.compile(
    r'^\s*public\s+(?:final\s+|abstract\s+|sealed\s+|non-sealed\s+)*'
    r'(?:class|interface|enum|record)\s+(\w+)', re.MULTILINE)
ANY_TYPE_RE = re.compile(r'^\s*(?:public\s+)?(?:final\s+|abstract\s+)*(?:class|interface|enum|record)\s+(\w+)', re.MULTILINE)
PUBLIC_METHOD_RE = re.compile(
    r'^\s*public\s+(?:static\s+|final\s+|synchronized\s+|native\s+|default\s+|abstract\s+)*'
    r'[\w<>\[\],.?\s]+\s+(\w+)\s*\(', re.MULTILINE)
CLASS_JAVADOC_RE = re.compile(r'/\*\*([\s\S]*?)\*/\s*$')
TAG_RE = re.compile(r'<[^>]+>')


def _first_sentence(javadoc: str) -> str:
    """Plain first sentence of a javadoc block, tags and stars stripped."""
    body = ' '.join(line.strip().lstrip('*').strip() for line in javadoc.split('\n'))
    body = TAG_RE.sub(' ', body)
    body = re.sub(r'@\w+.*$', '', body)
    body = ' '.join(body.split())
    if not body:
        return ''
    cut = re.split(r'(?<=[.!?])\s+', body)[0]
    return cut[:220]


def _package_javadoc(path: str) -> str:
    if not os.path.isfile(path):
        return ''
    text = _fsutil.read_text(path)
    m = re.search(r'/\*\*([\s\S]*?)\*/', text)
    return _first_sentence(m.group(1)) if m else ''


def _class_doc(text: str) -> str:
    for m in CLASS_JAVADOC_RE.finditer(text):
        doc = _first_sentence(m.group(1))
        if doc:
            return doc
    return ''


def digest(root: str) -> dict:
    """Walk ``root`` and return the inventory structure."""
    packages: dict[str, dict] = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        java = [f for f in filenames if f.endswith('.java')]
        if not java:
            continue
        rel = os.path.relpath(dirpath, root).replace(os.sep, '.')
        pkg = 'default' if rel == '.' else rel
        entry = packages.setdefault(pkg, {
            'path': os.path.relpath(dirpath, root).replace(os.sep, '/'),
            'summary': _package_javadoc(os.path.join(dirpath, 'package-info.java')),
            'files': 0, 'lines': 0, 'classes': [],
        })
        for name in sorted(java):
            if name == 'package-info.java':
                continue
            path = os.path.join(dirpath, name)
            text = _fsutil.read_text(path)
            lines = text.count('\n') + 1
            entry['files'] += 1
            entry['lines'] += lines
            public = PUBLIC_TYPE_RE.findall(text)
            methods = PUBLIC_METHOD_RE.findall(text)
            entry['classes'].append({
                'name': name[:-5],
                'file': os.path.relpath(path, root).replace(os.sep, '/'),
                'lines': lines,
                'public': bool(public),
                'kind': 'public' if public else 'internal',
                'summary': _class_doc(text),
                'public_methods': len(methods),
                'api': sorted(set(methods))[:24],
            })
    for entry in packages.values():
        entry['classes'].sort(key=lambda c: -c['lines'])
        entry['public_classes'] = [c['name'] for c in entry['classes'] if c['public']]
    return {
        'root': os.path.abspath(root),
        'totals': {
            'packages': len(packages),
            'files': sum(p['files'] for p in packages.values()),
            'lines': sum(p['lines'] for p in packages.values()),
        },
        'packages': dict(sorted(packages.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', default=None, help='Java source root (default: policy)')
    parser.add_argument('--out', default=None, help='inventory path (default: data/state)')
    parser.add_argument('--json', action='store_true', help='print a summary only')
    args = parser.parse_args(argv)

    root = args.root or _config.source_tree('src_main')
    out = args.out or os.path.join(_config.BOOK_ROOT, 'data', 'state', 'source-inventory.json')
    inventory = digest(root)

    if args.json:
        print(json.dumps({'root': inventory['root'], 'totals': inventory['totals'],
                          'top_packages': sorted(
                              ((p, v['lines']) for p, v in inventory['packages'].items()),
                              key=lambda kv: -kv[1])[:10]},
                         ensure_ascii=False, indent=2))
        return 0

    _fsutil.ensure_dir(out)
    _fsutil.write_text(out, json.dumps(inventory, ensure_ascii=False, indent=2) + '\n')
    totals = inventory['totals']
    print(f"inventory -> {os.path.relpath(out, _config.BOOK_ROOT)}")
    print(f"  packages {totals['packages']}  files {totals['files']}  lines {totals['lines']:,}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
