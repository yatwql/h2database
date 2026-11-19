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

TAGS = ('layer:manuscript', 'tier:fast')

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

class TestGlossaryBuilder(FixtureCase):
    def test_parse_glossary_v6(self):
        builder = self.module('glossary')
        entries = builder.parse_glossary_v6()
        self.assertIn('ACID', entries)
        self.assertEqual(entries['ACID']['chapters'], [1])
        self.assertTrue(entries['ACID']['section_refs'])

    def test_parse_glossary_skips_malformed_lines(self):
        builder = self.module('glossary')
        self.write('data/manuscript/back/glossary.md',
                   '# 术语表\n\n## A\n\n- 无加粗术语\n- **Term**: 释义\n  **章节**：第2章 §2.1\n')
        entries = builder.parse_glossary_v6()
        self.assertEqual(list(entries), ['Term'])

if __name__ == '__main__':
    unittest.main()
