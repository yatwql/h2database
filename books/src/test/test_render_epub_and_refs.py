#!/usr/bin/env python3
"""EPUB verify, source refs and figure clusters: the remaining audit tails."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:render', 'tier:fast')

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

class EpubVerifyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'verify_epub')

    def test_missing_epub_is_reported(self):
        report = self.mod.verify(os.path.join(self.tmp.name, 'none.epub'))
        self.assertFalse(report.to_dict()['ok'])

    def test_main_reports_a_missing_file(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(['--epub', os.path.join(self.tmp.name, 'none.epub')])
        self.assertEqual(code, 1)
        self.assertTrue(buffer.getvalue())

    def test_json_output_structure(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.mod.main(['--epub', os.path.join(self.tmp.name, 'none.epub'), '--json'])
        payload = json.loads(buffer.getvalue())
        self.assertIn('ok', payload)

class FigureClusterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'figure_clusters')

    def test_a_cluster_without_a_bridge_is_reported(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('# 第1章 测试\n\n'
                     '**图 1-1: 展示组件的连接方式**\n\n'
                     '**图 1-2: 展示组件的调用顺序**\n')
        code, out = _fixture.run_inproc(self.root, 'figure_clusters.py')
        self.assertEqual(code, 0, out[-400:])
        self.assertIn('图簇检测', out)
        self.assertNotIn('Traceback', out)

    def test_json_output_runs(self):
        code, out = _fixture.run_inproc(self.root, 'figure_clusters.py', '--json')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('unbridged', out)

class SourceRefsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'source_refs')

    def test_report_prints_a_summary(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer), \
                mock.patch.object(self.mod, 'build_class_index', return_value={}):
            code = self.mod.main([])
        self.assertEqual(code, 0)
        self.assertIn('source', buffer.getvalue().lower())

    def test_missing_source_tree_skips_cleanly(self):
        with mock.patch.object(self.mod, 'build_class_index', return_value={}):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = self.mod.main([])
        self.assertEqual(code, 0)

    def test_suggest_reports_a_missing_class(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('# 第1章 测试\n\n调用 `Ghost.java:3`。\n')
        buffer = io.StringIO()
        with redirect_stdout(buffer), \
                mock.patch.object(self.mod, 'build_class_index', return_value={}), \
                mock.patch.object(self.mod, 'CHAPTER_FILES', ['ch1-test.md'], create=True):
            code = self.mod.main(['--suggest'])
        self.assertEqual(code, 0, buffer.getvalue()[-300:])
        self.assertRegex(buffer.getvalue(), r'[\s\S]')

if __name__ == '__main__':
    unittest.main()
