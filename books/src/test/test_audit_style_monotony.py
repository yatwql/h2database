#!/usr/bin/env python3
"""Style gate: monotonous sentence openings are reported per paragraph."""
from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

_fixture.ensure_tools_path()


class SentenceOpeningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def add_paragraph(self, text: str) -> None:
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, encoding='utf-8') as fh:
            body = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(body + '\n' + text + '\n')

    def run_style(self):
        return _fixture.run_inproc(self.root, 'style.py')

    def test_three_identical_openings_are_reported(self):
        self.add_paragraph('系统负责协调。系统负责调度。系统负责回收。')
        _code, out = self.run_style()
        self.assertIn('句式单调', out)

    def test_a_sixty_percent_ratio_is_reported(self):
        self.add_paragraph('模块负责读取。模块负责写入。模块负责回滚。另一个组件负责校验。')
        _code, out = self.run_style()
        self.assertIn('句式单调', out)

    def test_varied_openings_are_not_reported(self):
        self.add_paragraph('存储层负责持久化。调度器分发任务。客户端提交请求。')
        _code, out = self.run_style()
        self.assertNotIn('句式单调', out)

    def test_short_paragraphs_are_skipped(self):
        self.add_paragraph('系统负责协调。系统负责调度。')
        _code, out = self.run_style()
        self.assertNotIn('句式单调', out)


if __name__ == '__main__':
    unittest.main()
