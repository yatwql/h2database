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
  python snapshot.py adopt <label>
  python snapshot.py list
  python snapshot.py diff <a> <b> [--cross]
  python snapshot.py verify <date>-<label>

Exit codes: 0 ok, 1 verification failure, 2 bad usage or missing input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil, _snapshot

MANIFEST = 'manifest.json'

SNAPSHOT_ROOT = os.path.join(
    _config.BOOK_ROOT,
    str(_config.BASE_POLICY.get('paths', {}).get('snapshots', 'data/snapshots')))


def identity() -> dict:
    """Who a snapshot belongs to: this book, the source trees it analyses, the tool.

    Two books can take a snapshot on the same day, and the same book can be rebuilt
    against a different source tree. Without this block the manifest answers neither
    question, and a comparison cannot tell an improvement from a different subject.
    """
    cfg = _config.current()
    versions = cfg.versions()
    roots = [{'label': str(root.get('label', '')), 'path': str(root.get('path', '')),
              'version': str(root.get('version', ''))} for root in cfg.source_roots()]
    return {
        'book': {'slug': cfg.merged_name, 'version': versions.get('doc', ''),
                 'edition': cfg.edition},
        'source': {'roots': roots, 'version': versions.get('source', '')},
        'tool': {'version': versions.get('tool', ''), 'config': cfg.fingerprint()},
        'language': cfg.language_code,
    }


def snapshot_dir(date: str, label: str) -> str:
    """Where a new snapshot goes: under this book's slug, so days never collide."""
    return os.path.join(SNAPSHOT_ROOT, identity()['book']['slug'], f'{date}-{label}')


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


def _copy_directory(archive_path: str, manuscript_dir: str):
    """(files, source name, source hash) for a directory tree, or None on error."""
    members = directory_members(archive_path)
    if not members:
        print(f'error: no manuscript members in {archive_path}', file=sys.stderr)
        return None
    files: dict[str, dict] = {}
    for member in members:
        destination = os.path.join(manuscript_dir, member)
        make_dir(os.path.dirname(destination))
        try:
            shutil.copyfile(os.path.join(archive_path, member), destination)
        except OSError as exc:
            print(f'error: cannot copy {member}: {exc}', file=sys.stderr)
            return None
        files[member.replace(os.sep, '/')] = facts(destination)
    return (files, os.path.relpath(archive_path, _config.BOOK_ROOT),
            source_digest(archive_path, members))


def _extract_zip(archive_path: str, manuscript_dir: str):
    """(files, source name, source hash) for a zip archive, or None on error."""
    with zipfile.ZipFile(archive_path) as archive:
        members = chapter_members(archive)
        if not members:
            print(f'error: no manuscript members in {archive_path}', file=sys.stderr)
            return None
        files: dict[str, dict] = {}
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
                return None
            files[rel.replace(os.sep, '/')] = facts(destination)
    return files, os.path.basename(archive_path), sha256_file(archive_path)


def _manifest(label: str, date: str, source_name: str, source_hash: str,
              files: dict[str, dict]) -> dict:
    return {
        'label': label,
        'date': date,
        'source_archive': source_name,
        'archive_sha256': source_hash,
        'edition': _config.current().edition,
        'identity': identity(),
        'files': files,
        'totals': {
            'files': len(files),
            'bytes': sum(item['bytes'] for item in files.values()),
            'lines': sum(item.get('lines', 0) for item in files.values()),
        },
    }


def import_snapshot(archive_path: str, label: str, date: str) -> int:
    """Copy a manuscript in as a read-only snapshot.

    The source is either a zip or a directory tree — an archived copy under
    `data/archive/<book>/<date>/manuscript` is already the right shape, so
    promoting it to a snapshot must not require zipping it again.
    """
    if not os.path.exists(archive_path):
        print(f'error: archive not found: {archive_path}', file=sys.stderr)
        return 2
    target = snapshot_dir(date, label)
    if os.path.exists(target):
        print(f'error: snapshot already exists: {target}', file=sys.stderr)
        return 2

    manuscript_dir = os.path.join(target, 'manuscript')
    make_dir(manuscript_dir)
    copied = (_copy_directory(archive_path, manuscript_dir) if os.path.isdir(archive_path)
              else _extract_zip(archive_path, manuscript_dir))
    if copied is None:
        return 2
    files, source_name, source_hash = copied

    manifest = _manifest(label, date, source_name, source_hash, files)
    _fsutil.dump_json(os.path.join(target, 'manifest.json'), manifest)
    print(f'snapshot imported: {os.path.relpath(target, _config.BOOK_ROOT)} '
          f'({manifest["totals"]["files"]} files, {manifest["totals"]["bytes"]} bytes)')
    return 0


def _artifact_files(root: str) -> dict[str, dict]:
    """Hash every file under `root`, keeping the relative name as the key."""
    files: dict[str, dict] = {}
    for current, _dirs, names in os.walk(root):
        for name in sorted(names):
            path = os.path.join(current, name)
            rel = os.path.relpath(path, root).replace(os.sep, '/')
            files[rel] = {'sha256': sha256_file(path),
                          'bytes': os.path.getsize(path)}
    return files


def import_artifacts(source: str, label: str, date: str) -> int:
    """Freeze built artifacts as a reference edition.

    A snapshot normally holds the manuscript, because a manuscript is what a later
    build reproduces from. When only the *outputs* survive — an HTML, an EPUB, two
    PDFs and the merged markdown of an edition — those are still worth keeping: they
    are the only thing a new build can be compared against, and they are read-only
    evidence rather than something to rebuild from.
    """
    if not os.path.isdir(source):
        print(f'error: not a directory: {source}', file=sys.stderr)
        return 2
    target = snapshot_dir(date, label)
    if os.path.exists(target):
        print(f'error: snapshot already exists: {target}', file=sys.stderr)
        return 2
    artifacts_dir = os.path.join(target, 'artifacts')
    make_dir(artifacts_dir)
    try:
        names = sorted(os.listdir(source))
    except OSError as exc:
        print(f'error: cannot read {source}: {exc}', file=sys.stderr)
        return 2
    for name in names:
        src = os.path.join(source, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(artifacts_dir, name))

    files = _artifact_files(artifacts_dir)
    manifest = _manifest(label, date, os.path.basename(source.rstrip(os.sep)), '', files)
    manifest['kind'] = 'artifacts'
    manifest['totals'] = {'files': len(files),
                          'bytes': sum(item['bytes'] for item in files.values()),
                          'lines': 0}
    _fsutil.dump_json(os.path.join(target, 'manifest.json'), manifest)
    print(f'artifact snapshot imported: {os.path.relpath(target, _config.BOOK_ROOT)} '
          f'({len(files)} files, {manifest["totals"]["bytes"]} bytes)')
    return 0


def snapshot_paths() -> dict[str, str]:
    """Snapshot name -> directory, both layouts; the reading lives in `lib/_snapshot.py`."""
    return _snapshot.paths(SNAPSHOT_ROOT)


def snapshots() -> list[str]:
    return sorted(snapshot_paths())


def _identity_summary(manifest: dict) -> tuple[str, str, str, str]:
    """(book, source version, tool version, config fingerprint) for display and diff."""
    identity = manifest.get('identity') or {}
    book = (identity.get('book') or {}).get('slug') or 'legacy'
    source = (identity.get('source') or {}).get('version') or '?'
    tool = (identity.get('tool') or {}).get('version') or '?'
    config = (identity.get('tool') or {}).get('config') or '?'
    return book, source, tool, config


def list_snapshots() -> int:
    found = snapshot_paths()
    if not found:
        print('no snapshots')
        return 0
    header = ('名称', '书', '源版本', '工具', '配置', '文件', '字节')
    rows = []
    for name, path in sorted(found.items()):
        manifest_path = os.path.join(path, 'manifest.json')
        if not os.path.exists(manifest_path):
            rows.append((name, '(manifest missing)', '?', '?', '?', '0', '0'))
            continue
        manifest = _fsutil.load_json(manifest_path)
        totals = manifest.get('totals', {})
        book, source, tool, config = _identity_summary(manifest)
        rows.append((name, book, source, tool, config,
                     str(totals.get('files', 0)), str(totals.get('bytes', 0))))
    widths = [max(len(str(row[i])) for row in [header, *rows]) for i in range(len(header))]
    print('  ' + '  '.join(text.ljust(widths[i]) for i, text in enumerate(header)))
    for row in rows:
        print('  ' + '  '.join(str(text).ljust(widths[i]) for i, text in enumerate(row)))
    return 0


def diff(first: str, second: str, cross: bool = False) -> int:
    """Compare two snapshots' manifests, refusing to compare different subjects."""
    paths: list[str] = []
    for label in (first, second):
        path, code = require(label)
        if code:
            return code
        paths.append(path)
    manifests = [_fsutil.load_json(os.path.join(path, 'manifest.json')) for path in paths]
    left = _identity_summary(manifests[0])
    right = _identity_summary(manifests[1])
    unknown = 'legacy' in (left[0], right[0]) or '?' in (left[1], right[1])
    if (left[:2] != right[:2] or unknown) and not cross:
        reason = ('a snapshot has no identity block, so its subject is unknown' if unknown
                  else 'different book or source tree')
        print(f'refusing to compare {first} with {second}: {reason}', file=sys.stderr)
        print(f'  {first}: book={left[0]} source={left[1]}', file=sys.stderr)
        print(f'  {second}: book={right[0]} source={right[1]}', file=sys.stderr)
        print('  pass --cross to see the comparison anyway', file=sys.stderr)
        return 2
    for label, summary in ((first, left), (second, right)):
        print(f'  {label}: book={summary[0]} source={summary[1]} '
              f'tool={summary[2]} config={summary[3]}')
    if left[:2] != right[:2]:
        print('  NOTE: cross-book or cross-source comparison; a delta is not a regression')
    left_files = manifests[0].get('files', {})
    right_files = manifests[1].get('files', {})
    changed = added = removed = 0
    for name in sorted(set(left_files) | set(right_files)):
        before, after = left_files.get(name), right_files.get(name)
        if before is None:
            print(f'  + {name}')
            added += 1
        elif after is None:
            print(f'  - {name}')
            removed += 1
        elif before.get('sha256') != after.get('sha256'):
            print(f'  ~ {name}  {before.get("bytes", 0)} -> {after.get("bytes", 0)} bytes')
            changed += 1
    print(f'  added {added}, removed {removed}, changed {changed}')
    return 0


def resolve(label: str) -> str | None:
    """Directory of a snapshot by label or by label suffix (`lib/_snapshot.resolve`)."""
    return _snapshot.resolve(label, SNAPSHOT_ROOT)


def require(label: str) -> tuple[str, int]:
    """(path, exit code) for a snapshot; non-zero when the label is ambiguous."""
    path = resolve(label)
    if path is not None:
        return path, 0
    known = ', '.join(snapshots()) or '(none)'
    print(f'error: no snapshot matches {label!r}; known: {known}', file=sys.stderr)
    return '', 2


def verify(label: str) -> int:
    target, code = require(label)
    if code:
        return code
    manifest_path = os.path.join(target, 'manifest.json')
    if not os.path.exists(manifest_path):
        print(f'error: no manifest at {manifest_path}', file=sys.stderr)
        return 2
    manifest = _fsutil.load_json(manifest_path)
    # an artifact snapshot has no manuscript: its evidence is the built files
    kind = manifest.get('kind', 'manuscript')
    base = 'artifacts' if kind == 'artifacts' else 'manuscript'
    problems: list[str] = []
    for rel, recorded in manifest.get('files', {}).items():
        path = os.path.join(target, base, rel)
        if not os.path.exists(path):
            problems.append(f'{rel}: missing')
            continue
        # artifacts include PDFs and EPUBs: hash them, never decode them
        digest = (sha256_file(path) if kind == 'artifacts'
                  else facts(path)['sha256'])
        if digest != recorded['sha256']:
            problems.append(f'{rel}: content changed since the snapshot')
    if problems:
        print(f'snapshot {label} FAILED verification:')
        for problem in problems:
            print(f'  - {problem}')
        return 1
    print(f'snapshot {label}: OK ({len(manifest.get("files", {}))} files match the manifest)')
    return 0


def adopt(label: str) -> int:
    """Give a snapshot taken before the identity block its identity, and move it home.

    An old snapshot sits flat in the root and its manifest says nothing about which book
    or source tree it came from. The only evidence left is the archive name and the
    manuscript itself, so adoption assumes *this* book and records that assumption
    (`identity.adopted_from` + `adopted_as`), which keeps the result auditable instead of
    silently claiming knowledge the snapshot never had.
    """
    path, code = require(label)
    if code:
        return code
    manifest_path = os.path.join(path, MANIFEST)
    if not os.path.exists(manifest_path):
        print(f'error: no manifest at {manifest_path}', file=sys.stderr)
        return 2
    manifest = _fsutil.load_json(manifest_path)
    if (manifest.get('identity') or {}).get('book', {}).get('slug'):
        print(f'snapshot {label} already carries an identity; nothing to adopt')
        return 0
    current = identity()
    current['adopted_from'] = os.path.relpath(path, SNAPSHOT_ROOT)
    current['adopted_as'] = current['book']['slug']
    manifest['identity'] = current
    target = os.path.join(SNAPSHOT_ROOT, current['book']['slug'], os.path.basename(path))
    if os.path.abspath(target) != os.path.abspath(path):
        if os.path.exists(target):
            print(f'error: target already exists: {target}', file=sys.stderr)
            return 2
        make_dir(os.path.dirname(target))
        try:
            shutil.move(path, target)
        except OSError as exc:
            print(f'error: cannot move {path} to {target}: {exc}', file=sys.stderr)
            return 2
    _fsutil.dump_json(os.path.join(target, MANIFEST), manifest)
    print(f'adopted {label} as {current["book"]["slug"]} '
          f'({os.path.relpath(target, SNAPSHOT_ROOT)})')
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
    artifacts = sub.add_parser('import-artifacts',
                               help='freeze built artifacts as a reference edition')
    artifacts.add_argument('source')
    artifacts.add_argument('label')
    artifacts.add_argument('--date', default=None)
    sub.add_parser('list', help='list snapshots')
    verifier = sub.add_parser('verify', help='check a snapshot against its manifest')
    verifier.add_argument('label')
    adopter = sub.add_parser('adopt', help='give a pre-identity snapshot its identity')
    adopter.add_argument('label')
    differ = sub.add_parser('diff', help='compare two snapshots manifest to manifest')
    differ.add_argument('first')
    differ.add_argument('second')
    differ.add_argument('--cross', action='store_true',
                        help='compare even when the book or source tree differs')
    args = parser.parse_args(argv)

    if args.command == 'import':
        date = args.date or '0000-00-00'
        code = import_snapshot(args.archive, args.label, date)
    elif args.command == 'import-artifacts':
        date = args.date or '0000-00-00'
        code = import_artifacts(args.source, args.label, date)
    elif args.command == 'list':
        code = list_snapshots()
    elif args.command == 'verify':
        code = verify(args.label)
    elif args.command == 'adopt':
        code = adopt(args.label)
    elif args.command == 'diff':
        code = diff(args.first, args.second, cross=args.cross)
    else:
        parser.print_help()
        return 2
    if args.json:
        print(json.dumps({'command': args.command, 'exit_code': code}, ensure_ascii=False))
    return code


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
