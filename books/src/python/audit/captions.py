#!/usr/bin/env python3
"""
Figure caption audit (v5.5 / U14).

Validates `**图 X-Y: Title**` lines against the verb-object structure spec
in `books/docs/managements/style-guide.md` §14.

Three flavours of violation are reported:

  NO_VERB    — caption is a bare noun phrase (no leading action verb)
  TOO_SHORT  — caption body shorter than the configured minimum
  TOO_LONG   — caption body longer than the configured maximum
  VAGUE      — caption uses one of the banned vague nouns (过程/示例/架构)
               with no further qualifier

Captions inside fenced code blocks (```text``` / ```java```) are explicitly
skipped so layout-style ASCII inside diagrams cannot trigger false positives.

Usage:
  python captions.py                    # default (normal) threshold
  python captions.py --threshold strict # tighter limits
  python captions.py --threshold loose  # baseline-friendly limits
  python captions.py --json             # machine-readable summary
  python captions.py --diff baseline.json   # report delta vs baseline

Exit codes:
  0  No violations above the configured threshold's `fail_at` count.
  1  Violation count exceeds `fail_at`.
"""

from __future__ import annotations

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import json
import os
import re
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from glob import glob

from lib import _config, _fsutil

# Pin stdout to UTF-8 so Chinese terminal output renders correctly on Windows.
_fsutil.pin_stdout_utf8()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = _config.BOOK_ROOT
MS_DIR = _config.MANUSCRIPT_DIR

# Verb dictionary — heuristic recognition. A caption "passes the verb gate" if
# its leading two characters match any of these. Keep this list close to the
# Vocabulary and presets come from books/data/config/config.json (policy).
LEADING_VERBS = tuple(_config.CAPTIONS.get('leading_verbs', (
    '展示', '对比', '拆解', '演示', '标注', '概览', '追踪',
)))

# Vague nouns in policy: a caption ending with one passes only when the
# prefix is long enough to qualify it ("MVStore 四层架构" passes).
VAGUE_TRAILING = tuple(_config.CAPTIONS.get('vague_trailing', ()))

# A single-character marker the figure caption regex uses; kept as a constant
# so it isn't accidentally inlined and divergent.
FIG_RE = re.compile(r'^\*\*图 ([A-Z0-9]+-\d+[a-z]*):\s*(.+?)\*\*\s*$')

# Presets (min_chars / max_chars / fail_at) come from policy with safe defaults.
THRESHOLDS = _config.CAPTIONS.get('presets') or {
    'strict': {'min_chars': 8, 'max_chars': 30, 'fail_at': 0},
    'normal': {'min_chars': 6, 'max_chars': 35, 'fail_at': 30},
    'loose': {'min_chars': 4, 'max_chars': 45, 'fail_at': 80},
}

@dataclass
class Violation:
    file: str
    line: int
    fig_id: str
    title: str
    kind: str        # NO_VERB / TOO_SHORT / TOO_LONG / VAGUE
    suggestion: str

    def to_record(self) -> dict:
        d = asdict(self)
        d['file'] = os.path.relpath(self.file, DOCS_DIR).replace(os.sep, '/')
        return d

def _strip_fences(lines: list[str]) -> list[bool]:
    """Return parallel array marking which lines are inside a fenced block."""
    inside = [False] * len(lines)
    fence_open = False
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith('```'):
            fence_open = not fence_open
            inside[i] = True  # the fence itself counts as inside
            continue
        inside[i] = fence_open
    return inside

def _classify(title: str, threshold: dict) -> tuple[str | None, str]:
    """Return (kind, suggestion) for a single title.

    `kind=None` means the title passes; otherwise one of the violation kinds
    plus a one-line rewrite hint. Order matters: VAGUE wins over NO_VERB so
    captions like "架构" surface the more useful diagnostic.
    """
    body = title.strip()
    length = len(body)

    if length < threshold['min_chars']:
        return 'TOO_SHORT', f'扩展至 ≥ {threshold["min_chars"]} 字，补充对象与限定语'
    if length > threshold['max_chars']:
        return 'TOO_LONG', f'压缩至 ≤ {threshold["max_chars"]} 字，把次要语境移到正文'

    # Vague trailing nouns with no qualifying prefix (e.g. just "MVStore 架构")
    # are flagged. The body must be at least 6 chars before the trailing noun
    # for it to pass — a richer caption like "MVStore 四层架构" is fine.
    for tail in VAGUE_TRAILING:
        if body.endswith(tail) and len(body) - len(tail) <= 4:
            return 'VAGUE', f'去掉模糊后缀「{tail}」，补充具体动词或维度'

    # Verb gate. We accept a leading 2-char verb from the dictionary;
    # otherwise the caption is "no verb".
    head = body[:2]
    if head not in LEADING_VERBS:
        return 'NO_VERB', '前置动词（展示 / 对比 / 拆解 / 标注 / 追踪 …）'

    return None, ''

def scan(threshold: dict, target_glob: str | None = None) -> list[Violation]:
    """Walk every .md file under books/ and return ordered violations."""
    paths: list[str] = []
    if target_glob:
        paths = sorted(glob(os.path.join(DOCS_DIR, target_glob)))
    else:
        paths.extend(sorted(glob(os.path.join(MS_DIR, 'ch*.md'))))
        paths.extend(sorted(glob(os.path.join(MS_DIR, 'appendix-*.md'))))

    out: list[Violation] = []
    for path in paths:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding='utf-8') as fh:
                lines = fh.readlines()
        except OSError as exc:
            print(f'warning: cannot read {path}: {exc}', file=sys.stderr)
            continue
        in_fence = _strip_fences(lines)
        for idx, raw in enumerate(lines):
            if in_fence[idx]:
                continue
            m = FIG_RE.match(raw.rstrip('\n'))
            if not m:
                continue
            fig_id, title = m.group(1), m.group(2)
            kind, hint = _classify(title, threshold)
            if kind:
                out.append(Violation(
                    file=path, line=idx + 1, fig_id=fig_id,
                    title=title, kind=kind, suggestion=hint,
                ))
    return out

def render_report(violations: Iterable[Violation], threshold: dict) -> int:
    """Print a human-readable report; return total count."""
    by_file: dict[str, list[Violation]] = {}
    counts = {'NO_VERB': 0, 'TOO_SHORT': 0, 'TOO_LONG': 0, 'VAGUE': 0}
    for v in violations:
        by_file.setdefault(v.file, []).append(v)
        counts[v.kind] = counts.get(v.kind, 0) + 1

    total = sum(counts.values())
    print('=' * 72)
    print(f'图注质量审计 (style-guide §14)  总违规：{total}  阈值：'
          f'min={threshold["min_chars"]}  max={threshold["max_chars"]}')
    print('=' * 72)

    for file, items in sorted(by_file.items()):
        rel = os.path.relpath(file, DOCS_DIR).replace(os.sep, '/')
        print(f'\n## {rel}  ({len(items)} 项)')
        for v in items:
            print(f'  L{v.line:>5} 图 {v.fig_id:<6} [{v.kind}] '
                  f'{v.title}')
            print(f'         → {v.suggestion}')

    print()
    print('---')
    print('按类型汇总：')
    for k in ('NO_VERB', 'VAGUE', 'TOO_SHORT', 'TOO_LONG'):
        print(f'  {k:<10}: {counts[k]:>4}')
    print(f'  {"TOTAL":<10}: {total:>4}')
    return total

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--threshold', choices=list(THRESHOLDS), default='normal',
                        help='violation threshold preset (default: normal)')
    parser.add_argument('--json', action='store_true',
                        help='emit machine-readable JSON summary instead of report')
    parser.add_argument('--diff', metavar='PATH',
                        help='compare against a previously saved JSON baseline')
    parser.add_argument('--target', metavar='GLOB',
                        help='restrict scan to files matching GLOB under books/')
    args = parser.parse_args(argv)

    threshold = THRESHOLDS[args.threshold]
    violations = scan(threshold, args.target)

    if args.json:
        payload = {
            'threshold': args.threshold,
            'min_chars': threshold['min_chars'],
            'max_chars': threshold['max_chars'],
            'count': len(violations),
            'violations': [v.to_record() for v in violations],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if len(violations) <= threshold['fail_at'] else 1

    if args.diff:
        try:
            with open(args.diff, encoding='utf-8') as fh:
                baseline = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f'error: cannot read baseline {args.diff}: {exc}', file=sys.stderr)
            return 2
        baseline_keys = {(v['file'], v['fig_id']) for v in baseline['violations']}
        current_keys = {(v.to_record()['file'], v.fig_id) for v in violations}
        fixed = baseline_keys - current_keys
        new = current_keys - baseline_keys
        print('与基线比较：')
        print(f'  基线违规：{baseline["count"]}')
        print(f'  当前违规：{len(violations)}')
        print(f'  已修复  ：{len(fixed)}')
        print(f'  新引入  ：{len(new)}')
        if new:
            print('  新引入的违规：')
            for f, fid in sorted(new):
                print(f'    {f} 图 {fid}')
        return 0

    total = render_report(violations, threshold)
    return 0 if total <= threshold['fail_at'] else 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
