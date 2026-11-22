#!/usr/bin/env python3
"""Docs archive gate: layout, headers, index and stale live sections."""
from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

CHANGELOG = """# 变更日志
> 版本：v0.1
---
## [0.1] - 开发中（未发布）
### 变更
- 第一件事
## 归档
"""

PLAN = """# 实施与维护计划
## 概述
在办 1 项。
"""

RF = """# 自我审查问题记录
## 当前待处理问题
| # | 问题 |
| --- | --- |
### 本版本已修复（0.1）
| # | 问题 | 修复 |
| --- | --- | --- |
| rf-1 | 某问题 | 某修复 |
## 归档
"""


def write_docs(root: str) -> None:
    """A miniature docs tree with the three live ledgers."""
    os.makedirs(os.path.join(root, 'managements'), exist_ok=True)
    os.makedirs(os.path.join(root, 'archive'), exist_ok=True)
    for name, text in (('changelog', CHANGELOG), ('plan', PLAN), ('review-findings', RF)):
        with open(os.path.join(root, 'managements', f'{name}.md'), 'w', encoding='utf-8') as fh:
            fh.write(text)


class ArchiveGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        write_docs(self.tmp)
        self.mod = importlib.import_module('audit.doc_archive')
        self.root = os.path.join(self.tmp, 'archive')

    def archive(self, name: str = 'v0.1', ledgers=('changelog', 'plan', 'review-findings'),
                header=True) -> None:
        directory = os.path.join(self.root, name)
        os.makedirs(directory, exist_ok=True)
        minor = name.lstrip('v')
        for ledger in ledgers:
            text = f'# {ledger}\n'
            if header:
                text += '> 涵盖版本：0.1\n> 归档时间：2026-11-22\n'
            with open(os.path.join(directory, f'archived_{ledger}.{minor}.md'),
                      'w', encoding='utf-8') as fh:
                fh.write(text)

    def test_an_empty_archive_is_green(self):
        self.assertEqual(self.mod.check(self.root, self.tmp), [])

    def test_a_version_directory_without_ledgers_is_reported(self):
        os.makedirs(os.path.join(self.root, 'v0.1'))
        problems = self.mod.check(self.root, self.tmp)
        self.assertTrue(any('缺少 archived_changelog.0.1.md' in p for p in problems))

    def test_a_missing_header_line_is_reported(self):
        self.archive(header=False)
        problems = self.mod.check(self.root, self.tmp)
        self.assertTrue(any('涵盖版本' in p for p in problems))

    def test_a_bad_version_directory_name_is_reported(self):
        self.archive('0.1')
        problems = self.mod.check(self.root, self.tmp)
        self.assertTrue(any('v<major>.<minor>' in p for p in problems))

    def test_an_unlisted_version_is_reported(self):
        self.archive()
        problems = self.mod.check(self.root, self.tmp)
        self.assertTrue(any('索引里没有 v0.1' in p for p in problems))

    def test_a_released_section_still_live_is_reported(self):
        self.archive()
        path = os.path.join(self.tmp, 'managements', 'changelog.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(CHANGELOG.replace('## 归档', '## 归档\n'
                                       '- [x](../archive/v0.1/archived_changelog.0.1.md)'))
        problems = self.mod.check(self.root, self.tmp)
        self.assertTrue(any('仍留在主文档' in p for p in problems))

    def test_a_topic_directory_with_extra_files_is_reported(self):
        self.archive()
        topic = os.path.join(self.root, 'v0.1', 'diagram-upgrade')
        os.makedirs(topic)
        with open(os.path.join(topic, 'design.md'), 'w', encoding='utf-8') as fh:
            fh.write('# 设计\n')
        with open(os.path.join(topic, 'notes.txt'), 'w', encoding='utf-8') as fh:
            fh.write('x\n')
        problems = self.mod.check(self.root, self.tmp)
        self.assertTrue(any('只允许 design.md/plan.md/README.md' in p for p in problems))

    def test_a_topic_directory_with_a_tracker_id_is_reported(self):
        self.archive()
        os.makedirs(os.path.join(self.root, 'v0.1', 'plan-3-foo'))
        problems = self.mod.check(self.root, self.tmp)
        self.assertTrue(any('迭代目录名不合规' in p for p in problems))

    def test_a_dangling_index_link_is_reported(self):
        self.archive()
        path = os.path.join(self.tmp, 'managements', 'changelog.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(CHANGELOG.replace(
                '## 归档',
                '## 归档\n- [gone](../archive/v0.1/archived_changelog.0.9.md)'))
        problems = self.mod.check(self.root, self.tmp)
        self.assertTrue(any('不存在的文件' in p for p in problems))



if __name__ == '__main__':
    unittest.main()
