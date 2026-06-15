#!/usr/bin/env python3
"""
Figure cluster detector (v5.5 / U16 helper).

Identifies "figure clusters" — groups of three or more figures whose captions
appear within a 50-line window — so authors can decide whether to add a
bridge sentence introducing the cluster as a coordinated set of views.

Usage:
  python _audit_figure_clusters.py                # default 3+ figures / 50 lines
  python _audit_figure_clusters.py --min 4        # require 4+ figures
  python _audit_figure_clusters.py --window 80    # widen the line window
  python _audit_figure_clusters.py --json         # machine-readable
  python _audit_figure_clusters.py --has-bridge   # report which clusters
                                                  # already have a bridge sentence

The "bridge sentence" detection is heuristic: a cluster has a bridge if the
non-blank line preceding its first figure caption contains one of the bridge
hint phrases (`以下三张图`, `下面三张`, `以下 N 张`, `三张图共同`, etc.).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from glob import glob
from typing import Iterable

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))

FIG_RE = re.compile(r'^\*\*图 ([A-Z0-9]+-\d+[a-z]*):\s*(.+?)\*\*\s*$')

# Heuristic patterns that indicate the author has already written a cluster
# bridge sentence. Conservative — false negatives are OK (script just suggests
# a bridge that's already there); false positives would let real clusters
# slip through.
BRIDGE_HINTS = (
    '以下三张图', '以下三张', '以下 三',
    '下面三张图', '下面三张',
    '以下四张图', '下面四张图',
    '三张图共同', '四张图共同',
    '三张图分别', '四张图分别',
    '这组图', '这组示意图', '这三张',
    '下列三', '下列四', '下列 N',
    '共同呈现', '共同刻画', '共同展示',
    '从三个视角', '从四个视角', '三个视角',
    '将这', '本组图',
)


def _strip_fences(lines: list[str]) -> list[bool]:
    inside = [False] * len(lines)
    fence_open = False
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith('```'):
            fence_open = not fence_open
            inside[i] = True
            continue
        inside[i] = fence_open
    return inside


def _has_bridge(lines: list[str], cluster_start: int) -> tuple[bool, str]:
    """Inspect the prose preceding the cluster's first figure for a bridge.

    Walks up to 8 non-blank lines backward; if any contains one of the
    BRIDGE_HINTS substrings, the cluster is considered already-bridged.
    """
    looked = 0
    i = cluster_start - 1
    while i >= 0 and looked < 8:
        raw = lines[i]
        stripped = raw.strip()
        # Skip blanks and code-fence boundaries
        if not stripped or stripped.startswith('```') or stripped.startswith('**图'):
            i -= 1
            continue
        for hint in BRIDGE_HINTS:
            if hint in stripped:
                return True, hint
        # Only the most recent prose paragraph is treated as candidate bridge;
        # a heading (### / ## / #) ends the lookback.
        if stripped.startswith('#'):
            return False, ''
        looked += 1
        i -= 1
    return False, ''


def find_clusters(path: str, min_figs: int, window: int) -> list[dict]:
    """Detect clusters in one file.

    A cluster is an unbroken sequence of >= `min_figs` figure captions where
    each consecutive pair sits within `window` lines of each other.
    """
    with open(path, 'r', encoding='utf-8') as fh:
        lines = fh.readlines()
    in_fence = _strip_fences(lines)

    fig_lines: list[tuple[int, str]] = []  # (1-indexed line, fig id)
    for idx, raw in enumerate(lines):
        if in_fence[idx]:
            continue
        m = FIG_RE.match(raw.rstrip('\n'))
        if m:
            fig_lines.append((idx + 1, m.group(1)))

    if not fig_lines:
        return []

    clusters: list[list[tuple[int, str]]] = []
    cur: list[tuple[int, str]] = [fig_lines[0]]
    for ln, fid in fig_lines[1:]:
        if ln - cur[-1][0] <= window:
            cur.append((ln, fid))
        else:
            if len(cur) >= min_figs:
                clusters.append(cur)
            cur = [(ln, fid)]
    if len(cur) >= min_figs:
        clusters.append(cur)

    out = []
    for c in clusters:
        first_line0 = c[0][0] - 1
        bridged, hint = _has_bridge(lines, first_line0)
        out.append({
            'first_line': c[0][0],
            'last_line': c[-1][0],
            'span': c[-1][0] - c[0][0],
            'count': len(c),
            'fig_ids': [fid for _, fid in c],
            'bridged': bridged,
            'bridge_hint': hint,
        })
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--min', type=int, default=3,
                        help='minimum figure count to qualify as cluster (default 3)')
    parser.add_argument('--window', type=int, default=50,
                        help='max line distance between consecutive figures (default 50)')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--has-bridge', action='store_true',
                        help='only print clusters that already have a bridge')
    parser.add_argument('--needs-bridge', action='store_true',
                        help='only print clusters lacking a bridge')
    args = parser.parse_args(argv)

    paths = sorted(glob(os.path.join(DOCS_DIR, 'ch*.md')))
    paths.extend(sorted(glob(os.path.join(DOCS_DIR, 'appendix-*.md'))))

    total_clusters = 0
    total_bridged = 0
    by_file: dict[str, list[dict]] = {}
    for p in paths:
        cl = find_clusters(p, args.min, args.window)
        if cl:
            by_file[p] = cl
            total_clusters += len(cl)
            total_bridged += sum(1 for c in cl if c['bridged'])

    if args.json:
        payload = {
            'min_figs': args.min,
            'window_lines': args.window,
            'total_clusters': total_clusters,
            'bridged': total_bridged,
            'unbridged': total_clusters - total_bridged,
            'files': {os.path.relpath(p, DOCS_DIR).replace(os.sep, '/'): cl
                      for p, cl in by_file.items()},
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print('=' * 72)
    print(f'图簇检测  min={args.min}  window={args.window}  '
          f'总数={total_clusters}  已桥接={total_bridged}  '
          f'待桥接={total_clusters - total_bridged}')
    print('=' * 72)
    for path, cl in sorted(by_file.items()):
        rel = os.path.relpath(path, DOCS_DIR).replace(os.sep, '/')
        items = cl
        if args.has_bridge:
            items = [c for c in cl if c['bridged']]
        if args.needs_bridge:
            items = [c for c in cl if not c['bridged']]
        if not items:
            continue
        print(f'\n## {rel}  ({len(items)} 处)')
        for c in items:
            tag = '✓ 已桥接' if c['bridged'] else '○ 待桥接'
            ids = ', '.join(c['fig_ids'])
            hint = f"  hint=「{c['bridge_hint']}」" if c['bridged'] else ''
            print(f"  L{c['first_line']:>5}-L{c['last_line']:<5} "
                  f"{c['count']} 张  span={c['span']:>3}行  {tag}{hint}")
            print(f"           figs: {ids}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
