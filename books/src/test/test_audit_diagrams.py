#!/usr/bin/env python3
"""End-to-end tests: run the delivery scripts against a fixture book.

Each test materialises a miniature book (book.toml + manuscript/ + dist/) in a
temporary directory, points BOOK_ROOT at it, and asserts the script's real
behaviour. This is what catches path drift, config wiring mistakes and
regressions in the audits — the class of bug unit tests cannot see.
"""

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

class FixtureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def dist(self, name: str) -> str:
        return os.path.join(self.root, 'dist', name)

    def read(self, path: str) -> str:
        with open(path, encoding='utf-8') as fh:
            return fh.read()

class TestAsciiAudit(FixtureTest):
    def test_clean_fixture_passes(self):
        result = _fixture.run(self.root, 'diagrams.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_wide_diagram_fails(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('\n```text\n' + 'x' * 120 + '\n```\n')
        result = _fixture.run(self.root, 'diagrams.py')
        self.assertEqual(result.returncode, 1)
        self.assertIn('WIDE_LINE', result.stdout)

    def test_baseline_absorbs_known_violation(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('\n```text\n' + 'x' * 120 + '\n```\n')
        self.assertEqual(
            _fixture.run(self.root, 'diagrams.py', '--update-baseline').returncode, 0)
        self.assertEqual(_fixture.run(self.root, 'diagrams.py').returncode, 0)

if __name__ == '__main__':
    unittest.main()
