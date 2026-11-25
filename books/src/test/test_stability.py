#!/usr/bin/env python3
"""Stability: same input → same output, repeated runs → same verdict."""

from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

TAGS = ('stability:idempotent', 'layer:infra', 'tier:fast')

_fixture.ensure_tools_path()


class IdempotencyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def test_building_twice_produces_identical_artifacts(self):
        merged = os.path.join(self.root, 'dist', 'test-book.md')
        _fixture.run_inproc(self.root, 'merge.py')
        first = _fixture.digest(merged)
        _fixture.run_inproc(self.root, 'merge.py')
        self.assertEqual(first, _fixture.digest(merged), 'merge.py is not idempotent')

    def test_cover_update_is_idempotent(self):
        cover = os.path.join(self.root, 'data', 'manuscript', 'cover.md')
        _fixture.run_inproc(self.root, 'cover.py')
        first = _fixture.digest(cover)
        _fixture.run_inproc(self.root, 'cover.py')
        self.assertEqual(first, _fixture.digest(cover), 'cover.py is not idempotent')

    def test_repeated_gate_runs_agree(self):
        runs = [_fixture.run_inproc(self.root, 'structure.py') for _ in range(3)]
        codes = {code for code, _out in runs}
        self.assertEqual(len(codes), 1, [out[-200:] for _code, out in runs])
        self.assertEqual(codes.pop(), 1)
        for _code, out in runs:
            self.assertIn('FAIL:', out)

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
        root = _fixture.build_book(tmp.name, extra={'data/book/book.toml': reordered})
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
        first = _fixture.digest(inv)
        _fixture.run_inproc(root, 'digest.py')
        self.assertEqual(first, _fixture.digest(inv), 'digest.py output is not stable')

if __name__ == '__main__':
    unittest.main()
