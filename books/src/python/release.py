#!/usr/bin/env python3
"""Release flow: check the tree, build the artifacts, record what shipped.

Modelled on investor-review's release entry: each step is its own subcommand, the
runner stops on the first failure, and the exit code states the reason.

  python release.py status            # three versions + which artifacts exist
  python release.py gate              # P2 tier (gates + slow suite + deliver)
  python release.py publish --title "…"
                                      # gate, then write books/dist/release-<doc>.json
  python release.py manifest          # rewrite the manifest from current artifacts

Exit codes: 0 ok, 1 a step failed, 2 precondition not met (dirty tree, no tag,
missing artifact).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import _config, _fsutil, _log

PY = sys.executable
PY_ROOT = os.path.dirname(os.path.abspath(__file__))
BOOK_ROOT = _config.BOOK_ROOT
REPO_ROOT = os.path.dirname(BOOK_ROOT)
RUNNER = os.path.join(PY_ROOT, 'check_runner.py')
LOG = _log.get_logger('release')

def artifacts() -> tuple[str, ...]:
    """Delivery artifacts by basename, derived from the configured book name."""
    paths = (_config.merged_md(), _config.merged_html(), _config.merged_pdf(),
             _config.merged_print_pdf(), _config.merged_epub())
    return tuple(os.path.basename(path) for path in paths)


def status() -> dict:
    """Versions and artifact presence, as one dict (also the manifest skeleton)."""
    versions = _config.versions()
    dist = _config.DIST_DIR
    present = {}
    for name in artifacts():
        path = os.path.join(dist, name)
        present[name] = os.path.getsize(path) if os.path.isfile(path) else 0
    return {'versions': versions, 'artifacts': present,
            'dist': os.path.relpath(dist, REPO_ROOT),
            'generated': datetime.datetime.now().isoformat(timespec='seconds')}


def git(*args: str) -> str:
    try:
        result = subprocess.run(['git', *args], cwd=REPO_ROOT, capture_output=True,
                                text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return ''
    return (result.stdout or '').strip()


def tree_is_dirty() -> bool:
    return bool(git('status', '--porcelain'))


def sha256(path: str) -> str:
    """SHA-256 of one artifact; empty string when it cannot be read."""
    digest = hashlib.sha256()
    try:
        with open(path, 'rb') as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b''):
                digest.update(chunk)
    except OSError as exc:
        print(f'  [warn] cannot hash {path}: {exc}', file=sys.stderr)
        return ''
    return digest.hexdigest()


def manifest_path() -> str:
    version = _config.versions()['doc'].replace('/', '-')
    return os.path.join(_config.DIST_DIR, f'release-{version}.json')


def write_manifest(title: str = '') -> str:
    """Record versions, artifact sizes/hashes and the commit that produced them."""
    snapshot = status()
    files = {}
    for name, size in snapshot['artifacts'].items():
        if not size:
            continue
        path = os.path.join(_config.DIST_DIR, name)
        files[name] = {'bytes': size, 'sha256': sha256(path)}
    payload = {
        'title': title,
        'versions': snapshot['versions'],
        'commit': git('rev-parse', '--short', 'HEAD'),
        'generated': snapshot['generated'],
        'artifacts': files,
    }
    target = manifest_path()
    _fsutil.write_text(target, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    return target


def run_runner(mode: str) -> int:
    """Delegate to the tier runner so release and CI share one orchestration."""
    proc = subprocess.run([PY, RUNNER, '--mode', mode], cwd=REPO_ROOT, check=False)
    return proc.returncode


def cmd_status(_args: argparse.Namespace) -> int:
    snapshot = status()
    print('versions :', ', '.join(f'{k}={v}' for k, v in snapshot['versions'].items()))
    print('dist     :', snapshot['dist'])
    for name, size in snapshot['artifacts'].items():
        print(f'  {name:44s} {"missing" if not size else f"{size / 1024:.0f} KiB"}')
    print('commit   :', git('rev-parse', '--short', 'HEAD') or '(not a git checkout)')
    return 0


def cmd_gate(_args: argparse.Namespace) -> int:
    return run_runner('p2')


def cmd_manifest(_args: argparse.Namespace) -> int:
    target = write_manifest()
    print('manifest :', os.path.relpath(target, REPO_ROOT))
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    if tree_is_dirty() and not args.allow_dirty:
        print('error: working tree is dirty; commit first or pass --allow-dirty',
              file=sys.stderr)
        return 2
    code = run_runner('p2')
    if code != 0:
        print('error: the release gate failed; nothing was recorded', file=sys.stderr)
        return code
    target = write_manifest(args.title)
    version = _config.versions()['doc']
    print(f'manifest : {os.path.relpath(target, REPO_ROOT)}')
    print(f'next     : git tag -a v{version} -m "{args.title or "release"}" && git push --tags')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status', help='versions and artifact presence')
    sub.add_parser('gate', help='run the P2 tier (gates + slow suite + deliver)')
    sub.add_parser('manifest', help='rewrite the release manifest')
    publish = sub.add_parser('publish', help='gate, then write the manifest')
    publish.add_argument('--title', default='', help='release title')
    publish.add_argument('--allow-dirty', action='store_true',
                         help='publish from a dirty tree (not recommended)')
    args = parser.parse_args(argv)

    handlers = {'status': cmd_status, 'gate': cmd_gate,
                'manifest': cmd_manifest, 'publish': cmd_publish}
    LOG.info('release %s start', args.command)
    code = handlers[args.command](args)
    LOG.info('release %s done rc=%s', args.command, code)
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
