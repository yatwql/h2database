#!/usr/bin/env python3
"""Unit tests for the helper functions behind the audits.

These target the pure logic (counting, parsing, clustering, PDF checks) that the
end-to-end tests exercise only indirectly.
"""

import importlib.util
import os
import sys
import tempfile
import unittest

import _fixture

TAGS = ('layer:audit', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

HAS_PYPDF = importlib.util.find_spec('pypdf') is not None

class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def module(self, name: str):
        return _fixture.load_module(self.root, name)

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

class TestBalanceCheckHelpers(FixtureCase):
    def test_count_lines(self):
        bc = self.module('balance')
        self.assertEqual(bc.count_lines('a\nb\nc\n'), 3)

    def test_count_figures(self):
        bc = self.module('balance')
        text = '**图 1-1: 展示**\n**图 2-3: 对比**\n**图 A-1: 标注**\n'
        self.assertEqual(bc.count_figures(text), 3)

    def test_count_source_refs(self):
        bc = self.module('balance')
        self.assertEqual(bc.count_source_refs('见 MVStore.java:12 与 Page.java:7'), 2)

    def test_glossary_chapter_index(self):
        bc = self.module('balance')
        index = bc.load_glossary_chapter_index()
        self.assertIsInstance(index, dict)
        self.assertTrue(index, 'fixture glossary should contribute chapter hits')

    def test_index_chapter_index(self):
        bc = self.module('balance')
        index = bc.load_index_chapter_index()
        self.assertIsInstance(index, dict)

    def test_collect_metrics_and_render(self):
        bc = self.module('balance')
        metrics = bc.collect_metrics()
        self.assertIn('totals', metrics)
        self.assertGreaterEqual(metrics['totals']['files'], 1)
        rendered = bc.render_markdown(metrics)
        self.assertIn('| 文件 |', rendered)

    def test_render_diff(self):
        bc = self.module('balance')
        current = bc.collect_metrics()
        baseline = bc.collect_metrics()
        diff = bc.render_diff(current, baseline)
        self.assertIsInstance(diff, str)

if __name__ == '__main__':
    unittest.main()
