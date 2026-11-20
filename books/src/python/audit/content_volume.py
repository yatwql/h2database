#!/usr/bin/env python3
"""Content-volume gate: the manuscript may grow, never silently shrink.

Every other gate in this toolchain judges shape — headings, links, figure
numbers, captions, style. None of them notices when a rewrite deletes most of
the prose but keeps the shape intact: the manuscript still validates, it is just
smaller. Volume is a property of its own, so it gets its own floor.

Two floors, both relative to a reviewed baseline:

  MANUSCRIPT   each tracked chapter keeps at least `floor_ratio` of its bytes
               and lines; the manuscript total keeps the same floor
  DELIVERED    the rendered PDF keeps at least `page_ratio` of its baseline
               pages, and the EPUB at least `size_ratio` of its bytes

A file may disappear from the book only by removing it from `book.toml` and
re-baselining (`--update-baseline`), which is a reviewed, diffable change.

Usage:
  python content_volume.py                 # gate
  python content_volume.py --json          # machine-readable report
  python content_volume.py --update-baseline
Exit 1 on any finding. An absent baseline is advisory (0): a new book has no
manuscript to protect yet.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil, _log

BASELINE_PATH = os.path.join(_config.BOOK_ROOT, 'data', 'baselines', 'content-volume.json')
LOG = _log.get_logger('content_volume')
# Ratios come from data/config/base.json [toolchain]: policy is configuration,
# never a constant buried in a gate.
FLOOR_RATIO = float(_config.THRESHOLDS.get('content_floor_ratio', 0.95))
PAGE_RATIO = float(_config.THRESHOLDS.get('pdf_page_ratio', 0.90))
SIZE_RATIO = float(_config.THRESHOLDS.get('epub_size_ratio', 0.85))
# Which starting point the book is in (docs/managements/quality-model.md §2):
#   baseline    — an accepted manuscript that must not shrink (strict)
#   rewrite     — the prose is being replaced wholesale: the floor still holds,
#                 but a reviewed `--update-baseline` is the expected next step
#   cold-start  — no history yet; the floor is advisory until the first review
PROFILE = str(_config.THRESHOLDS.get('content_profile', 'baseline'))


def manuscript_files() -> list[str]:
    """Chapter and matter files in reading order (the baseline key order)."""
    files: list[str] = []
    files += _config.front_matter()
    files += [os.path.join(_config.MANUSCRIPT_DIR, name)
              for name in _config.chapter_files(include_cover=True)]
    files += _config.back_matter()
    seen: set[str] = set()
    ordered: list[str] = []
    for path in files:
        if os.path.exists(path) and path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered


def measure(path: str) -> dict[str, int]:
    text = _fsutil.read_text(path)
    return {'bytes': len(text.encode('utf-8')), 'lines': len(text.splitlines())}


def snapshot() -> dict:
    files: dict[str, dict[str, int]] = {}
    total = {'bytes': 0, 'lines': 0}
    for path in manuscript_files():
        stats = measure(path)
        files[os.path.relpath(path, _config.MANUSCRIPT_DIR).replace(os.sep, '/')] = stats
        total['bytes'] += stats['bytes']
        total['lines'] += stats['lines']
    return {
        'manuscript': {'files': files, 'total': total},
        'delivered': delivered_snapshot(),
        'thresholds': {
            'floor_ratio': FLOOR_RATIO,
            'page_ratio': PAGE_RATIO,
            'size_ratio': SIZE_RATIO,
        },
    }


def delivered_snapshot() -> dict[str, int]:
    """Pages and bytes of the current artifacts; empty when nothing was built."""
    out: dict[str, int] = {}
    pdf = _config.merged_pdf()
    epub = _config.merged_epub()
    if os.path.exists(pdf):
        try:
            from pypdf import PdfReader

            out['pdf_pages'] = len(PdfReader(pdf).pages)
            out['pdf_bytes'] = os.path.getsize(pdf)
        except Exception as exc:  # noqa: BLE001 - unreadable artifact is not this gate's finding
            LOG.debug('cannot read %s: %s', pdf, exc)
    if os.path.exists(epub):
        out['epub_bytes'] = os.path.getsize(epub)
    return out


def load_baseline() -> dict:
    if not os.path.exists(BASELINE_PATH):
        return {}
    raw = _fsutil.read_text(BASELINE_PATH)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f'内容体积基线无法解析：{exc}', file=sys.stderr)
        return {}


def compare(baseline: dict, current: dict) -> list[str]:
    problems: list[str] = []
    floor = float(baseline.get('thresholds', {}).get('floor_ratio', FLOOR_RATIO))
    base_files = baseline.get('manuscript', {}).get('files', {})
    now_files = current['manuscript']['files']
    for name, stats in base_files.items():
        if name not in now_files:
            problems.append(f'{name}: gone from the manuscript '
                            f'(was {stats["bytes"]} bytes / {stats["lines"]} lines)')
            continue
        for key in ('bytes', 'lines'):
            floor_value = int(stats[key] * floor)
            if now_files[name][key] < floor_value:
                problems.append(f'{name}: {key} {now_files[name][key]} < floor {floor_value} '
                                f'(baseline {stats[key]})')
    base_total = baseline.get('manuscript', {}).get('total', {})
    for key in ('bytes', 'lines'):
        if key in base_total:
            floor_value = int(base_total[key] * floor)
            if current['manuscript']['total'][key] < floor_value:
                problems.append(f'manuscript total: {key} {current["manuscript"]["total"][key]}'
                                f' < floor {floor_value} (baseline {base_total[key]})')
    delivered = baseline.get('delivered', {})
    now_delivered = current['delivered']
    if 'pdf_pages' in delivered and 'pdf_pages' in now_delivered:
        floor_pages = int(delivered['pdf_pages'] * PAGE_RATIO)
        if now_delivered['pdf_pages'] < floor_pages:
            problems.append(f'delivered PDF: {now_delivered["pdf_pages"]} pages '
                            f'< floor {floor_pages} (baseline {delivered["pdf_pages"]})')
    if 'epub_bytes' in delivered and 'epub_bytes' in now_delivered:
        floor_size = int(delivered['epub_bytes'] * SIZE_RATIO)
        if now_delivered['epub_bytes'] < floor_size:
            problems.append(f'delivered EPUB: {now_delivered["epub_bytes"]} bytes '
                            f'< floor {floor_size} (baseline {delivered["epub_bytes"]})')
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--update-baseline', action='store_true',
                        help='record the current volume as the reviewed baseline')
    args = parser.parse_args(argv)

    current = snapshot()
    if args.update_baseline:
        _fsutil.write_text(BASELINE_PATH,
                           json.dumps(current, ensure_ascii=False, indent=2) + '\n')
        total = current['manuscript']['total']
        print(f'content-volume baseline updated: {len(current["manuscript"]["files"])} files, '
              f'{total["bytes"]} bytes, {total["lines"]} lines')
        return 0

    baseline = load_baseline()
    if PROFILE == 'cold-start' and baseline:
        print(f'内容体积：cold-start 档，基线仅供参考（profile={PROFILE}）')
        baseline = {}
    if not baseline:
        # A fresh book (or an unfamiliar project's first pass) has nothing to
        # regress against: the floor only protects an established manuscript.
        print('内容体积基线尚未建立（首次分析与新书正常）：'
              f'{os.path.relpath(BASELINE_PATH, _config.BOOK_ROOT)}')
        print('   定稿后执行：python books/src/python/audit/content_volume.py --update-baseline')
        return 0

    problems = compare(baseline, current)
    if args.json:
        print(json.dumps({'count': len(problems), 'problems': problems,
                          'total': current['manuscript']['total'],
                          'delivered': current['delivered']}, ensure_ascii=False, indent=2))
        return 0 if not problems else 1
    total = current['manuscript']['total']
    print(f'手稿：{len(current["manuscript"]["files"])} 文件 / '
          f'{total["bytes"]} 字节 / {total["lines"]} 行')
    if current['delivered']:
        print(f'产物：{current["delivered"]}')
    if not problems:
        print('✅ 内容体积不低于基线')
        return 0
    print(f'内容体积问题 {len(problems)} 处：')
    for problem in problems:
        print(f'  - {problem}')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
