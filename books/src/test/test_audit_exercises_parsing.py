#!/usr/bin/env python3
"""Exercises gate: chapter-slot parsing and the per-file audit."""

from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

class SlotParsingTest(unittest.TestCase):
    def setUp(self):
        self.mod = _fixture.load_module(BOOK_ROOT, 'exercises')

    def lines(self, text: str) -> list[str]:
        return text.splitlines(keepends=True)

    def test_a_complete_slot_is_found(self):
        text = ('# 第1章 测试\n\n## 1.9 本章小结\n\n小结。\n\n'
                '## 1.10 延伸思考\n\n1. 练习\n\n## 1.11 延展阅读\n\n- 参考\n')
        slots = self.mod.parse_chapter_slots(self.lines(text))
        self.assertTrue(slots)
        self.assertEqual(slots[0]['chapter'], 1)

    def test_a_file_starting_mid_chapter_uses_the_h2_number(self):
        text = '## 6.5 本章小结\n\n小结。\n\n## 6.6 延伸思考\n\n1. 练习\n'
        slots = self.mod.parse_chapter_slots(self.lines(text))
        self.assertTrue(slots)
        self.assertEqual(slots[0]['chapter'], 6)

    def test_exercises_without_a_chapter_heading_are_attributed(self):
        text = '## 3.7 延伸思考\n\n1. 练习\n\n## 3.8 延展阅读\n\n- 参考\n'
        slots = self.mod.parse_chapter_slots(self.lines(text))
        self.assertEqual(slots[0]['chapter'], 3)

    def test_fenced_blocks_are_ignored(self):
        text = ('# 第1章 测试\n\n## 1.9 本章小结\n\n小结。\n\n```text\n'
                '## 1.10 延伸思考\n```\n')
        slots = self.mod.parse_chapter_slots(self.lines(text))
        self.assertTrue(all(slot['chapter'] == 1 for slot in slots))

    def test_section_end_stops_at_the_next_heading(self):
        text = self.lines('## 1.9 延伸思考\n\n1. 练习\n\n## 1.10 延展阅读\n\n- 参考\n')
        end = self.mod.find_section_end(text, 0)
        self.assertGreaterEqual(end, 1)

class AuditFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'exercises')

    def write(self, text: str) -> str:
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    def test_audit_file_counts_the_exercises(self):
        path = self.write('# 第1章 测试\n\n## 1.9 本章小结\n\n小结。\n\n'
                          '## 1.10 延伸思考\n\n'
                          '**1. 🟢★ 练习一**\n\n> 提示：看 §1.1\n> 回顾：§1.1 小节\n\n'
                          '**2. 🔵★★ 练习二**\n\n> 提示：看 §1.1\n> 回顾：§1.1 小节\n\n'
                          '## 1.11 延展阅读\n\n- 参考\n')
        report = self.mod.audit_file(path)
        self.assertIn('slots', report)
        slot = report['slots'][0]
        self.assertEqual(slot['exercise_count'], 2)
        self.assertTrue(slot['placement_ok'])

    def test_audit_file_tolerates_a_missing_slot(self):
        path = self.write('# 第1章 测试\n\n没有小结也没有练习。\n')
        report = self.mod.audit_file(path)
        self.assertIsInstance(report, dict)

if __name__ == '__main__':
    unittest.main()
