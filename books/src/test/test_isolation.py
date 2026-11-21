#!/usr/bin/env python3
"""The suite runs offline and never touches the checked-out book."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:infra', 'tier:fast')

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

class IsolationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fsutil = _fixture.load_module(BOOK_ROOT, '_fsutil')

    def test_the_guards_are_installed_on_import(self):
        self.assertTrue(os.environ.get('BOOK_TEST_GUARD'))
        self.assertEqual(os.environ.get('BOOK_LLM_OFFLINE'), '1')

    def test_writing_the_real_manuscript_is_refused(self):
        target = os.path.join(BOOK_ROOT, 'data', 'manuscript', 'ch1.md')
        with self.assertRaises(RuntimeError):
            self.fsutil.write_text(target, 'x')

    def test_regenerable_artifacts_may_be_rebuilt(self):
        target = os.path.join(self.tmp.name, 'dist', 'merged.md')
        os.makedirs(os.path.dirname(target), exist_ok=True)
        self.fsutil.write_text(target, 'x')
        with open(target, encoding='utf-8') as fh:
            self.assertEqual(fh.read(), 'x')

    def test_a_fixture_book_may_still_be_written(self):
        target = os.path.join(self.tmp.name, 'data', 'manuscript', 'ch1.md')
        os.makedirs(os.path.dirname(target), exist_ok=True)
        self.fsutil.write_text(target, 'x')
        with open(target, encoding='utf-8') as fh:
            self.assertEqual(fh.read(), 'x')

    def test_a_fixture_book_logs_inside_its_own_root(self):
        root = _fixture.build_book(tempfile.mkdtemp())
        log = _fixture.load_module(root, '_log')
        self.assertTrue(log.log_dir().startswith(root))

    def test_a_real_provider_cannot_reach_the_network(self):
        """The socket guard is the last line: a real provider attempt raises."""
        import socket

        import _netguard
        with self.assertRaises(_netguard.BlockedNetwork):
            socket.create_connection(('api.deepseek.com', 443), timeout=0.01)

    def test_a_mock_provider_still_answers(self):
        llm = _fixture.load_module(BOOK_ROOT, '_llm')
        provider = {'kind': 'mock', 'models': ['m']}
        with mock.patch.object(llm, 'providers', lambda: {'providers': {'p': provider}}), \
                mock.patch.object(llm, 'resolve',
                                  lambda *a, **k: {'provider': 'p', 'settings': {}}):
            self.assertIn('hello', llm.complete('hello', scenario='summary'))


if __name__ == '__main__':
    unittest.main()
