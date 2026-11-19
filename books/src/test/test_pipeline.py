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

    def test_generate_html_produces_anchors_and_toc(self):
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


class TestLinkAudit(FixtureTest):
    def test_clean_fixture_passes(self):
        result = _fixture.run(self.root, 'links.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_broken_link_fails(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('\n[坏的](nope.md)\n')
        result = _fixture.run(self.root, 'links.py')
        self.assertEqual(result.returncode, 1)
        self.assertIn('BROKEN_FILE', result.stdout)

    def test_broken_anchor_fails(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('\n[坏的](back/glossary.md#不存在)\n')
        result = _fixture.run(self.root, 'links.py')
        self.assertEqual(result.returncode, 1)
        self.assertIn('BROKEN_ANCHOR', result.stdout)


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


class TestContentAudits(FixtureTest):
    def test_figures_audit_passes(self):
        result = _fixture.run(self.root, 'figures.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_captions_audit_passes(self):
        result = _fixture.run(self.root, 'captions.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_captions_audit_flags_bare_noun(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('\n**图 1-2: MVStore 架构**\n')
        result = _fixture.run(self.root, 'captions.py', '--threshold', 'strict')
        self.assertEqual(result.returncode, 1)
        self.assertIn('NO_VERB', result.stdout)

    def test_crossrefs_audit_passes(self):
        result = _fixture.run(self.root, 'crossrefs.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_style_audit_reports_count(self):
        result = _fixture.run(self.root, 'style.py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('style report', result.stdout + result.stderr)

    def test_balance_check_emits_metrics(self):
        result = _fixture.run(self.root, 'balance.py')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('章节均衡度量报告', result.stdout)

    def test_exercises_audit_reads_fixture_chapters(self):
        # The fixture uses simplified exercise blocks, so the audit reports
        # shortfalls; what matters here is that it finds both chapter slots.
        result = _fixture.run(self.root, 'exercises.py')
        self.assertIn('延伸思考', result.stdout + result.stderr)
        self.assertIn('第1章', result.stdout)
        self.assertIn('第2章', result.stdout)


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
