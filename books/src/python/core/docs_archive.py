#!/usr/bin/env python3
"""Move a released version's ledgers and finished designs into ``docs/archive``.

The rule this tool enforces is mechanical only: **a released version's records
leave the live documents and land in ``docs/archive/v<major>.<minor>/``**, and the
live documents keep a single index line per archived version. What counts as
"finished" stays a human decision — the tool takes the topic names it is given
and never guesses, and ``--dry-run`` prints every action without writing.

Layout produced for version ``0.1``::

    docs/archive/v0.1/
      archived_changelog.0.1.md        # the release's own section, moved
      archived_plan.0.1.md             # snapshot of plan.md at release
      archived_review-findings.0.1.md  # that version's fixed-issue table, moved
      multi-book/                      # finished iteration designs (moved whole)

Usage::

    python core/docs_archive.py --version 0.1 --dry-run
    python core/docs_archive.py --version 0.1 --topic multi-book --date 2026-11-22
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import sys

_sys = sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _errors, _fsutil  # noqa: E402

ARCHIVE_REL = ('archive',)
LEDGERS = ('changelog', 'plan', 'review-findings')
VERSION_DIR_RE = re.compile(r'^v(\d+)\.(\d+)$')
SECTION_RE = re.compile(r'^## \[([^\]]+)\][^\n]*$', re.M)
ANY_SECTION_RE = re.compile(r'^## ', re.M)
RF_BLOCK_RE = re.compile(r'^### 本版本已修复[（(]([^)）]+)[)）][^\n]*$', re.M)
TOPIC_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')
INDEX_HEADING = '## 归档'
ARCHIVE_HEADER_VERSION = '> 涵盖版本：{}'
ARCHIVE_HEADER_TIME = '> 归档时间：{}'


class ArchiveError(RuntimeError):
    """Raised when the documents are not in a state the tool can act on."""


# ---- pure helpers ----------------------------------------------------------


def minor_of(version: str) -> str:
    """``0.1.2`` -> ``0.1``; a version without a minor part is an error."""
    parts = str(version).strip().lstrip('v').split('.')
    if len(parts) < 2 or not all(part.isdigit() for part in parts[:2]):
        raise ArchiveError(f'版本号 {version!r} 不是 X.Y[.Z] 形态')
    return f'{parts[0]}.{parts[1]}'


def version_dir_name(version: str) -> str:
    return f'v{minor_of(version)}'


def archive_names(version: str) -> dict[str, str]:
    """Archive file name per ledger, keyed by live document name."""
    minor = minor_of(version)
    return {name: f'archived_{name}.{minor}.md' for name in LEDGERS}


def render_header(version: str, today: str) -> str:
    return f'{ARCHIVE_HEADER_VERSION.format(version)}\n{ARCHIVE_HEADER_TIME.format(today)}\n'


def apply_header(text: str, version: str, today: str) -> str:
    """Append this release to the archive header, or write it when absent."""
    text = re.sub(r'^> 涵盖版本：.*$', f'> 涵盖版本：{version}', text, flags=re.M)
    text = re.sub(r'^> 归档时间：.*$', f'> 归档时间：{today}', text, flags=re.M)
    if ARCHIVE_HEADER_VERSION.format('')[:-1] not in text:
        text = render_header(version, today) + text.lstrip('\n')
    return text


def split_version_section(text: str, version: str) -> tuple[str, str]:
    """Cut the ``## [<version>]`` section out; returns (rest, section)."""
    wanted = {minor_of(version), str(version).strip().lstrip('v')}
    for match in SECTION_RE.finditer(text):
        if match.group(1).strip().lstrip('v') not in wanted:
            continue
        following = ANY_SECTION_RE.search(text, match.end())
        end = following.start() if following else len(text)
        return text[:match.start()] + text[end:], text[match.start():end]
    raise ArchiveError(f'变更日志里没有 [{version}] 段')


def split_rf_block(text: str, version: str) -> tuple[str, str]:
    """Cut the ``### 本版本已修复（<version>）`` table out; returns (rest, block)."""
    minor = minor_of(version)
    for match in RF_BLOCK_RE.finditer(text):
        if match.group(1).strip().lstrip('v') != minor \
                and match.group(1).strip().lstrip('v') != str(version).lstrip('v'):
            continue
        following = re.search(r'^### ', text[match.end():], re.M)
        end = match.end() + following.start() if following else len(text)
        return text[:match.start()] + text[end:], text[match.start():end]
    raise ArchiveError(f'问题台账里没有「本版本已修复（{version}）」小节')


def index_line(name: str, version_dir: str, note: str) -> str:
    return f'- [`{name}`](../archive/{version_dir}/{name}) — {note}'


def ensure_index(text: str, entries: list[str]) -> str:
    """Keep one ``## 归档`` section listing every archived version."""
    if not entries:
        return text
    block = INDEX_HEADING + '\n' + '\n'.join(entries) + '\n'
    pattern = re.compile(r'^## 归档\n(?:(?!^## ).*\n)*', re.M)
    if pattern.search(text):
        return pattern.sub(block, text, count=1)
    return text.rstrip('\n') + '\n\n' + block


def topic_dirs(path: str) -> list[str]:
    """Iteration directories already inside a version archive."""
    try:
        names = os.listdir(path)
    except OSError:
        return []
    return sorted(name for name in names if os.path.isdir(os.path.join(path, name)))


# ---- actions ---------------------------------------------------------------


class ArchivePlan:
    """What the tool would do, so ``--dry-run`` and ``apply`` share one list."""

    def __init__(self, version: str, docs: str, today: str) -> None:
        self.version = version
        self.minor = minor_of(version)
        self.docs = docs
        self.today = today
        self.target = os.path.join(docs, 'archive', version_dir_name(version))
        self.names = archive_names(version)
        self.steps: list[str] = []
        self.errors: list[str] = []

    def path(self, ledger: str) -> str:
        return os.path.join(self.target, self.names[ledger])

    def live(self, ledger: str) -> str:
        return os.path.join(self.docs, 'managements', f'{ledger}.md')

    def check(self) -> None:
        if not os.path.isdir(self.docs):
            self.errors.append(f'文档目录不存在：{self.docs}')
        for ledger in LEDGERS:
            if not os.path.isfile(self.live(ledger)):
                self.errors.append(f'缺少主文档：{self.live(ledger)}')

    def describe(self) -> list[str]:
        return list(self.steps)


def build_plan(version: str, docs: str, topics: list[str], today: str) -> ArchivePlan:
    plan = ArchivePlan(version, docs, today)
    plan.check()
    if plan.errors:
        return plan
    plan.steps.append(f'建立版本目录 {os.path.relpath(plan.target, docs)}')
    plan.steps.append(f'迁出变更日志 [{version}] 段 → {plan.names["changelog"]}')
    plan.steps.append(
        f'迁出问题台账「本版本已修复（{version}）」→ {plan.names["review-findings"]}')
    plan.steps.append(f'快照计划文件 → {plan.names["plan"]}')
    for topic in topics:
        source = os.path.join(docs, 'plan', topic)
        if not os.path.isdir(source):
            plan.errors.append(f'迭代目录不存在：{os.path.relpath(source, docs)}')
            continue
        if not TOPIC_RE.match(topic):
            plan.errors.append(f'迭代目录名不合规：{topic}')
            continue
        plan.steps.append(f'移动迭代目录 {topic} → {version_dir_name(version)}/{topic}')
    plan.steps.append('刷新三份主文档的「## 归档」索引')
    return plan


def _move_section(plan: ArchivePlan, name: str, splitter) -> None:
    """Move one ledger section into the archive and leave the rest live.

    Idempotent: a second run finds the section gone and keeps what is already
    archived instead of failing.
    """
    live_text = _fsutil.read_text(plan.live(name))
    try:
        rest, section = splitter(live_text, plan.version)
    except ArchiveError:
        # second run: the section already moved, nothing left to take
        if not os.path.isfile(plan.path(name)):
            raise
        rest, section = live_text, ''
    section = re.sub(r'^## \[[^\]]+\]', f'## [{plan.version}]', section,
                     count=1, flags=re.M)
    existing = (_fsutil.read_text(plan.path(name))
                if os.path.isfile(plan.path(name)) else '')
    body = existing if section.strip() in existing else existing + '\n' + section
    _fsutil.write_text(plan.path(name), apply_header(body, plan.version, plan.today))
    _fsutil.write_text(plan.live(name), rest)


def _move_topics(plan: ArchivePlan, topics: list[str]) -> None:
    for topic in topics:
        source = os.path.join(plan.docs, 'plan', topic)
        destination = os.path.join(plan.target, topic)
        if os.path.isdir(destination):
            continue
        try:
            shutil.move(source, destination)
        except OSError as exc:
            raise ArchiveError(f'无法移动 {topic}：{exc}') from exc


def _refresh_indexes(plan: ArchivePlan) -> None:
    """Every ledger's archive index lists the versions now under data/archive."""
    entries = []
    try:
        archived = sorted(os.listdir(os.path.join(plan.docs, 'archive')))
    except OSError as exc:
        raise ArchiveError(f'无法读取归档目录：{exc}') from exc
    for name in archived:
        directory = os.path.join(plan.docs, 'archive', name)
        if not os.path.isdir(directory) or not VERSION_DIR_RE.match(name):
            continue
        names = archive_names(name.lstrip('v'))
        entries.append(index_line(names['changelog'], name, name.lstrip('v')))
    for ledger in LEDGERS:
        path = plan.live(ledger)
        _fsutil.write_text(path, ensure_index(_fsutil.read_text(path), entries))


def apply_plan(plan: ArchivePlan, topics: list[str]) -> None:
    """Perform the moves. Every write is idempotent: running twice changes nothing."""
    if plan.errors:
        raise ArchiveError('; '.join(plan.errors))
    _fsutil.ensure_dir(os.path.join(plan.target, plan.names['changelog']))

    _move_section(plan, 'changelog', split_version_section)
    _move_section(plan, 'review-findings', split_rf_block)
    # The plan is archived as a snapshot: it keeps describing what was in flight.
    _fsutil.write_text(plan.path('plan'),
                       apply_header(_fsutil.read_text(plan.live('plan')),
                                    plan.version, plan.today))

    _move_topics(plan, topics)
    _refresh_indexes(plan)


# ---- cli -------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    _fsutil.pin_stdout_utf8()
    parser = argparse.ArgumentParser(description='把已发布版本的台账与完成的迭代设计移入归档')
    parser.add_argument('--version', required=True, help='已发布的工具版本，如 0.1')
    parser.add_argument('--topic', action='append', default=[],
                        help='已完成的迭代目录名（可重复），由人指定')
    parser.add_argument('--date', default='', help='归档日期，缺省取今天')
    parser.add_argument('--dry-run', action='store_true', help='只打印动作，不写文件')
    parser.add_argument('--docs', default='', help='文档目录，缺省取书根的 docs/')
    args = parser.parse_args(argv)

    docs = args.docs or os.path.join(_config.BOOK_ROOT, 'docs')
    today = args.date or datetime.date.today().isoformat()
    try:
        plan = build_plan(args.version, docs, args.topic, today)
    except ArchiveError as exc:
        print(f'error: {exc}')
        return 2
    for error in plan.errors:
        print(f'error: {error}')
    if plan.errors:
        return 2
    for step in plan.describe():
        print(('would ' if args.dry_run else '') + step)
    if args.dry_run:
        return 0
    try:
        apply_plan(plan, args.topic)
    except ArchiveError as exc:
        print(f'error: {exc}')
        return 2
    print(f'已归档 {plan.version} → {os.path.relpath(plan.target, docs)}')
    return 0


if __name__ == '__main__':
    sys.exit(_errors.run(main))
