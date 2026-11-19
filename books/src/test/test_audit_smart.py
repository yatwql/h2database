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

class TestSmartAuditHelpers(FixtureCase):
    def test_count_diagrams_detects_blocks(self):
        smart = self.module('smart')
        text = '```text\n┌──┐\n│ab│\n└──┘\n```\n'
        self.assertEqual(smart.count_diagrams(text), 1)

    def test_count_diagrams_ignores_short_blocks(self):
        smart = self.module('smart')
        self.assertEqual(smart.count_diagrams('```text\nab\n```\n'), 0)

    def test_build_exempt_ranges_for_appendix_file(self):
        smart = self.module('smart')
        lines = ['# 附录 A 案例研究', '', '## 附：小节', '正文']
        headings = [(1, '附录 A 案例研究', 1), (2, '附：小节', 3)]
        ranges = smart.build_exempt_ranges(headings, lines)
        self.assertIsInstance(ranges, list)

    def test_check_figure_refs_runs(self):
        smart = self.module('smart')
        smart.check_figure_refs()  # prints a report; must not raise

if __name__ == '__main__':
    unittest.main()
