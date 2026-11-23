#!/usr/bin/env python3
"""version_consistency: the name and version rules that only fire on drift."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class VersionConsistencyRulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'version_consistency')

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    def title(self) -> str:
        return self.mod._config.current().title or '测试之书'

    def test_a_document_without_the_software_name_is_reported(self):
        self.write('docs/managements/plan.md', '# 计划\n\n> 版本：v0.1\n\n没有称号。\n')
        problems = self.mod.software_problems()
        self.assertTrue(any('plan.md' in problem for problem in problems), problems)

    def test_a_document_that_names_one_book_is_reported(self):
        title = self.title()
        self.write('docs/managements/plan.md',
                   f'# 计划\n\n> 版本：v0.1\n\n这本书叫《{title}》。\n')
        problems = self.mod.title_problems()
        self.assertTrue(any('plan.md' in problem for problem in problems), problems)

    def test_a_readme_that_names_one_book_is_reported(self):
        title = self.title()
        self.write('README.md', f'# README\n\n本仓构建《{title}》。\n')
        problems = self.mod.title_problems()
        self.assertTrue(any('README.md' in problem for problem in problems), problems)

    def test_a_cover_whose_version_disagrees_is_reported(self):
        self.write('data/manuscript/cover.md',
                   f'# {self.title()}\n\n版本 v9.9 · 2026-01-01\n')
        problems = self.mod.cover_problems()
        self.assertTrue(any('v9.9' in problem for problem in problems), problems)

    def test_an_artifact_text_is_none_when_it_cannot_be_read(self):
        broken = os.path.join(self.root, 'dist', 'broken.pdf')
        os.makedirs(os.path.dirname(broken), exist_ok=True)
        with open(broken, 'wb') as fh:
            fh.write(b'not a pdf')
        self.assertIsNone(self.mod.artifact_text(broken))

    def test_html_text_is_read_directly(self):
        path = self.write('dist/test-book.html', '<p>正文</p>')
        self.assertIn('正文', self.mod.artifact_text(path) or '')

    def test_json_mode_reports_every_section(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, 0 if not payload['problems'] else 1)
        for key in ('versions', 'problems', 'warnings'):
            self.assertIn(key, payload)


if __name__ == '__main__':
    unittest.main()
