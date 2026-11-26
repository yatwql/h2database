#!/usr/bin/env python3
"""Marked fact blocks: the parts of a chapter that are re-derived from source.

Package tables, type tables, source coordinates and dependency directions change
with the source tree, but they are not prose. Marking them lets
``chapters.py --refresh-facts`` swap the facts inside a chapter that already
carries written prose, without touching a single word outside the markers.

Format, one block per name:

  <!-- generated:packages -->
  | 包 | 文件数 | 行数 | 职责 |
  <!-- /generated -->

A file without markers has nothing to refresh; the caller reports the skip.
"""
from __future__ import annotations

import difflib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
from typing import TypedDict

from lib import _config, _fsutil

GENERATED_OPEN = '<!-- generated:{} -->'
GENERATED_CLOSE = '<!-- /generated -->'
GENERATED_OPEN_RE = re.compile(r'^<!--\s*generated:([\w.:-]+)\s*-->$')
GENERATED_CLOSE_RE = re.compile(r'^<!--\s*/generated\s*-->$')
BACKUP_SUBDIR = 'generated-backup'




class Insertion(TypedDict):
    """One planned insertion: which block, where, and the anchor it matched."""

    name: str
    line: int
    anchor: str


class MarkerPlan(TypedDict):
    """What a chapter carries and what it would gain."""

    present: list[str]
    missing: list[str]
    unclosed: list[str]
    duplicated: list[str]
    plan: list[Insertion]


def blocks_from_skeleton(text: str) -> dict[str, list[str]]:
    """name -> body lines, read back from a rendered skeleton.

    The skeleton is the only authority on where a block belongs and what it holds,
    so the plan is derived from it rather than from labels written down here.
    """
    blocks: dict[str, list[str]] = {}
    current = None
    body: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        opened = GENERATED_OPEN_RE.match(stripped)
        if opened:
            current, body = opened.group(1), []
            continue
        if GENERATED_CLOSE_RE.match(stripped):
            if current is not None:
                blocks[current] = body
            current, body = None, []
            continue
        if current is not None:
            body.append(line)
    return blocks


def marker_names(text: str) -> dict[str, list[str]]:
    """What the text already carries: names, unclosed markers and duplicates."""
    names: list[str] = []
    unclosed: list[str] = []
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        opened = GENERATED_OPEN_RE.match(stripped)
        if opened:
            if current is not None:
                unclosed.append(current)
            current = opened.group(1)
            names.append(current)
            continue
        if GENERATED_CLOSE_RE.match(stripped):
            current = None
    if current is not None:
        unclosed.append(current)
    counted: dict[str, int] = {}
    for name in names:
        counted[name] = counted.get(name, 0) + 1
    return {'present': sorted(counted),
            'unclosed': sorted(set(unclosed)),
            'duplicated': sorted(name for name, n in counted.items() if n > 1)}


HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$')


def block_headings(skeleton: str) -> dict[str, str]:
    """The heading each block sits under in the skeleton.

    The generator already decides this placement; reading it back keeps the
    insertion rule language- and book-neutral — no label list to translate.
    """
    out: dict[str, str] = {}
    heading = ''
    current = None
    for line in skeleton.splitlines():
        if HEADING_RE.match(line):
            heading = line.strip()
            continue
        opened = GENERATED_OPEN_RE.match(line.strip())
        if opened:
            current = opened.group(1)
            out[current] = heading
    return out


def _section_number(heading: str) -> str:
    match = re.search(r'(\d+(?:\.\d+)*)', heading)
    return match.group(1) if match else ''


def _title(line: str) -> str:
    return re.sub(r'^#{1,6}\s+', '', line).strip()


def suggest_anchor(lines: list[str], heading: str) -> tuple[int, str]:
    """The 1-based line a block should be inserted before, and the reason.

    The rule reads only the skeleton and the chapter — no label list, so it works for
    any book or language. Title similarity decides; the section number is a tie-break
    only among titles that already look related, because numbers get reused for
    different sections (a `1.5` in the skeleton need not be the `1.5` in the prose).
    """
    if not heading:
        return 0, '（章末）'
    title = _title(heading)
    headings = [(i, line) for i, line in enumerate(lines, start=1) if HEADING_RE.match(line)]
    for index, line in headings:
        if _title(line) == title:
            return index, line.strip()
    number = _section_number(heading)

    def score(entry: tuple[int, str]) -> float:
        """How well a heading in the prose matches the skeleton's.

        Title similarity carries the decision; a shared section number adds a fixed
        bonus, so a renamed `1.2` still lands in the right place while a number
        reused for a different section cannot outrank a clearly better title.
        """
        _index, line = entry
        ratio = difflib.SequenceMatcher(None, title, _title(line)).ratio()
        if number and _section_number(line) == number:
            ratio += 0.25
        return ratio

    ranked = sorted(((score(entry), entry) for entry in headings), key=lambda item: -item[0])
    if not ranked or ranked[0][0] < 0.5:
        return 0, '（章末）'
    index, line = ranked[0][1]
    return index, line.strip()


def plan_insertions(text: str, blocks: dict[str, list[str]],
                    headings: dict[str, str] | None = None) -> MarkerPlan:
    """What a chapter is missing, and where each missing block would go.

    `blocks` and `headings` come from the rendered skeleton (`blocks_from_skeleton`,
    `block_headings`); nothing is modified here — the caller prints the plan.
    """
    state = marker_names(text)
    lines = text.splitlines()
    headings = headings or {}
    missing = [name for name in blocks if name not in state['present']]
    plan: list[Insertion] = []
    for name in missing:
        lineno, why = suggest_anchor(lines, headings.get(name, ''))
        plan.append({'name': name, 'line': lineno, 'anchor': why})
    return {'present': state['present'], 'missing': missing,
            'unclosed': state['unclosed'], 'duplicated': state['duplicated'],
            'plan': plan}


def insert_block(text: str, lineno: int, name: str, lines: list[str]) -> str:
    """Insert one marked block before 1-based `lineno` (0 or past the end = append)."""
    body = text.splitlines()
    block = mark_block(name, lines)
    index = max(0, min(len(body), lineno - 1)) if lineno > 0 else len(body)
    if index > 0 and body[index - 1].strip():
        block = ['', *block]
    head, tail = body[:index], body[index:]
    if tail and tail[0].strip():
        block = [*block, '']
    return '\n'.join([*head, *block, *tail]).rstrip('\n') + '\n'


def mark_block(name: str, lines: list[str]) -> list[str]:
    """One marked block: open marker, body, close marker, blank separator."""
    return [GENERATED_OPEN.format(name), *lines, GENERATED_CLOSE, '']


def generated_blocks(text: str) -> dict[str, list[str]]:
    """Block name -> body lines, for every marked block in ``text``."""
    blocks: dict[str, list[str]] = {}
    name = None
    body: list[str] = []
    for line in (text or '').split('\n'):
        stripped = line.strip()
        opening = GENERATED_OPEN_RE.match(stripped)
        if opening and name is None:
            name, body = opening.group(1), []
            continue
        if GENERATED_CLOSE_RE.match(stripped) and name is not None:
            blocks[name] = body
            name = None
            continue
        if name is not None:
            body.append(line)
    return blocks


def line_delta(old: str, new: str) -> tuple[int, int]:
    """(removed, added) line counts between two texts, for the cost preview."""
    matcher = difflib.SequenceMatcher(None, (old or '').split('\n'),
                                      (new or '').split('\n'), autojunk=False)
    removed = added = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        removed += i2 - i1
        added += j2 - j1
    return removed, added


def refresh_blocks(existing: str, fresh: str) -> tuple[str, int, int] | None:
    """Swap fresh facts into the existing chapter, leaving the rest untouched.

    Returns ``(new_text, removed_lines, added_lines)``, or None when the file on
    disk carries no marked block: there is nothing to refresh in place, and the
    caller reports the skip instead of guessing where the facts belong.
    """
    current = generated_blocks(existing)
    if not current:
        return None
    wanted = generated_blocks(fresh)
    out: list[str] = []
    name = None
    for line in existing.split('\n'):
        opening = GENERATED_OPEN_RE.match(line.strip())
        if opening and name is None:
            name = opening.group(1)
            out.append(line)
            if name in wanted:
                out.extend(wanted[name])
            continue
        if GENERATED_CLOSE_RE.match(line.strip()) and name is not None:
            out.append(line)
            name = None
            continue
        if name is not None and name in wanted:
            continue
        out.append(line)
    removed = added = 0
    for name, body in current.items():
        if name in wanted:
            gone, grown = line_delta('\n'.join(body), '\n'.join(wanted[name]))
            removed += gone
            added += grown
    return '\n'.join(out), removed, added


def backup_existing(path: str, stamp: str) -> str | None:
    """Copy a chapter aside before --force overwrites it; None when it is new."""
    if not os.path.isfile(path):
        return None
    folder = os.path.join(_config.tmp_dir(), BACKUP_SUBDIR, stamp)
    try:
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, os.path.basename(path))
        _fsutil.write_text(target, _fsutil.read_text(path))
    except OSError as exc:
        print(f'  [warn] 备份失败（{exc}）；继续覆盖', file=sys.stderr)
        return None
    return target

def insert_planned(text: str, plan: MarkerPlan, blocks: dict[str, list[str]]) -> str:
    """Insert every planned block; bottom-up, so earlier line numbers stay valid."""
    updated = text
    for item in sorted(plan['plan'], key=lambda entry: -int(entry['line'])):
        updated = insert_block(updated, int(item['line']), str(item['name']),
                               blocks[str(item['name'])])
    return updated


def marker_mode(chapters: list[dict], args, *, spec, skeleton_for, path_of) -> int:
    """Report (and with `--apply` perform) marker insertion for every chapter.

    Kept here rather than in the chapter generator: the markers, their anchors and
    the insertion are one subject, and the generator only supplies the skeleton.
    """
    written = 0
    for chapter in chapters:
        name = chapter['file']
        if (args.only and name != args.only) or name not in spec:
            continue
        skeleton = skeleton_for(chapter)
        blocks = blocks_from_skeleton(skeleton)
        headings = block_headings(skeleton)
        path = path_of(name)
        text = _fsutil.read_text(path) if os.path.isfile(path) else ''
        plan = plan_insertions(text, blocks, headings)
        missing = plan['missing']
        print(f"{name}: 标记 {len(plan['present'])}/{len(blocks)}"
              + (f"｜缺 {', '.join(missing)}" if missing else '｜齐备'))
        for warning in ('unclosed', 'duplicated'):
            if plan[warning]:
                print(f"  ! {warning}: {', '.join(plan[warning])}")
        for item in plan['plan']:
            print(f"  + {item['name']} → 第 {item['line'] or '末尾'} 行（{item['anchor']}）")
        if not args.insert_markers or not plan['plan'] or not args.apply:
            continue
        _fsutil.ensure_dir(os.path.dirname(path))
        _fsutil.write_text(path, insert_planned(text, plan, blocks))
        written += 1
    if args.insert_markers and not args.apply:
        print('（只读预览；加 --apply 写入，写入前先备份）')
    if written:
        print(f'markers inserted: {written} chapter(s)')
    return 0
