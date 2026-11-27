#!/usr/bin/env python3
"""Inventory the accepted-state baselines: what each one records, and whether it is stale.

`data/baselines/` holds eleven files written by different gates over two years of
iterations, in three shapes (`accepted` lists, per-file counts, and two one-off
structures). Reading the directory told you nothing about which gate owns a file or
whether it still means anything, so this command answers that in one table:

    文件 / 形态 / 条数 / 更新 / 记录什么

It is read-only: nothing here writes a baseline, because a baseline changes only through
its own gate's `--update-baseline` after review.

Usage:
  python baselines.py            table for humans
  python baselines.py --json     the same rows, machine-readable
  python baselines.py --check    non-zero when a baseline is empty, unreadable or unowned

Exit codes: 0 ok, 1 --check found something worth fixing, 2 bad usage.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil

# filename -> (shape, gate that owns it, what it records). The shape decides how the
# entries are counted; the owner is the script whose `--update-baseline` rewrites it.
KNOWN = {
    'ascii-baseline.json': ('accepted', 'audit/diagrams.py',
                            'ASCII 图存量违规（超宽行等），键含内容哈希'),
    'captions-findings.json': ('accepted', 'audit/captions.py',
                               '图注质量存量：缺动词、过长、含糊尾词'),
    'content-depth-findings.json': ('accepted', 'audit/content_depth.py',
                                    '内容深度存量：术语未入表、摘录漂移、前置知识无指路'),
    'content-volume.json': ('records', 'audit/content_volume.py',
                            '篇幅与交付体积下限，以及经批准的下调记录'),
    'coverage.json': ('counts', 'make.py cover',
                      '每文件覆盖率下限（百分比）'),
    'editorial.json': ('counts', 'audit/editorial.py',
                       '编辑要素计数：学习目标、要点回顾、误区、表格张数'),
    'loose-assertions.json': ('accepted', 'audit/test_redundancy.py',
                              '断言过松的存量用例'),
    'perf-baseline.json': ('records', 'audit/perf_baseline.py',
                           '门禁耗时读数，用于发现变慢'),
    'readability-box-drawing.json': ('counts', 'audit/readability.py',
                                     '框线闭合告警的每文件计数'),
    'source-symbol-baseline.json': ('accepted', 'audit/source_refs.py',
                                    '承认的符号漂移（Class.method 断言）'),
    'style-rules-baseline.json': ('accepted', 'audit/style_rules.py',
                                  '文风规则存量违规（术语、间距、标点）'),
}


def baseline_dir() -> str:
    """Where this book keeps its accepted state, resolved when it is used."""
    return _config.baseline_dir()


def _stamp(value) -> str:
    """A short date for the table, whether the file records one or a review record.

    The reviewed baselines keep `{by, at, commit, reason}` — the reason matters and the
    table shows only the date, because a release review reads the file, not this list.
    """
    if isinstance(value, dict):
        return str(value.get('at') or '?')[:10]
    return str(value or '?')


def rows() -> list[dict]:
    """One row per baseline file: shape, count, last update and owner."""
    folder = baseline_dir()
    try:
        names = sorted(name for name in os.listdir(folder) if name.endswith('.json'))
    except FileNotFoundError:
        return []
    out: list[dict] = []
    for name in names:
        shape, owner, purpose = KNOWN.get(name, ('unknown', '?', '未登记的基线文件'))
        path = os.path.join(folder, name)
        try:
            payload = _fsutil.load_json(path)
        except (_errors.ToolError, OSError, ValueError) as exc:
            out.append({'file': name, 'shape': shape, 'count': None, 'updated': '?',
                        'owner': owner, 'purpose': purpose, 'problem': f'无法读取：{exc}'})
            continue
        if shape == 'accepted':
            count = len(payload.get('accepted') or [])
        elif shape == 'counts':
            count = len(payload.get('files') or {})
        elif shape == 'records':
            count = len(payload.get('steps') or payload.get('manuscript', {}).get('files') or {})
        else:
            count = None
        out.append({
            'file': name, 'shape': shape, 'count': count,
            'updated': _stamp(payload.get('updated') or payload.get('reviewed')),
            'owner': owner, 'purpose': purpose, 'problem': '',
        })
    return out


def problems(rows_: list[dict]) -> list[str]:
    """Baselines that are unreadable, unowned, or accepted nothing at all."""
    found: list[str] = []
    for row in rows_:
        if row['problem']:
            found.append(f'{row["file"]}: {row["problem"]}')
        elif row['shape'] == 'unknown':
            found.append(f'{row["file"]}: no gate claims it (see KNOWN in this module)')
        elif row['count'] == 0:
            found.append(f'{row["file"]}: empty; delete it and let the gate start clean')
    return found


def render(rows_: list[dict]) -> str:
    header = ('文件', '形态', '条数', '更新', '门禁', '记录什么')
    cells = [[row['file'], row['shape'],
              '-' if row['count'] is None else str(row['count']),
              row['updated'], row['owner'], row['purpose'][:34]] for row in rows_]
    widths = [max(len(str(line[i])) for line in [header, *cells]) for i in range(len(header))]
    lines = ['  ' + '  '.join(text.ljust(widths[i]) for i, text in enumerate(header))]
    for line in cells:
        lines.append('  ' + '  '.join(str(text).ljust(widths[i]) for i, text in enumerate(line)))
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true', help='machine-readable rows')
    parser.add_argument('--check', action='store_true',
                        help='fail on an empty, unreadable or unowned baseline')
    args = parser.parse_args(argv)
    rows_ = rows()
    if args.json:
        print(json.dumps({'baselines': rows_}, ensure_ascii=False, indent=2))
        return 0
    if not rows_:
        print(f'no baselines in {baseline_dir()}')
        return 0
    print(render(rows_))
    if not args.check:
        return 0
    found = problems(rows_)
    for problem in found:
        print(f'  PROBLEM {problem}')
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(_errors.run(main, sys.argv[1:]))
