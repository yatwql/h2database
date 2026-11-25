#!/usr/bin/env python3
"""In-process smoke + behaviour tests for every delivery script.

Each script is executed with ``runpy`` against the fixture book, so coverage
counts the real code paths (a subprocess run would not) while staying
deterministic and offline.

Environment-dependent scripts (PDF/EPUB toolchain) run only when their
optional dependencies are importable; otherwise they are skipped by name so the
gap stays visible instead of silently passing.
"""

import os
import sys
import unittest
from unittest import mock

from _cases import ScriptTestBase

TAGS = ("layer:render", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class TestBuildScripts(ScriptTestBase):
    def test_cover_stats_runs(self):
        code, out = self.run_script("cover.py")
        self.assertEqual(code, 0, out)
        self.assertIn("cover.md", out)

    def test_cover_without_a_book_date_keeps_the_printed_date(self):
        # book_updated() is "" only when git has no history for the manuscript and no
        # file under it can be stat'ed; cover.md itself must exist to be rewritten, so
        # the fixture cannot reach that shape and the date source is stubbed instead.
        with mock.patch("lib._book_versions.BookVersions.book_updated", return_value=""):
            code, out = self.run_script("cover.py")
        self.assertEqual(code, 0, out)
        after = self.read("data", "manuscript", "cover.md")
        self.assertIn("版本 v0.1 · 2026-01-01 · ", after)
        self.assertNotIn("1,000 行", after)

    def test_rebuild_merged_writes_dist(self):
        code, out = self.run_script("merge.py")
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isfile(self.path("dist", "test-book.md")))

    def test_to_html_runs_after_merge(self):
        self.run_script("merge.py")
        code, out = self.run_script("to_html.py")
        self.assertEqual(code, 0, out)
        html = self.read("dist", "test-book.html")
        self.assertIn('<h1 id="第1章-测试章节">', html)
        self.assertIn('id="toc-page-nav"', html)


if __name__ == "__main__":
    unittest.main()
