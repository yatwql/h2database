#!/usr/bin/env python3
"""End-to-end tests: run the delivery scripts against a fixture book.

Each test materialises a miniature book (book.toml + manuscript/ + dist/) in a
temporary directory, points BOOK_ROOT at it, and asserts the script's real
behaviour. This is what catches path drift, config wiring mistakes and
regressions in the audits — the class of bug unit tests cannot see.
"""

import os
import sys
import unittest

import _fixture
from _cases import FixtureCase

TAGS = ("layer:audit", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class TestContentAudits(FixtureCase):
    def test_each_content_audit_passes_on_the_fixture(self):
        # one case per script rather than one test per script: the assertion is the
        # same, and subTest still names the script that failed
        for script in ("figures.py", "captions.py", "crossrefs.py"):
            with self.subTest(script=script):
                result = _fixture.run(self.root, script)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_crossrefs_audit_separates_matching_and_unknown_chapters(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n详见第2章《测试章节》，详见第9章《空章节》。\n")
        code, out = _fixture.run_inproc(self.root, "crossrefs.py")
        self.assertEqual(code, 0, out)
        self.assertIn("CHAPTER_NOT_FOUND", out)
        self.assertIn("OK: 1, Errors: 3", out)

    def test_crossrefs_audit_confirms_a_book_whose_references_all_match(self):
        chapters = {
            "ch1-test.md": "# 第1章 测试章节\n\n详见第2章《测试章节》。\n",
            "ch2-test.md": "# 第2章 测试章节\n\n正文一段。\n",
        }
        for name, text in chapters.items():
            path = os.path.join(self.root, "data", "manuscript", name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        code, out = _fixture.run_inproc(self.root, "crossrefs.py")
        self.assertEqual(code, 0, out)
        self.assertIn("All cross-references match!", out)
        self.assertIn("OK: 1, Errors: 0", out)

    def test_captions_audit_flags_bare_noun(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n**图 1-2: MVStore 架构**\n")
        result = _fixture.run(self.root, "captions.py", "--threshold", "strict")
        self.assertEqual(result.returncode, 1)
        self.assertIn("NO_VERB", result.stdout)

    def test_style_audit_reports_count(self):
        result = _fixture.run(self.root, "style.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("style report", result.stdout + result.stderr)

    def test_balance_check_emits_metrics(self):
        result = _fixture.run(self.root, "balance.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("章节均衡度量报告", result.stdout)

    def test_exercises_audit_reads_fixture_chapters(self):
        # The fixture uses simplified exercise blocks, so the audit reports
        # shortfalls; what matters here is that it finds both chapter slots.
        result = _fixture.run(self.root, "exercises.py")
        self.assertIn("延伸思考", result.stdout + result.stderr)
        self.assertIn("第1章", result.stdout)
        self.assertIn("第2章", result.stdout)


class TestFigureCitations(FixtureCase):
    """figures.py: cited figures, dangling citations, and the strict verdict."""

    def write_chapter(self, name: str, text: str) -> str:
        path = os.path.join(self.root, "data", "manuscript", name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def audit(self, text: str) -> dict:
        path = self.write_chapter("ch3-test.md", text)
        figures = _fixture.load_module(self.root, "figures")
        return figures.audit([path])

    def test_a_cited_figure_is_not_reported_as_uncited(self):
        result = self.audit("**图 3-1: 结构**\n\n如图 3-1 所示，结构清晰。\n")
        self.assertEqual(result["uncited"], [])
        self.assertEqual(result["dangling"], [])

    def test_a_citation_without_its_figure_is_dangling(self):
        result = self.audit("如图 3-7 所示，这一幅并不存在。\n")
        self.assertEqual([name for name, _ids in result["dangling"]], ["ch3-test.md"])

    def test_strict_fails_on_a_dangling_citation_and_names_it(self):
        self.write_chapter("ch3-test.md", "如图 3-7 所示，这一幅并不存在。\n")
        code, out = _fixture.run_inproc(self.root, "figures.py", "--strict")
        self.assertEqual(code, 1, out)
        self.assertIn("dangling citations", out)
        self.assertIn("3-7", out)

    def test_a_book_with_every_figure_cited_passes_strict(self):
        for name, figure in (("ch1-test.md", "1-1"), ("ch2-test.md", "2-1")):
            path = os.path.join(self.root, "data", "manuscript", name)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"\n如图 {figure} 所示。\n")
        self.write_chapter("ch3-test.md", "**图 3-1: 结构**\n\n如图 3-1 所示。\n")
        code, out = _fixture.run_inproc(self.root, "figures.py", "--strict")
        self.assertEqual(code, 0, out)
        self.assertIn("Files with uncited figures: 0", out)


if __name__ == "__main__":
    unittest.main()
