#!/usr/bin/env python3
"""Manage read-only historical manuscript snapshots.

A snapshot is a frozen copy of another book's manuscript kept for comparison —
never part of the build. Layout:

  data/snapshots/<date>-<label>/manuscript/*.md
  data/snapshots/<date>-<label>/manifest.json

The manifest records where the snapshot came from (archive path and SHA-256),
when it was taken, and the per-file size/line/hash facts, so a comparison never
has to trust the archive file still being around.

Usage:
  python snapshot.py import <archive.zip> <label> [--date YYYYMMDD]
  python snapshot.py list
  python snapshot.py verify <date>-<label>
  python snapshot.py baseline <date>-<label>

Exit codes: 0 ok, 1 verification failure, 2 bad usage or missing input.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil

SNAPSHOT_ROOT = os.path.join(
    _config.BOOK_ROOT,
    str(_config.BASE_POLICY.get('paths', {}).get('snapshots', 'data/snapshots')))


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    try:
        with open(path, 'rb') as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(block)
    except OSError as exc:
        print(f'error: cannot hash {path}: {exc}', file=sys.stderr)
        return ''
    return digest.hexdigest()


def make_dir(path: str) -> None:
    """Create a directory tree (lib._fsutil.ensure_dir takes a file path)."""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        print(f'error: cannot create {path}: {exc}', file=sys.stderr)
        raise SystemExit(2) from exc


def facts(path: str) -> dict[str, int | str]:
    text = _fsutil.read_text(path)
    return {'bytes': len(text.encode('utf-8')),
            'lines': len(text.splitlines()),
            'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}


def chapter_members(archive: zipfile.ZipFile) -> list[str]:
    """Markdown members that belong to the manuscript (chapters and matter)."""
    keep = []
    for name in archive.namelist():
        if not name.endswith('.md') or name.endswith('/'):
            continue
        if _belongs_to_manuscript(name):
            keep.append(name)
    return sorted(keep)


def _belongs_to_manuscript(name: str) -> bool:
    """The same rule for a zip member and for a file inside a directory."""
    base = os.path.basename(name)
    parent = os.path.basename(os.path.dirname(name))
    is_chapter = bool(re.match(r'^ch\d', base)) or base.startswith(('cover.', 'appendix'))
    return is_chapter or parent in ('front', 'back')


def directory_members(root: str) -> list[str]:
    """Manuscript files inside a directory tree, as paths relative to ``root``."""
    keep: list[str] = []
    for base, _dirs, names in os.walk(root):
        for name in names:
            if not name.endswith('.md'):
                continue
            rel = os.path.relpath(os.path.join(base, name), root)
            if _belongs_to_manuscript(rel.replace(os.sep, '/')):
                keep.append(rel)
    return sorted(keep)


def source_digest(path: str, members: list[str]) -> str:
    """Content digest of an imported tree, recorded in place of a zip hash."""
    digest = hashlib.sha256()
    for rel in members:
        digest.update(rel.replace(os.sep, '/').encode('utf-8'))
        digest.update(str(facts(os.path.join(path, rel))['sha256']).encode('utf-8'))
    return digest.hexdigest()


def import_snapshot(archive_path: str, label: str, date: str) -> int:
    """Copy a manuscript in as a read-only snapshot.

    The source is either a zip or a directory tree — an archived copy under
    `data/archive/<book>/<date>/manuscript` is already the right shape, so
    promoting it to a snapshot must not require zipping it again.
    """
    if not os.path.exists(archive_path):
        print(f'error: archive not found: {archive_path}', file=sys.stderr)
        return 2
    target = os.path.join(SNAPSHOT_ROOT, f'{date}-{label}')
    if os.path.exists(target):
        print(f'error: snapshot already exists: {target}', file=sys.stderr)
        return 2
    manuscript_dir = os.path.join(target, 'manuscript')
    make_dir(manuscript_dir)
    files: dict[str, dict] = {}
    if os.path.isdir(archive_path):
        members = directory_members(archive_path)
        if not members:
            print(f'error: no manuscript members in {archive_path}', file=sys.stderr)
            return 2
        for member in members:
            destination = os.path.join(manuscript_dir, member)
            make_dir(os.path.dirname(destination))
            try:
                shutil.copyfile(os.path.join(archive_path, member), destination)
            except OSError as exc:
                print(f'error: cannot copy {member}: {exc}', file=sys.stderr)
                return 2
            files[member.replace(os.sep, '/')] = facts(destination)
        source_name = os.path.relpath(archive_path, _config.BOOK_ROOT)
        source_hash = source_digest(archive_path, members)
    else:
        with zipfile.ZipFile(archive_path) as archive:
            members = chapter_members(archive)
            if not members:
                print(f'error: no manuscript members in {archive_path}', file=sys.stderr)
                return 2
            for member in members:
                rel = os.path.basename(member)
                parent = os.path.basename(os.path.dirname(member))
                if parent in ('front', 'back'):
                    rel = os.path.join(parent, rel)
                destination = os.path.join(manuscript_dir, rel)
                make_dir(os.path.dirname(destination))
                try:
                    with archive.open(member) as source, open(destination, 'wb') as out:
                        shutil.copyfileobj(source, out)
                except (OSError, zipfile.BadZipFile) as exc:
                    print(f'error: cannot extract {member}: {exc}', file=sys.stderr)
                    return 2
                files[rel.replace(os.sep, '/')] = facts(destination)
        source_name = os.path.basename(archive_path)
        source_hash = sha256_file(archive_path)
    manifest = {
        'label': label,
        'date': date,
        'source_archive': source_name,
        'archive_sha256': source_hash,
        'edition': _config.current().edition,
        'files': files,
        'totals': {
            'files': len(files),
            'bytes': sum(item['bytes'] for item in files.values()),
            'lines': sum(item['lines'] for item in files.values()),
        },
    }
    _fsutil.dump_json(os.path.join(target, 'manifest.json'), manifest)
    print(f'snapshot imported: {os.path.relpath(target, _config.BOOK_ROOT)} '
          f'({manifest["totals"]["files"]} files, {manifest["totals"]["bytes"]} bytes)')
    return 0


def snapshots() -> list[str]:
    if not os.path.isdir(SNAPSHOT_ROOT):
        return []
    try:
        entries = os.listdir(SNAPSHOT_ROOT)
    except OSError as exc:
        print(f'error: cannot list {SNAPSHOT_ROOT}: {exc}', file=sys.stderr)
        return []
    return sorted(name for name in entries
                  if os.path.isdir(os.path.join(SNAPSHOT_ROOT, name)))


def list_snapshots() -> int:
    found = snapshots()
    if not found:
        print('no snapshots')
        return 0
    for name in found:
        manifest_path = os.path.join(SNAPSHOT_ROOT, name, 'manifest.json')
        if not os.path.exists(manifest_path):
            print(f'  {name}  (manifest missing)')
            continue
        manifest = _fsutil.load_json(manifest_path)
        totals = manifest.get('totals', {})
        print(f'  {name}  {totals.get("files", 0)} files / '
              f'{totals.get("bytes", 0)} bytes / from {manifest.get("source_archive", "?")}')
    return 0


def resolve(label: str) -> str | None:
    """Directory of a snapshot by label or by label suffix.

    ``import`` stores ``<date>-<label>``, so the same snapshot answers to both
    "june-2026" and "2026-06-11-june-2026"; requiring one spelling in the CLI and
    the other in the human's head is how a working snapshot looks missing.
    """
    direct = os.path.join(SNAPSHOT_ROOT, label)
    if os.path.isdir(direct):
        return direct
    matches = sorted(p for p in glob.glob(os.path.join(SNAPSHOT_ROOT, f'*{label}'))
                     if os.path.isdir(p))
    return matches[0] if len(matches) == 1 else None


def require(label: str) -> tuple[str, int]:
    """(path, exit code) for a snapshot; non-zero when the label is ambiguous."""
    path = resolve(label)
    if path is not None:
        return path, 0
    known = ', '.join(sorted(os.path.basename(p) for p in
                             glob.glob(os.path.join(SNAPSHOT_ROOT, '*')))) or '(none)'
    print(f'error: no snapshot matches {label!r}; known: {known}', file=sys.stderr)
    return '', 2


def verify(label: str) -> int:
    target = os.path.join(SNAPSHOT_ROOT, label)
    manifest_path = os.path.join(target, 'manifest.json')
    if not os.path.exists(manifest_path):
        print(f'error: no manifest at {manifest_path}', file=sys.stderr)
        return 2
    manifest = _fsutil.load_json(manifest_path)
    problems: list[str] = []
    for rel, recorded in manifest.get('files', {}).items():
        path = os.path.join(target, 'manuscript', rel)
        if not os.path.exists(path):
            problems.append(f'{rel}: missing')
            continue
        current = facts(path)
        if current['sha256'] != recorded['sha256']:
            problems.append(f'{rel}: content changed since the snapshot')
    if problems:
        print(f'snapshot {label} FAILED verification:')
        for problem in problems:
            print(f'  - {problem}')
        return 1
    print(f'snapshot {label}: OK ({len(manifest.get("files", {}))} files match the manifest)')
    return 0


def baseline(label: str) -> int:
    """Volume baseline for the snapshot, for comparing an old draft to the current one."""
    root, code = require(label)
    if code:
        return code
    target = os.path.join(root, 'manuscript')
    if not os.path.isdir(target):
        print(f'error: no snapshot manuscript at {target}', file=sys.stderr)
        return 2
    files: dict[str, dict] = {}
    for root, _dirs, names in os.walk(target):
        for name in sorted(names):
            if not name.endswith('.md'):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, target).replace(os.sep, '/')
            stats = facts(path)
            files[rel] = {'bytes': stats['bytes'], 'lines': stats['lines']}
    payload = {'snapshot': label, 'files': files,
               'totals': {'files': len(files),
                          'bytes': sum(item['bytes'] for item in files.values()),
                          'lines': sum(item['lines'] for item in files.values())}}
    out = os.path.join(_config.BOOK_ROOT, 'data', 'baselines', f'snapshot-{label}.json')
    _fsutil.dump_json(out, payload)
    print(f'baseline written: {os.path.relpath(out, _config.BOOK_ROOT)} '
          f'({payload["totals"]["files"]} files, {payload["totals"]["bytes"]} bytes)')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true', help='machine-readable summary')
    sub = parser.add_subparsers(dest='command')
    importer = sub.add_parser('import', help='extract a manuscript archive into a snapshot')
    importer.add_argument('archive')
    importer.add_argument('label')
    importer.add_argument('--date', default=None)
    sub.add_parser('list', help='list snapshots')
    verifier = sub.add_parser('verify', help='check a snapshot against its manifest')
    verifier.add_argument('label')
    baseliner = sub.add_parser('baseline', help='write a volume baseline for a snapshot')
    baseliner.add_argument('label')
    args = parser.parse_args(argv)

    if args.command == 'import':
        date = args.date or '0000-00-00'
        code = import_snapshot(args.archive, args.label, date)
    elif args.command == 'list':
        code = list_snapshots()
    elif args.command == 'verify':
        code = verify(args.label)
    elif args.command == 'baseline':
        code = baseline(args.label)
    else:
        parser.print_help()
        return 2
    if args.json:
        print(json.dumps({'command': args.command, 'exit_code': code}, ensure_ascii=False))
    return code


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
