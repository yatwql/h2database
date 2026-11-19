#!/usr/bin/env python3
"""Branch coverage for the audit/report paths.

These exercise the error and edge branches (missing files, empty inputs,
threshold violations, alternate CLI modes) that the happy-path tests skip.
"""
import os
import sys
import tempfile
import unittest

import _fixture
from _cases import Base

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def module(self, name: str):
        return _fixture.load_module(self.root, name)

    def run_script(self, script: str, *args: str):
        return _fixture.run_inproc(self.root, script, *args)

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path


class TestStyleAndHtmlBranches(FixtureCase):
    def test_style_on_broken_tables(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n| a | b |\n|---|---|\n| 1 |\n')
        code, out = self.run_script('style.py')
        self.assertIn(code, (0, 1), out[-300:])

    def test_html_handles_unclosed_fence(self):
        self.write('data/manuscript/ch2-test.md',
                   '# 第2章 测试章节\n\n```text\n未闭合\n')
        self.run_script('merge.py')
        code, out = self.run_script('to_html.py')
        self.assertEqual(code, 0, out[-300:])


if __name__ == '__main__':
    unittest.main()


class TestHtmlCoverBranches(Base):
    RICH_COVER = (
        '# 测试之书\n\n'
        '> 版本 v0.1 · 2026-01-01 · 1,000 行\n\n'
        '## 图书信息\n\n'
        '| 项目 | 内容 |\n|------|------|\n| 作者 | 某人 |\n| 页数 | 100 |\n\n'
        '## 阅读指引\n\n正文。\n'
    )

    def test_cover_info_table_rendered(self):
        self.write('data/manuscript/cover.md', self.RICH_COVER)
        self.run_script('merge.py')
        code, out = self.run_script('to_html.py')
        self.assertEqual(code, 0, out[-300:])
        html_path = os.path.join(self.root, 'dist', 'test-book.html')
        with open(html_path, encoding='utf-8') as fh:
            html = fh.read()
        self.assertIn('cover-info', html)

    def test_missing_merged_md(self):
        _code, out = self.run_script('to_html.py')
        self.assertNotIn('Traceback', out)
