#!/usr/bin/env python3
"""The smart audit's full report path (helper-level, no fixture book)."""
from __future__ import annotations

import importlib
import unittest

import _fixture
from _cases import FixtureCase

_fixture.ensure_tools_path()

_smart = importlib.import_module('smart')


class TestSmartAuditDeep(FixtureCase):
    RICH = (
        '# 第1章 测试章节\n\n'
        '> **本章导读**: 导读。\n\n'
        '## 1.1 小节\n\n'
        '展示组件之间的调用关系与数据流向，便于读者建立整体认识。\n\n'
        '```text\n┌──────┐\n│ 组件 │\n└──────┘\n```\n\n'
        '**图 1-1: 展示组件 A 的调用路径**\n\n'
        '如图 1-1 所示，调用链清晰。\n\n'
        '```text\n┌───┐\n│ B │\n└───┘\n```\n\n'
        '**图 1-2: 对比组件 B 与 A 的差异**\n\n'
        '## 1.2 小节\n\n'
        '```java\nclass A {}\n```\n\n'
        '**图 1-3: 标注未引用图的情形**\n\n'
        '## 1.9 本章小结\n\n小结。\n'
    )

    def test_full_report_path(self):
        self.write('data/manuscript/ch1-test.md', self.RICH)
        code, out = self.run_script('smart.py')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertNotIn('Traceback', out)


if __name__ == '__main__':
    unittest.main()
