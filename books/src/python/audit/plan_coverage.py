#!/usr/bin/env python3
"""Plan coverage gate: no design directory without an owner, no item without a design.

``docs/plan/<topic>/`` holds one iteration's design and plan. ``plan.md`` is what
says whether that iteration is open (an item's 事实位) or finished and waiting to
be archived (the 待归档 table). Without this check the two drift silently: an item
disappears from the list while its design directory stays, or a design directory
appears and nobody schedules it.

What it enforces:

* every ``docs/plan/<topic>/`` is claimed exactly once — by one open item, or by
  one row of 待归档;
* every directory named by an item or by 待归档 exists;
* ``plan-N`` identifiers are unique and ``plan-next`` equals the largest one plus
  one, so the next item cannot collide;
* every open item carries 现状 / 动作 / 验收 / 事实位, in that order;
* the 概述 line "在办 N 项" and its per-tier breakdown match the items present.
"""
from __future__ import annotations

import os
import re
import sys

_sys = sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil  # noqa: E402

ITEM_RE = re.compile(r'^#### `plan-(\d+)` ([^\n]+)$', re.M)
BLOCKS = ('**现状**', '**动作**', '**验收**', '**事实位**')
TIER_RE = re.compile(r'^### P(\d) — ', re.M)
COUNT_RE = re.compile(r'在办 (\d+) 项：(.+)$', re.M)
NEXT_RE = re.compile(r'`plan-next = (\d+)`')
DIR_REF_RE = re.compile(r'`(docs/plan/[a-z0-9][a-z0-9-]*)(?:/[^`]*)?`')
PENDING_HEADING = '## 待归档'


def plan_dir() -> str:
    return os.path.join(_config.DOCS_DIR, 'plan')


def plan_path() -> str:
    return os.path.join(_config.DOCS_DIR, 'managements', 'plan.md')


def design_dirs(root: str | None = None) -> list[str]:
    """Iteration directories that exist on disk."""
    try:
        names = sorted(os.listdir(root or plan_dir()))
    except OSError:
        return []
    base = root or plan_dir()
    return [name for name in names if os.path.isdir(os.path.join(base, name))]


def as_int(value: str) -> int:
    """A regex-captured number; a malformed capture counts as zero rather than raising."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def own_section(text: str, heading: str) -> str:
    """Text of one ``## `` section (heading included), up to the next ``## ``."""
    match = re.search(rf'^{re.escape(heading)}[^\n]*\n', text, re.M)
    if not match:
        return ''
    following = re.search(r'^## ', text[match.end():], re.M)
    end = match.end() + following.start() if following else len(text)
    return text[match.start():end]


def open_items(text: str) -> dict[str, dict]:
    """plan-N -> {title, blocks, dirs}, taken from the 当前迭代待办 section."""
    section = own_section(text, '## 当前迭代待办')
    items: dict[str, dict] = {}
    matches = list(ITEM_RE.finditer(section))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        body = section[match.end():end]
        items[f'plan-{match.group(1)}'] = {
            'title': match.group(2).strip(),
            'body': body,
            'dirs': sorted(set(DIR_REF_RE.findall(body))),
        }
    return items


def pending_dirs(text: str) -> list[str]:
    """Directories listed in the 待归档 table."""
    return DIR_REF_RE.findall(own_section(text, PENDING_HEADING))


def tier_counts(text: str) -> dict[str, int]:
    """P1..P4 -> number of items found under that heading."""
    section = own_section(text, '## 当前迭代待办')
    headings = list(TIER_RE.finditer(section))
    counts: dict[str, int] = {}
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(section)
        counts[f'P{match.group(1)}'] = len(ITEM_RE.findall(section[match.end():end]))
    return counts


def check(docs: str | None = None) -> list[str]:
    base: str = docs if docs else str(_config.DOCS_DIR)
    text = _fsutil.read_text(os.path.join(base, 'managements', 'plan.md'))
    problems: list[str] = []
    items = open_items(text)
    pending = pending_dirs(text)
    on_disk = design_dirs(os.path.join(base, 'plan'))

    claimed: dict[str, str] = {}
    for name, item in items.items():
        if not item['dirs']:
            problems.append(f'{name}：事实位没有指向 docs/plan/<主题>/')
        for directory in item['dirs']:
            topic = directory.rsplit('/', 1)[-1]
            if topic in claimed:
                problems.append(f'{topic}：被 {claimed[topic]} 与 {name} 同时认领')
            claimed[topic] = name
            if topic not in on_disk:
                problems.append(f'{name}：事实位指向不存在的目录 {directory}/')
        positions = [item['body'].find(block) for block in BLOCKS]
        if any(position < 0 for position in positions):
            missing = [b for b, p in zip(BLOCKS, positions, strict=True) if p < 0]
            problems.append(f'{name}：缺少 {"、".join(missing)}')
        elif positions != sorted(positions):
            problems.append(f'{name}：现状/动作/验收/事实位的顺序不规范')

    for directory in pending:
        topic = directory.rsplit('/', 1)[-1]
        if topic in claimed:
            problems.append(f'{topic}：被 {claimed[topic]} 与待归档同时认领')
        claimed[topic] = PENDING_HEADING
        if topic not in on_disk:
            problems.append(f'待归档：指向不存在的目录 {directory}/')

    for topic in on_disk:
        if topic not in claimed:
            problems.append(f'docs/plan/{topic}/：没有计划项认领，也不在待归档')

    raw = own_section(text, '## 当前迭代待办')
    numbers = [as_int(number) for number, _title in ITEM_RE.findall(raw)]
    if len(set(numbers)) != len(numbers):
        problems.append('plan-N 编号重复')
    nexts = NEXT_RE.search(text)
    if not nexts:
        problems.append('缺少 `plan-next` 编号源')
    elif numbers and as_int(nexts.group(1)) != max(numbers) + 1:
        problems.append(
            f'`plan-next = {nexts.group(1)}` 应为 {max(numbers) + 1}（最大编号 + 1）')

    counts = tier_counts(text)
    total = sum(counts.values())
    if total != len(items):
        problems.append(f'P1–P4 下的计划项共 {total} 项，与实际 {len(items)} 项不符')
    claim = COUNT_RE.search(text)
    if not claim:
        problems.append('缺少「在办 N 项」概述行')
    else:
        if as_int(claim.group(1)) != len(items):
            problems.append(f'概述写「在办 {claim.group(1)} 项」，实际 {len(items)} 项')
        stated = {tier: as_int(count)
                  for tier, count in re.findall(r'(P\d) (\d+) 项', claim.group(2))}
        actual = {tier: count for tier, count in counts.items() if count}
        if stated != actual:
            problems.append(f'概述的分档数字 {stated} 与实际 {actual} 不符')
    return problems


def main() -> int:
    _fsutil.pin_stdout_utf8()
    problems = check()
    if problems:
        print(f'计划覆盖问题 {len(problems)} 处：')
        for problem in problems:
            print(f'  {problem}')
        return 1
    print('计划覆盖正常')
    return 0


if __name__ == '__main__':
    sys.exit(main())
