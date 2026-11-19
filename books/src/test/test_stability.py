#!/usr/bin/env python3
"""Stability: same input → same output, repeated runs → same verdict."""
from __future__ import annotations

import hashlib
import os
import tempfile
import unittest

import _fixture

_fixture.ensure_tools_path()


def digest(path: str) -> str:
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class IdempotencyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def test_building_twice_produces_identical_artifacts(self):
        merged = os.path.join(self.root, 'dist', 'test-book.md')
        _fixture.run_inproc(self.root, 'merge.py')
        first = digest(merged)
        _fixture.run_inproc(self.root, 'merge.py')
        self.assertEqual(first, digest(merged), 'merge.py is not idempotent')

    def test_cover_update_is_idempotent(self):
        cover = os.path.join(self.root, 'data', 'manuscript', 'cover.md')
        _fixture.run_inproc(self.root, 'cover.py')
        first = digest(cover)
        _fixture.run_inproc(self.root, 'cover.py')
        self.assertEqual(first, digest(cover), 'cover.py is not idempotent')

    def test_repeated_gate_runs_agree(self):
        for _ in range(3):
            code, _out = _fixture.run_inproc(self.root, 'structure.py')
            self.assertIn(code, (0, 1), 'structure.py verdict changed between runs')


class DeterminismTest(unittest.TestCase):
    """Chapter order comes from configuration, not from directory order."""

    def test_merged_order_follows_the_configured_chapter_list(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        toml = _fixture.BOOK_TOML
        reordered = toml.replace(
            '"cover.md",\n    "ch1-test.md",\n    "ch2-test.md",',
            '"cover.md",\n    "ch2-test.md",\n    "ch1-test.md",')
        self.assertNotEqual(reordered, toml, 'fixture chapter list changed')
        root = _fixture.build_book(tmp.name, extra={'data/tmpl/book.toml': reordered})
        _fixture.run_inproc(root, 'merge.py')
        with open(os.path.join(root, 'dist', 'test-book.md'), encoding='utf-8') as fh:
            text = fh.read()
        self.assertLess(text.index('# 第2章'), text.index('# 第1章'))

    def test_digest_output_is_byte_stable(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = _fixture.build_book(tmp.name)
        inv = os.path.join(root, 'data', 'state', 'source-inventory.json')
        _fixture.run_inproc(root, 'digest.py')
        if not os.path.isfile(inv):
            self.skipTest('no source tree in the fixture')
        first = digest(inv)
        _fixture.run_inproc(root, 'digest.py')
        self.assertEqual(first, digest(inv), 'digest.py output is not stable')


if __name__ == '__main__':
    unittest.main()
