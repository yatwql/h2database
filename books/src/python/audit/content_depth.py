#!/usr/bin/env python3
"""Content-depth checks that structure and prose metrics cannot see.

  PREREQ    a chapter cites a type owned by a later chapter without naming that
            chapter (forward reference with no signpost)
  GLOSSARY  a public type is used repeatedly in the manuscript but has no
            glossary entry
  EXCERPT   a fenced code excerpt annotated with `File.java:LINE` no longer
            matches the source at that line
  EXERCISE  an 延伸思考 item names neither a key type of its chapter nor a §anchor

Thresholds and toggles live in style.json [content_depth].

Usage:
  python content_depth.py
  python content_depth.py --json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _baseline, _config, _fsutil

SETTINGS = dict(_config.STYLE_POLICY.get('content_depth') or {})
MIN_USES = int(SETTINGS.get('glossary_min_uses', 3))
IGNORE = set(SETTINGS.get('glossary_ignore') or [])
EXCERPT_LINES = int(SETTINGS.get('excerpt_lines', 6))
FENCE_RE = re.compile(r'^\s*```(\w*)\s*$')
EXCERPT_HEAD_RE = re.compile(r'^\s*(?://|#|--)\s*([\w.]+?\.(?:java|py|rs)):(\d+)\s*$')
EXERCISE_RE = re.compile(r'^\*\*\d+\.\s*[🟢🔵🟠]', re.MULTILINE)
ANCHOR_RE = re.compile(r'§\d+(?:\.\d+)*')


def inventory() -> dict:
    path = os.path.join(_config.BOOK_ROOT, 'data', 'state', 'source-inventory.json')
    if not os.path.isfile(path):
        return {}
    try:
        return json.loads(_fsutil.read_text(path))
    except (OSError, json.JSONDecodeError):
        return {}


def owner_map() -> dict[str, int]:
    """Type name -> the chapter that owns its package."""
    owners: dict[str, int] = {}
    numbering = _config.chapter_numbering()
    for chapter, packages in _config.chapter_packages().items():
        chapter_no = (numbering.get(chapter) or [0])[0]
        inv = inventory().get('packages') or {}
        for package in packages:
            entry = inv.get(package) or {}
            for unit in entry.get('classes') or []:
                owners.setdefault(unit['name'], chapter_no)
    return owners


def chapter_text(path: str) -> str:
    return _fsutil.read_text(path)


def check_prerequisites(path: str, chapter_no: int, owners: dict[str, int]) -> list[dict]:
    out = []
    text = chapter_text(path)
    lines = text.split('\n')
    in_fence = False
    for index, line in enumerate(lines, 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or line.lstrip().startswith('#'):
            continue
        spans = set(re.findall(r'`([A-Za-z_][A-Za-z0-9_.]*)`', line))
        for name, owner in owners.items():
            if owner <= chapter_no or len(name) < 4 or name not in spans:
                continue
            if re.search(rf'第\s*{owner}\s*章', line) or f'第{owner}章' in line:
                continue
            out.append({'file': os.path.basename(path), 'line': index, 'kind': 'PREREQ',
                        'detail': f'{name} is owned by chapter {owner}, no signpost'})
            break
    return out


def check_glossary(files: list[str], min_uses: int | None = None,
                   ignore: set[str] | None = None) -> list[dict]:
    threshold = MIN_USES if min_uses is None else min_uses
    skipped = IGNORE if ignore is None else ignore
    glossary = _fsutil.read_text(_config.glossary_path())
    entries = set(re.findall(r'^- \*\*([^*]+)\*\*', glossary, re.MULTILINE))
    counts: dict[str, int] = {}
    for path in files:
        for name in re.findall(r'\b([A-Z][A-Za-z0-9]{3,})\b', chapter_text(path)):
            counts[name] = counts.get(name, 0) + 1
    missing = [(name, count) for name, count in counts.items()
               if count >= threshold and name not in entries and name not in skipped]
    return [{'file': '(manuscript)', 'line': 0, 'kind': 'GLOSSARY',
             'detail': f'{name} used {count}x, no glossary entry'}
            for name, count in sorted(missing, key=lambda item: -item[1])[:20]]


def check_excerpts(files: list[str]) -> list[dict]:
    source_root = _config.source_tree('src_main')
    out = []
    for path in files:
        lines = _fsutil.read_lines(path)
        for index, line in enumerate(lines):
            head = EXCERPT_HEAD_RE.match(line)
            if not head:
                continue
            rel, start = head.group(1), int(head.group(2))
            candidate = os.path.join(source_root, rel)
            if not os.path.isfile(candidate):
                matches = glob.glob(os.path.join(source_root, '**', os.path.basename(rel)),
                                    recursive=True)
                if not matches:
                    out.append({'file': os.path.basename(path), 'line': index + 1,
                                'kind': 'EXCERPT', 'detail': f'{rel} not found in source tree'})
                    continue
                candidate = matches[0]
            body = [row.strip() for row in lines[index + 1:index + 1 + EXCERPT_LINES]
                    if row.strip() and not FENCE_RE.match(row)]
            source_lines = [row.strip() for row in
                            _fsutil.read_lines(candidate)[start - 1:start - 1 + len(body)]]
            if body and source_lines and body[0] != source_lines[0]:
                out.append({'file': os.path.basename(path), 'line': index + 1,
                            'kind': 'EXCERPT',
                            'detail': f'{rel}:{start} excerpt drifted from source'})
    return out


def check_exercises(files: list[str], owners: dict[str, int],
                    numbering: dict[str, list[int]]) -> list[dict]:
    out = []
    for path in files:
        name = os.path.basename(path)
        chapter_no = (numbering.get(name) or [0])[0]
        key_types = [t for t, owner in owners.items()
                     if owner == chapter_no and len(t) >= 4]
        text = chapter_text(path)
        block = text.split('延伸思考', 1)
        if len(block) < 2:
            continue
        section = block[1]
        for match in EXERCISE_RE.finditer(section):
            chunk = section[match.start():match.start() + 400]
            if ANCHOR_RE.search(chunk):
                continue
            if any(key in chunk for key in key_types):
                continue
            out.append({'file': name, 'line': section[:match.start()].count('\n') + 1,
                        'kind': 'EXERCISE',
                        'detail': chunk.split('\n')[0][:60]})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--update-baseline', action='store_true',
                        help='accept the current findings as the reviewed backlog')
    args = parser.parse_args(argv)

    files = (sorted(glob.glob(os.path.join(_config.MANUSCRIPT_DIR, 'ch*.md')))
             + sorted(glob.glob(os.path.join(_config.MANUSCRIPT_DIR, 'appendix-*.md'))))
    owners = owner_map()
    numbering = _config.chapter_numbering()

    findings: list[dict] = []
    for path in files:
        chapter_no = (numbering.get(os.path.basename(path)) or [0])[0]
        findings.extend(check_prerequisites(path, chapter_no, owners))
    findings.extend(check_glossary(files))
    findings.extend(check_excerpts(files))
    findings.extend(check_exercises(files, owners, numbering))

    by_kind: dict[str, int] = {}
    for item in findings:
        by_kind[item['kind']] = by_kind.get(item['kind'], 0) + 1

    # Key by detail, not by line: inserting a section shifts every line number
    # below it and would resurrect a whole baseline as "new" findings.
    keys = {f'{item["file"]}:{item["kind"]}:{item["detail"]}' for item in findings}
    if args.update_baseline:
        path = _baseline.save('content-depth', keys,
                              'Reviewed depth backlog: forward references that predate the gate.')
        print(f'内容深度基线已更新：{len(keys)} 项 → {os.path.relpath(path, _config.BOOK_ROOT)}')
        return 0
    new, stale = _baseline.split('content-depth', keys)
    findings = [item for item in findings
                if f'{item["file"]}:{item["kind"]}:{item["detail"]}' in new]

    if args.json:
        print(json.dumps({'count': len(findings), 'by_kind': by_kind,
                          'new': len(new), 'stale': sorted(stale),
                          'findings': findings[:120]}, ensure_ascii=False, indent=2))
        return 0 if not findings else 1

    if not findings:
        print('✅ 内容深度检查通过（前提顺序/术语覆盖/摘录新鲜度/练习指向）')
        return 0
    print(f'内容深度问题 {len(findings)} 处：' +
          '  '.join(f'{k}={v}' for k, v in sorted(by_kind.items())))
    if stale:
        print(f'  基线中有 {len(stale)} 项已不再出现（可用 --update-baseline 收缩）')
    for item in findings[:15]:
        print(f"  {item['file']}:{item['line']}  [{item['kind']}] {item['detail']}")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
