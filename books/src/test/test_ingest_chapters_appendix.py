#!/usr/bin/env python3
"""Appendix rendering: coordinates table, exercises and summary from the inventory."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:ingest', 'tier:fast')

_fixture.ensure_tools_path()

class AppendixRenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, 'chapters')
        self.spec: dict = {}

    def with_spec(self, spec: dict) -> None:
        self.spec = spec

    def chapter(self, packages: dict | None = None) -> dict:
        return {'file': 'appendix-z.md', 'source_lines': 100,
                'packages': packages if packages is not None else {}}

    def test_unknown_appendix_yields_nothing(self):
        self.with_spec({})
        self.assertEqual(self.chapters.render_appendix(self.chapter(), self.spec), '')

    def test_appendix_without_packages_explains_the_cross_reference(self):
        self.with_spec({'appendix-z.md': (7, '附录 Z 案例')})
        text = self.chapters.render_appendix(self.chapter(), self.spec)
        self.assertIn('## 7.1 附录 Z 案例', text)
        self.assertIn('不拥有源码包', text)
        self.assertIn('## 7.2 延伸思考', text)
        self.assertIn('## 7.3 本章小结', text)

    def test_appendix_with_packages_lists_coordinates(self):
        self.with_spec({'appendix-z.md': (7, '附录 Z 案例')})
        packages = {'org.example': {
            'lines': 120, 'files': 3,
            'key_classes': [{'name': 'Widget', 'lines': 40, 'public_methods': 2,
                             'rel': 'org/example/Widget.java',
                             'api': ['run'], 'api_lines': {'run': 12}}],
            'depends_on': {},
        }}
        text = self.chapters.render_appendix(self.chapter(packages), self.spec)
        self.assertIn('`Widget.run()`', text)
        self.assertIn('`org/example/Widget.java:12`', text)
        self.assertIn('可核验的源码坐标', text)

    def test_class_without_rel_is_skipped(self):
        self.with_spec({'appendix-z.md': (7, '附录 Z 案例')})
        packages = {'org.example': {
            'lines': 10, 'files': 1,
            'key_classes': [{'name': 'Anon', 'lines': 3, 'public_methods': 0,
                             'rel': '', 'api': [], 'api_lines': {}}],
            'depends_on': {},
        }}
        text = self.chapters.render_appendix(self.chapter(packages), self.spec)
        self.assertNotIn('Anon', text)

if __name__ == '__main__':
    unittest.main()


class AppendixAppendTest(unittest.TestCase):
    """Appending the coordinate block: skip, dry run, and the real write."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, 'chapters')
        self.file = 'appendix-z.md'
        self.spec = {self.file: (7, '附录 Z', '附录')}

    def write(self, text: str) -> str:
        path = os.path.join(self.root, 'data', 'manuscript', self.file)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)
        return path

    def chapter(self) -> dict:
        return {'file': self.file, 'source_lines': 10, 'packages': {}}

    def run_append(self, dry_run: bool, block: str = '正文\n') -> str:
        with mock.patch.dict(self.chapters.APPENDIX_SPEC, self.spec), \
                mock.patch.object(self.chapters, 'render_appendix', return_value=block), \
                mock.patch.object(self.chapters, '_config') as config, \
                redirect_stdout(io.StringIO()):
            config.manuscript.side_effect = lambda name: os.path.join(
                self.root, 'data', 'manuscript', name)
            return self.chapters._append_appendix(self.chapter(), dry_run)

    def test_a_block_already_present_is_skipped(self):
        self.write('# 附录 Z\n\n## 7.1 已有\n')
        self.assertEqual(self.run_append(False), 'skip')

    def test_a_dry_run_reports_without_writing(self):
        path = self.write('# 附录 Z\n\n正文\n')
        before = open(path, encoding='utf-8').read()
        self.assertEqual(self.run_append(True), 'written')
        self.assertEqual(open(path, encoding='utf-8').read(), before)

    def test_a_missing_appendix_file_is_created_with_the_block(self):
        self.spec[self.file] = (7, '附录 Z', '附录')
        outcome = self.run_append(False, '## 7.1 坐标\n')
        self.assertEqual(outcome, 'written')
        path = os.path.join(self.root, 'data', 'manuscript', self.file)
        self.assertIn('## 7.1 坐标', open(path, encoding='utf-8').read())
