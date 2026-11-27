"""Where snapshots live and what a snapshot holds — one reader for every layer.

A snapshot already records everything a volume baseline needs: per-file bytes, lines and
hash, plus the totals and the identity block naming the book and the source tree. Keeping
a second copy under `data/baselines/snapshot-*.json` meant two records of the same facts,
which drift the moment one of them is regenerated. This module is the single reader:

    paths()          name -> directory, for the slug layout and the older flat one
    manifest(name)   the parsed manifest, or None when there is none
    volume(name)     files/totals in the shape the content-volume gate compares against

Governance lives one layer up (`manuscript/snapshot.py` writes manifests for the CLI,
`audit/content_volume.py` compares against them); both call these functions instead of
re-deriving the paths themselves.
"""

import os

from lib import _config, _fsutil

MANIFEST = 'manifest.json'


def root() -> str:
    """The snapshot root of the active book, read when it is used."""
    return os.path.join(_config.BOOK_ROOT,
                        str(_config.BASE_POLICY.get('paths', {}).get('snapshots',
                                                                     'data/snapshots')))


def paths(base: str | None = None) -> dict[str, str]:
    """Snapshot name -> directory, for both layouts.

    `import` writes under a book slug; snapshots taken before that sit flat in the root.
    A directory counts as a snapshot when it has a manifest, or the manuscript/artifacts
    tree a manifest would describe — a snapshot whose manifest was lost is still one.
    """
    base = base or root()
    if not os.path.isdir(base):
        return {}
    try:
        entries = sorted(os.listdir(base))
    except OSError:
        return {}
    found: dict[str, str] = {}
    for name in entries:
        path = os.path.join(base, name)
        if not os.path.isdir(path):
            continue
        if looks_like_snapshot(path):
            found[name] = path
            continue
        try:
            children = sorted(os.listdir(path))
        except OSError:
            continue
        for child in children:
            child_path = os.path.join(path, child)
            if os.path.isdir(child_path) and looks_like_snapshot(child_path):
                found[f'{name}/{child}'] = child_path
    return found


def looks_like_snapshot(path: str) -> bool:
    """Whether a directory holds a snapshot rather than being a book namespace."""
    return (os.path.exists(os.path.join(path, MANIFEST))
            or os.path.isdir(os.path.join(path, 'manuscript'))
            or os.path.isdir(os.path.join(path, 'artifacts')))


def resolve(label: str, base: str | None = None) -> str | None:
    """Directory of a snapshot by name, or by a name it ends with.

    Accepts `2026-06-11`, `2026-06-11-june` and `h2-book/2026-06-11-june`, because the
    layout changed once and the label a person types should not have to.
    """
    base = base or root()
    direct = os.path.join(base, label)
    if os.path.isdir(direct):
        return direct
    found = paths(base)
    exact = [path for name, path in found.items()
             if name == label or name.endswith(f'/{label}')]
    if len(exact) == 1:
        return exact[0]
    partial = [path for name, path in found.items() if label in name]
    return partial[0] if len(partial) == 1 else None


def manifest(label: str) -> dict | None:
    """The parsed manifest of a snapshot, or None when there is none."""
    path = resolve(label)
    if path is None:
        return None
    manifest_path = os.path.join(path, MANIFEST)
    if not os.path.isfile(manifest_path):
        return None
    return _fsutil.load_json(manifest_path)


def volume(label: str) -> dict | None:
    """A snapshot's volume facts in baseline shape, or None when unavailable.

    Artifact snapshots report files and bytes with zero lines: they are evidence of an
    edition, not something a new build reproduces line by line.
    """
    payload = manifest(label)
    if payload is None:
        return None
    files = {name: {'bytes': int(stats.get('bytes', 0)),
                    'lines': int(stats.get('lines', 0))}
             for name, stats in (payload.get('files') or {}).items()}
    total = {'files': len(files),
             'bytes': sum(item['bytes'] for item in files.values()),
             'lines': sum(item['lines'] for item in files.values())}
    return {'label': label, 'files': files, 'totals': total,
            'identity': payload.get('identity') or {}}
