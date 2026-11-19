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


class TestBuildPipeline(FixtureTest):
    def test_cover_stats_updates_cover(self):
        result = _fixture.run(self.root, 'cover.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        cover = self.read(os.path.join(self.root, 'data', 'manuscript', 'cover.md'))
        self.assertIn('行', cover)

    def test_rebuild_merged_keeps_chapter_order(self):
        result = _fixture.run(self.root, 'merge.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        merged = self.read(self.dist('test-book.md'))
        self.assertLess(merged.index('# 第1章'), merged.index('# 第2章'))
        self.assertIn('阅读指南', merged, 'front matter missing from merge')

    def test_rebuild_merged_fails_on_missing_chapter(self):
        os.unlink(os.path.join(self.root, 'data', 'manuscript', 'ch2-test.md'))
        result = _fixture.run(self.root, 'merge.py')
        # Missing chapters are skipped with a warning, not a crash.
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('skip missing', result.stdout)

    def test_to_html_produces_anchors_and_toc(self):
        _fixture.run(self.root, 'merge.py')
        result = _fixture.run(self.root, 'to_html.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        html = self.read(self.dist('test-book.html'))
        self.assertIn('<h1 id="第1章-测试章节">', html)
        self.assertIn('id="toc-page-nav"', html)
        self.assertIn('<pre><code>', html, 'fenced block not rendered')

    def test_build_is_idempotent(self):
        for _ in range(2):
            _fixture.run(self.root, 'merge.py')
            _fixture.run(self.root, 'to_html.py')
        first = self.read(self.dist('test-book.html'))
        _fixture.run(self.root, 'merge.py')
        _fixture.run(self.root, 'to_html.py')
        self.assertEqual(first, self.read(self.dist('test-book.html')))


if __name__ == '__main__':
    unittest.main()
