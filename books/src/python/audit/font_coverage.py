#!/usr/bin/env python3
"""Check whether a candidate font actually covers the book's characters.

Choosing a font by name is guesswork: a family may be missing, may exist only as a
`.ttc` collection Chromium cannot subset, or may lack the rarer CJK characters this
book happens to use — and the last case is what turns a 7 MB PDF into 19 MB of
Type3 glyph procedures.

This reads the manuscript, collects every character that must be typeset, and
reports per candidate: the file it resolves to, whether it is embeddable, and which
characters it cannot draw.

Usage:
    python audit/font_coverage.py [--dir data/manuscript] [--family NAME ...]
"""
from __future__ import annotations

import argparse
import collections
import os
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from lib import (  # noqa: E402 - after the sys.path insert above
    _config,
    fonts,
)

SKIP_EXT = ('.png', '.jpg', '.pdf', '.epub')


def manuscript_chars(root: str) -> collections.Counter:
    """Character histogram of every manuscript file under `root`."""
    counts: collections.Counter = collections.Counter()
    for base, _dirs, files in os.walk(root):
        for name in files:
            if name.lower().endswith(SKIP_EXT):
                continue
            path = os.path.join(base, name)
            try:
                with open(path, encoding='utf-8') as handle:
                    counts.update(handle.read())
            except (OSError, UnicodeDecodeError):
                continue
    return counts


def coverage(font_path: str, counts: collections.Counter) -> tuple[int, list[str]]:
    """(characters drawn, missing characters) for one font file."""
    try:
        from fontTools.ttLib import TTFont  # noqa: PLC0415 - optional dependency
    except ImportError:
        return 0, ['fonttools 未安装，无法校验覆盖']
    try:
        font = TTFont(font_path, lazy=True, fontNumber=0)
        cmap = font.getBestCmap() or {}
    except Exception as exc:
        return 0, [f'无法读取字体: {exc}']
    missing = [char for char in counts if char.strip() and ord(char) not in cmap]
    return len(counts) - len(missing), sorted(missing, key=lambda c: -counts[c])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dir', default=None,
                        help='手稿目录，默认取书根下的 data/manuscript')
    parser.add_argument('--json', action='store_true', help='输出 JSON 供工具消费')
    parser.add_argument('--family', action='append', dest='families')
    args = parser.parse_args(argv[1:])

    families = args.families or fonts.default_sans()
    root = args.dir or os.path.join(_config.resolve_book_root(), 'data', 'manuscript')
    counts = manuscript_chars(root)
    if not counts:
        print(f'{args.dir} 下没有可读手稿')
        return 1
    print(f'手稿字符集 {len(counts)} 个不同字符（{sum(counts.values())} 次出现）')

    rows = []
    ok = True
    for family in families:
        path = fonts._font_file(family)
        if not path:
            rows.append({'family': family, 'file': '', 'embeddable': False,
                         'covered': 0, 'missing': []})
            if not args.json:
                print(f'  {family:22s} 未安装')
            continue
        embeddable = fonts.is_embeddable(family)
        drawn, missing = coverage(path, counts)
        rows.append({'family': family, 'file': path, 'embeddable': embeddable,
                     'covered': drawn, 'missing': missing[:50]})
        if missing:
            ok = False
        if not args.json:
            flag = 'ok' if embeddable and not missing else '问题'
            print(f'  {family:22s} {os.path.basename(path):32s} 可嵌入={embeddable} '
                  f'覆盖={drawn}/{len(counts)} 缺字={len(missing)} → {flag}')
            if missing:
                worst = ''.join(missing[:12])
                print(f'{"":26s}缺: {worst}{" …" if len(missing) > 12 else ""}')
    if args.json:
        import json  # noqa: PLC0415 - only for the machine-readable mode
        print(json.dumps({'root': root, 'characters': len(counts), 'fonts': rows},
                         ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
