#!/usr/bin/env python3
"""
延伸思考 / chapter exercises audit (v5.6 / U17).

Verifies every chapter ends with a `## N.X 延伸思考` sub-section that meets
style-guide §12 minimums:

  R1. The section exists once per chapter (or once per chapter-pair for files
      that combine two chapters such as `ch1-2-architecture.md`).
  R2. The section sits between `## N.X 本章小结` and `## N.X+1 延展阅读`.
  R3. Contains ≥ 3 numbered exercise blocks. An exercise block is a paragraph
      led by `**N. <emoji><star> 题干**` and immediately followed by
      blockquote lines beginning with `> 提示：` and `> 回顾：`.
  R4. Each exercise block carries a difficulty marker (`★`, `★★`, `★★★`)
      and a type emoji (🟢/🔵/🟠).
  R5. The 回顾 line points at concrete `§X.Y` or `第X章` anchors.

Usage:
  python _audit_exercises.py              # default: scan all ch*.md
  python _audit_exercises.py --json       # machine-readable summary
  python _audit_exercises.py --target ch7-sql-execution.md   # single file
  python _audit_exercises.py --template   # emit a 3-question template

Exit codes:
  0  every chapter passes; total exercise count >= floor (50 by default).
  1  any chapter fails R1-R5, or total below floor.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from glob import glob

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))

# Match `## N.X 延伸思考` where N is the chapter number and X is the local
# subsection index. We accept any subsection number — placement enforcement
# (between 本章小结 and 延展阅读) is checked separately.
HEADING_EXERCISES = re.compile(r'^## (\d+)\.(\d+)\s+延伸思考\s*$')
HEADING_SUMMARY = re.compile(r'^## (\d+)\.(\d+)\s+本章小结\s*$')
HEADING_FURTHER = re.compile(r'^## (\d+)\.(\d+)\s+延展阅读\s*$')
HEADING_CHAPTER = re.compile(r'^# 第(\d+)章')
HEADING_H2_ANY = re.compile(r'^## ')

# Exercise block: starts with `**N. ...**` line, where the body must contain
# both a difficulty marker (★ at least once) and a type emoji from the
# approved set 🟢🔵🟠. Capture the whole leading line.
EXERCISE_LEAD = re.compile(
    r'^\*\*(\d+)\.\s*([🟢🔵🟠])(★+)\s*(.+?)\*\*\s*$'
)

# Hint and review markers — both are blockquote lines but the wording is
# fixed so the audit can recognise them deterministically.
HINT_RE = re.compile(r'^>\s*提示[：:]\s*(.+)')
REVIEW_RE = re.compile(r'^>\s*回顾[：:]\s*(.+)')

# The review line must contain at least one §X.Y or 第X章 anchor.
ANCHOR_RE = re.compile(r'§\d+(?:\.\d+)*[a-z]?|第\d+章')


def _is_in_fence(idx: int, fence_state: list[bool]) -> bool:
    return fence_state[idx]


def _scan_fences(lines: list[str]) -> list[bool]:
    """Mark each line as inside-fence so we don't pattern-match diagram art."""
    inside = [False] * len(lines)
    fence_open = False
    for i, raw in enumerate(lines):
        if raw.lstrip().startswith('```'):
            fence_open = not fence_open
            inside[i] = True
            continue
        inside[i] = fence_open
    return inside


def parse_chapter_slots(lines: list[str]) -> list[dict]:
    """Identify every (chapter, summary_line, exercises_line, further_line) slot.

    A "slot" is one chapter's tail. Files that contain two chapters (e.g.
    ch1-2) yield two slots. Each slot dict:
      {
        'chapter': int,
        'summary_line': int | None,
        'exercises_line': int | None,
        'further_line': int | None,
        'next_h2_after_exercises': int | None,
      }
    """
    fence = _scan_fences(lines)
    slots: list[dict] = []
    current = {'chapter': None, 'summary_line': None,
               'exercises_line': None, 'further_line': None}

    def flush():
        nonlocal current
        if current['chapter'] is not None:
            slots.append(current)
        current = {'chapter': None, 'summary_line': None,
                   'exercises_line': None, 'further_line': None}

    for i, raw in enumerate(lines):
        if fence[i]:
            continue
        cm = HEADING_CHAPTER.match(raw)
        if cm:
            # New chapter starts — flush previous slot context, but only
            # actually emit a slot when we see its 本章小结. Just track
            # which chapter we're in.
            if current['chapter'] is not None and current['summary_line']:
                # Previous chapter had a summary; finalise it before moving on.
                flush()
            current = {'chapter': int(cm.group(1)), 'summary_line': None,
                       'exercises_line': None, 'further_line': None}
            continue
        sm = HEADING_SUMMARY.match(raw)
        if sm:
            ch = int(sm.group(1))
            if current['chapter'] != ch:
                # The chapter heading wasn't seen (file starts mid-chapter,
                # e.g. ch6-2 starts at §6.4). Use the H2's chapter number.
                current = {'chapter': ch, 'summary_line': None,
                           'exercises_line': None, 'further_line': None}
            current['summary_line'] = i + 1
            continue
        em = HEADING_EXERCISES.match(raw)
        if em:
            ch = int(em.group(1))
            if current['chapter'] is None:
                current['chapter'] = ch
            current['exercises_line'] = i + 1
            continue
        fm = HEADING_FURTHER.match(raw)
        if fm:
            ch = int(fm.group(1))
            if current['chapter'] is None:
                current['chapter'] = ch
            current['further_line'] = i + 1
            # 延展阅读 closes a chapter slot; emit and reset.
            flush()
            continue

    flush()
    return [s for s in slots if s['chapter'] is not None]


def parse_exercises(lines: list[str], start_line: int, end_line: int) -> list[dict]:
    """Walk a 延伸思考 section and return a list of exercise records.

    `start_line` is the 1-indexed line of the section heading; `end_line` is
    the 1-indexed line of the next H2 (exclusive). Exercises are emitted
    in document order.
    """
    fence = _scan_fences(lines)
    out: list[dict] = []
    i = start_line  # skip the heading itself (start_line is 1-indexed)
    cur: dict | None = None
    while i < end_line:
        if i - 1 >= len(lines):
            break
        raw = lines[i - 1].rstrip('\n')
        if fence[i - 1]:
            i += 1
            continue
        m = EXERCISE_LEAD.match(raw)
        if m:
            if cur is not None:
                out.append(cur)
            cur = {
                'index': int(m.group(1)),
                'emoji': m.group(2),
                'difficulty': len(m.group(3)),  # number of stars
                'title': m.group(4).strip(),
                'has_hint': False,
                'has_review': False,
                'review_anchors': [],
                'line': i,
            }
            i += 1
            continue
        if cur is not None:
            hm = HINT_RE.match(raw)
            if hm:
                cur['has_hint'] = True
            rm = REVIEW_RE.match(raw)
            if rm:
                cur['has_review'] = True
                cur['review_anchors'] = ANCHOR_RE.findall(rm.group(1))
        i += 1
    if cur is not None:
        out.append(cur)
    return out


def find_section_end(lines: list[str], start_line: int) -> int:
    """Return the 1-indexed line of the next H2 after `start_line`.

    Falls back to len(lines)+1 if there is no following H2.
    """
    fence = _scan_fences(lines)
    for i in range(start_line, len(lines)):  # start_line is 1-indexed
        if fence[i]:
            continue
        if HEADING_H2_ANY.match(lines[i]):
            return i + 1
    return len(lines) + 1


def audit_file(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as fh:
        lines = fh.readlines()
    slots = parse_chapter_slots(lines)
    file_report = {
        'file': os.path.relpath(path, DOCS_DIR).replace(os.sep, '/'),
        'slots': [],
        'issues': [],
    }
    for slot in slots:
        ch = slot['chapter']
        report = {
            'chapter': ch,
            'has_summary': slot['summary_line'] is not None,
            'has_exercises': slot['exercises_line'] is not None,
            'has_further': slot['further_line'] is not None,
            'placement_ok': False,
            'exercise_count': 0,
            'difficulties': [],
            'emoji_distribution': {'🟢': 0, '🔵': 0, '🟠': 0},
            'all_have_hint': True,
            'all_have_review': True,
            'all_anchors_present': True,
            'exercises': [],
        }

        # Placement check: summary < exercises < further
        s, e, f = slot['summary_line'], slot['exercises_line'], slot['further_line']
        if s and e and f:
            report['placement_ok'] = (s < e < f)
        elif e and f:
            report['placement_ok'] = (e < f)

        if e is not None:
            section_end = (f or find_section_end(lines, e + 1))
            ex_list = parse_exercises(lines, e, section_end)
            report['exercise_count'] = len(ex_list)
            for ex in ex_list:
                report['difficulties'].append(ex['difficulty'])
                report['emoji_distribution'][ex['emoji']] += 1
                if not ex['has_hint']:
                    report['all_have_hint'] = False
                    file_report['issues'].append(
                        f"ch{ch} 延伸思考 第{ex['index']}题 缺少 提示 行 (L{ex['line']})")
                if not ex['has_review']:
                    report['all_have_review'] = False
                    file_report['issues'].append(
                        f"ch{ch} 延伸思考 第{ex['index']}题 缺少 回顾 行 (L{ex['line']})")
                if not ex['review_anchors']:
                    report['all_anchors_present'] = False
                    file_report['issues'].append(
                        f"ch{ch} 延伸思考 第{ex['index']}题 回顾行无 §X.Y 锚点 (L{ex['line']})")
                report['exercises'].append({
                    'index': ex['index'],
                    'difficulty': ex['difficulty'],
                    'emoji': ex['emoji'],
                    'has_hint': ex['has_hint'],
                    'has_review': ex['has_review'],
                    'anchors': ex['review_anchors'],
                })
        else:
            file_report['issues'].append(f"ch{ch} 缺少 ## N.X 延伸思考 小节")

        file_report['slots'].append(report)
    return file_report


def render_report(reports: list[dict], total_floor: int) -> int:
    issues_total = 0
    exercises_total = 0
    chapters_total = 0
    chapters_pass = 0

    print('=' * 72)
    print(f'章末延伸思考审计 (style-guide §12)  阈值：每章 ≥ 3 题，全书 ≥ {total_floor} 题')
    print('=' * 72)

    for fr in reports:
        print(f'\n## {fr["file"]}  ({len(fr["slots"])} 章节)')
        for s in fr['slots']:
            chapters_total += 1
            cnt = s['exercise_count']
            placement = '✓' if s['placement_ok'] else '✗'
            hint = '✓' if s['all_have_hint'] else '✗'
            review = '✓' if s['all_have_review'] else '✗'
            anch = '✓' if s['all_anchors_present'] else '✗'
            ok = (cnt >= 3 and s['placement_ok']
                  and s['all_have_hint'] and s['all_have_review']
                  and s['all_anchors_present'])
            tag = '✅ PASS' if ok else '❌ FAIL'
            if ok:
                chapters_pass += 1
            exercises_total += cnt
            difficulty_summary = '/'.join(
                str(s['difficulties'].count(k)) for k in (1, 2, 3))
            emoji_summary = (
                f"🟢{s['emoji_distribution']['🟢']}"
                f"🔵{s['emoji_distribution']['🔵']}"
                f"🟠{s['emoji_distribution']['🟠']}"
            )
            print(f"  第{s['chapter']}章 {tag}  题数={cnt}  "
                  f"placement={placement}  hint={hint}  review={review}  "
                  f"anchors={anch}  ★/★★/★★★={difficulty_summary}  {emoji_summary}")
        if fr['issues']:
            issues_total += len(fr['issues'])
            for msg in fr['issues']:
                print(f"    - {msg}")

    print()
    print('---')
    print(f'章节合格：{chapters_pass} / {chapters_total}')
    print(f'题目总数：{exercises_total}（floor={total_floor}）')
    print(f'未解决问题：{issues_total}')
    if chapters_pass < chapters_total or exercises_total < total_floor:
        return 1
    return 0


TEMPLATE = '''## {chapter}.{subsection} 延伸思考

下面 4 道自查题用来检验读者是否能把本章关键决策迁移到其他场景。

**1. 🟢★ 简要题干（理解题示例）**

> 提示：从 X 与 Y 的关系入手，比较 A 模式与 B 模式的核心差异。
> 回顾：§{chapter}.1、§{chapter}.2

**2. 🔵★★ 推理题干（分析题示例）**

> 提示：聚焦 X 改变后 Y 与 Z 的级联反应；考虑 W 的极端情形。
> 回顾：§{chapter}.3

**3. 🟠★★★ 动手题干（动手题示例）**

> 提示：在 H2 测试目录下定位相关用例；模拟某条件后观察输出。
> 回顾：§{chapter}.4、第{chapter}章

**4. 🔵★★ 对比题干**

> 提示：把本章的方案与上一章的方案放在同一坐标系下评估。
> 回顾：§{chapter}.5
'''


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='emit JSON')
    parser.add_argument('--target', help='single file under docs-stm/ to scan')
    parser.add_argument('--template', action='store_true',
                        help='print a 4-question template and exit')
    parser.add_argument('--floor', type=int, default=50,
                        help='minimum total exercise count to pass (default 50)')
    args = parser.parse_args(argv)

    if args.template:
        print(TEMPLATE.format(chapter=7, subsection=7))
        return 0

    if args.target:
        paths = [os.path.join(DOCS_DIR, args.target)]
    else:
        paths = sorted(glob(os.path.join(DOCS_DIR, 'ch*.md')))

    reports = [audit_file(p) for p in paths if os.path.isfile(p)]

    if args.json:
        chapters_total = sum(len(r['slots']) for r in reports)
        chapters_pass = sum(
            1 for r in reports for s in r['slots']
            if s['exercise_count'] >= 3 and s['placement_ok']
            and s['all_have_hint'] and s['all_have_review']
            and s['all_anchors_present']
        )
        exercises_total = sum(s['exercise_count']
                              for r in reports for s in r['slots'])
        payload = {
            'chapters_total': chapters_total,
            'chapters_pass': chapters_pass,
            'exercises_total': exercises_total,
            'floor': args.floor,
            'reports': reports,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        ok = chapters_pass == chapters_total and exercises_total >= args.floor
        return 0 if ok else 1

    return render_report(reports, args.floor)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
