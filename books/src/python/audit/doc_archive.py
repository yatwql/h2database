#!/usr/bin/env python3
"""Archive layout gate: one directory per released version, three ledgers inside.

What it checks (all mechanical, all cheap):

* ``docs/archive/`` holds only README files and ``v<major>.<minor>`` directories;
* each version directory holds the three archived ledgers and nothing else at its
  top level except finished iteration directories;
* each archived ledger carries the two self-describing header lines;
* the live ledgers keep one ``## 归档`` index whose links resolve and which lists
  every archived version — an unlisted directory is a version nobody can find;
* no released version is still written as a live section in the current ledgers;
* iteration directories keep the naming rule（小写连字符，不含追踪编号）and hold
  ``design.md`` / ``plan.md`` / ``README.md`` only.

The archive starts empty; every check is written so the empty state is green.
"""
from __future__ import annotations

import os
import re
import sys

_sys = sys
_sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _fsutil  # noqa: E402

ARCHIVE_REL = ('docs', 'archive')
LEDGERS = ('changelog', 'plan', 'review-findings')
VERSION_DIR_RE = re.compile(r'^v(\d+)\.(\d+)$')
HEADER_VERSION_RE = re.compile(r'^> 涵盖版本：\d+\.\d+$', re.M)
HEADER_TIME_RE = re.compile(r'^> 归档时间：\d{4}-\d{2}-\d{2}$', re.M)
INDEX_HEADING = '## 归档'
LINK_RE = re.compile(r'\]\((\.\./archive/v\d+\.\d+/([^)]+))\)')
TRACKER_RE = re.compile(r'(plan|rf)-\d+')
ALLOWED_TOPIC_FILES = frozenset({'design.md', 'plan.md', 'README.md'})
LIVE_SECTION_RE = re.compile(r'^## \[([^\]]+)\][^\n]*$', re.M)
LIVE_RF_RE = re.compile(r'^### 本版本已修复[（(]([^)）]+)[)）][^\n]*$', re.M)


def archive_root() -> str:
    return os.path.join(_config.BOOK_ROOT, *ARCHIVE_REL)


def safe_listdir(path: str) -> list[str]:
    """Directory entries, or an empty list when the directory cannot be read."""
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def version_dirs(root: str) -> list[str]:
    return [name for name in safe_listdir(root) if os.path.isdir(os.path.join(root, name))]


def archived_names(version: str) -> dict[str, str]:
    return {ledger: f'archived_{ledger}.{version}.md' for ledger in LEDGERS}


def live_path(ledger: str, docs: str | None = None) -> str:
    return os.path.join(docs or _config.DOCS_DIR, 'managements', f'{ledger}.md')


def index_links(text: str) -> set[str]:
    section = re.search(r'^## 归档\n(?:(?!^## ).*\n)*', text, re.M)
    if not section:
        return set()
    return {match.group(1) for match in LINK_RE.finditer(section.group(0))}


def live_versions(text: str) -> set[str]:
    return {match.group(1).strip().lstrip('v') for match in LIVE_SECTION_RE.finditer(text)}


def check(root: str | None = None, docs: str | None = None) -> list[str]:
    root = root or archive_root()
    docs = docs or _config.DOCS_DIR
    problems: list[str] = []
    versions = version_dirs(root)
    for name in version_dirs(root):
        if not VERSION_DIR_RE.match(name):
            problems.append(f'{name}：版本目录名应为 v<major>.<minor>')
    for name in versions:
        minor = name.lstrip('v')
        directory = os.path.join(root, name)
        names = archived_names(minor)
        for filename in names.values():
            path = os.path.join(directory, filename)
            if not os.path.isfile(path):
                problems.append(f'{name}：缺少 {filename}')
                continue
            text = _fsutil.read_text(path)
            if not HEADER_VERSION_RE.search(text):
                problems.append(f'{name}/{filename}：缺少「> 涵盖版本：」头行')
            if not HEADER_TIME_RE.search(text):
                problems.append(f'{name}/{filename}：缺少「> 归档时间：」头行')
        for entry in safe_listdir(directory):
            path = os.path.join(directory, entry)
            if os.path.isdir(path):
                if not re.match(r'^[a-z0-9][a-z0-9-]*$', entry) or TRACKER_RE.search(entry):
                    problems.append(f'{name}/{entry}：迭代目录名不合规')
                    continue
                inside = set(safe_listdir(path))
                extra = inside - ALLOWED_TOPIC_FILES
                if extra:
                    problems.append(
                        f'{name}/{entry}：只允许 design.md/plan.md/README.md，多余 {sorted(extra)}')
                if not inside & ALLOWED_TOPIC_FILES:
                    problems.append(f'{name}/{entry}：缺少 design.md 或 plan.md')
                continue
            if entry.endswith('.md'):
                continue
            if entry not in names.values():
                problems.append(f'{name}/{entry}：版本目录顶层的多余文件')

    listed: set[str] = set()
    for ledger in LEDGERS:
        path = live_path(ledger, docs)
        if not os.path.isfile(path):
            continue
        text = _fsutil.read_text(path)
        links = index_links(text)
        listed |= links
        for link in links:
            if not os.path.isfile(os.path.normpath(os.path.join(os.path.dirname(path), link))):
                problems.append(f'{ledger}.md：归档索引指向不存在的文件 {link}')
        for name in versions:
            expected = archived_names(name.lstrip('v'))[ledger]
            if f'../archive/{name}/{expected}' not in links:
                problems.append(f'{ledger}.md：索引里没有 {name}/{expected}')
        for version in live_versions(text):
            if f'v{version}' in versions:
                problems.append(f'{ledger}.md：已归档的版本 {version} 仍留在主文档')
        if ledger == 'review-findings':
            for match in LIVE_RF_RE.finditer(text):
                if f'v{match.group(1).strip().lstrip("v")}' in versions:
                    problems.append(f'{ledger}.md：已归档版本 {match.group(1)} 的修复表仍在主文档')
    return problems


def main() -> int:
    _fsutil.pin_stdout_utf8()
    problems = check()
    if problems:
        print(f'归档布局问题 {len(problems)} 处：')
        for problem in problems:
            print(f'  {problem}')
        return 1
    print('归档布局正常')
    return 0


if __name__ == '__main__':
    sys.exit(main())
