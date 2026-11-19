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
from _cases import ScriptTestBase

TAGS = ('layer:infra', 'tier:fast')

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

class TestToolchainEntryPoint(FixtureTest):
    def test_make_test_and_check_run(self):
        result = _fixture.run(self.root, 'make.py', 'check', '--only', 'audit_links,audit_ascii')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('OK', result.stdout)

    def test_make_unknown_step_fails(self):
        result = _fixture.run(self.root, 'make.py', 'check', '--only', 'nope')
        self.assertNotEqual(result.returncode, 0)

if __name__ == '__main__':
    unittest.main()

class TestMakeEntryPoint(ScriptTestBase):
    def test_make_doctor(self):
        code, out = _fixture.run_inproc(self.root, 'make.py', 'doctor')
        self.assertIn(code, (0, 1), out)
        self.assertIn('python', out)

    def test_make_build_only(self):
        code, out = _fixture.run_inproc(
            self.root, 'make.py', 'build', '--only', 'cover_stats')
        self.assertEqual(code, 0, out)
