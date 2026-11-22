#!/usr/bin/env python3
"""Terminology, spacing and heading rules from style.json [style_rules].

Rules (all opt-in via config):
  TERM      the same concept must use the preferred spelling (synonym map)
  LINK      link text must be descriptive (no "点击这里/这里/链接")
  HEADING   headings carry no trailing punctuation and are not bare labels
  CJK_SPACE a space is required between CJK and Latin/digits
  LIST      list items end consistently (all with 。 or all without)
  PARA      paragraphs stay under max_paragraph_chars

Usage:
  python style_rules.py
  python style_rules.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil

RULES = (_config.STYLE_POLICY.get('style_rules') or {})
BASELINE_PATH = os.path.join(_config.baseline_dir(),
                             'style-rules-baseline.json')
FENCE_RE = re.compile(r'^\s*```')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*$')
LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]*\)')
CJK = r'\u4e00-\u9fff'
CJK_LATIN_RE = re.compile(rf'[{CJK}][A-Za-z0-9]|[A-Za-z0-9][{CJK}]')
LIST_ITEM_RE = re.compile(r'^\s*(?:[-*+]|\d+\.)\s+(.*)$')
# Chinese typography keeps these tight: 第3章 / 图 6-12 / §6.2 / 附录 A
CJK_IDIOM_RE = re.compile(r'第\d+[章节题条个张]|图 [A-Z0-9]+-\d+|表 [A-Z0-9]+-\d+|§\d+(\.\d+)*|附录 [A-Z]')


def files() -> list[str]:
    """Chapters plus appendices, in the configured reading order."""
    return _config.chapter_files(include_cover=False)


def check_file(path: str) -> list[dict]:
    findings: list[dict] = []
    name = os.path.basename(path)
    lines = _fsutil.read_lines(path)
    in_fence = False
    list_blocks: list[list[bool]] = []
    list_endings: list[bool] = []

    def note(lineno: int, kind: str, detail: str) -> None:
        findings.append({'file': name, 'line': lineno, 'kind': kind, 'detail': detail})

    terminology = RULES.get('terminology') or {}
    banned_links = RULES.get('banned_link_text') or []
    heading_rule = RULES.get('heading') or {}

    for i, raw in enumerate(lines, 1):
        stripped = raw.rstrip('\n')
        if FENCE_RE.match(stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        heading = HEADING_RE.match(stripped)
        if heading:
            title = heading.group(2).strip()
            if heading_rule.get('no_trailing_punctuation') and re.search(r'[。：:，,；;]$', title):
                note(i, 'HEADING', f'trailing punctuation: {title[:40]}')
            if title in (heading_rule.get('forbid_bare') or []):
                note(i, 'HEADING', f'bare label heading: {title}')
            continue

        for label in LINK_RE.findall(stripped):
            if label.strip() in banned_links:
                note(i, 'LINK', f'non-descriptive link text: {label}')

        for group in terminology:
            hits = [variant for variant in group if variant in stripped]
            if len(hits) > 1:
                note(i, 'TERM', f'mixed spellings: {hits}')

        if RULES.get('cjk_latin_spacing'):
            candidate = CJK_IDIOM_RE.sub('', stripped)
            if CJK_LATIN_RE.search(candidate):
                note(i, 'CJK_SPACE', 'missing space between CJK and Latin')

        item = LIST_ITEM_RE.match(stripped)
        if item:
            list_endings.append(item.group(1).rstrip().endswith('。'))
        elif list_endings:
            if len(set(list_endings)) > 1:
                list_blocks.append(list_endings)
            list_endings = []

    if list_endings and len(set(list_endings)) > 1:
        list_blocks.append(list_endings)
    if RULES.get('list_punctuation') == 'consistent' and list_blocks:
        findings.append({'file': name, 'line': 0, 'kind': 'LIST',
                         'detail': f'{len(list_blocks)} list(s) mix ending punctuation'})

    limit = RULES.get('max_paragraph_chars')
    if limit:
        for block in re.split(r'\n\s*\n', '\n'.join(lines)):
            text = block.strip()
            if text and not text.startswith(('#', '|', '```', '>')) and len(text) > int(limit):
                findings.append({'file': name, 'line': 0, 'kind': 'PARA',
                                 'detail': f'paragraph {len(text)} chars > {limit}'})
    return findings


def _key(item: dict) -> str:
    detail = re.sub(r'\s+', ' ', item['detail'])[:60]
    return f"{item['file']}::{item['kind']}::{detail}"


def load_baseline() -> set[str]:
    if not os.path.isfile(BASELINE_PATH):
        return set()
    try:
        return set(json.loads(_fsutil.read_text(BASELINE_PATH)).get('accepted', []))
    except (OSError, json.JSONDecodeError):
        return set()


def save_baseline(findings: list[dict]) -> None:
    payload = {'updated': __import__('datetime').date.today().isoformat(),
               'note': 'Accepted style-rule findings. Refresh with --update-baseline.',
               'accepted': sorted(_key(item) for item in findings)}
    _fsutil.ensure_dir(BASELINE_PATH)
    _fsutil.write_text(BASELINE_PATH, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--update-baseline', action='store_true',
                        help='record the current findings as accepted')
    args = parser.parse_args(argv)

    findings: list[dict] = []
    for path in files():
        findings.extend(check_file(path))
    by_kind: dict[str, int] = {}
    for item in findings:
        by_kind[item['kind']] = by_kind.get(item['kind'], 0) + 1

    if args.update_baseline:
        save_baseline(findings)
        print(f'baseline updated: {len(findings)} accepted -> '
              f'{os.path.relpath(BASELINE_PATH, _config.BOOK_ROOT)}')
        return 0

    accepted = load_baseline()
    new = [item for item in findings if _key(item) not in accepted]

    if args.json:
        print(json.dumps({'count': len(findings), 'new': len(new), 'by_kind': by_kind,
                          'findings': findings[:200]}, ensure_ascii=False, indent=2))
        return 0 if not new else 1

    if not new:
        print(f'✅ 风格规则通过（已知 {len(findings)} 项在基线内）')
        return 0
    print(f'风格规则新增问题 {len(new)} 处（已知 {len(findings) - len(new)}）：' +
          '  '.join(f'{k}={v}' for k, v in sorted(by_kind.items())))
    for item in new[:20]:
        print(f"  {item['file']}:{item['line']}  [{item['kind']}] {item['detail']}")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
