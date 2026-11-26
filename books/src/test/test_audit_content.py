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
        self.assertEqual(code, 1, out)
        self.assertIn("CHAPTER_NOT_FOUND", out)
        self.assertIn("OK: 3, Errors: 1", out)

    def test_crossrefs_audit_confirms_a_book_whose_references_all_match(self):
        chapters = {
            "ch1-test.md": "# 第1章 测试章节\n\n详见第2章《测试章节》。\n",
            "ch2-test.md": "# 第2章 测试章节\n\n正文一段，详见第1章《测试章节》。\n",
        }
        for name, text in chapters.items():
            path = os.path.join(self.root, "data", "manuscript", name)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        code, out = _fixture.run_inproc(self.root, "crossrefs.py")
        self.assertEqual(code, 0, out)
        self.assertIn("All cross-references match!", out)
        self.assertIn("OK: 2, Errors: 0", out)

    def test_crossrefs_audit_fails_a_chapter_below_the_density_floor(self):
        """A chapter the rest of the book never sends the reader to is a finding."""
        path = os.path.join(self.root, "data", "manuscript", "ch2-test.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text.replace("详见第1章《测试章节》。", "本章不与它章互相引用。"))
        code, out = _fixture.run_inproc(self.root, "crossrefs.py")
        self.assertEqual(code, 1, out)
        self.assertIn("below the configured minimum", out)
        self.assertIn("ch2(0)", out)

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


class CrossrefsDensityTest(unittest.TestCase):
    """The density rule counts chapters, and a title that drifted is an error."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def _append(self, name, text):
        path = os.path.join(self.root, "data", "manuscript", name)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)

    def test_a_reference_whose_title_drifted_is_reported_with_the_actual_title(self):
        self._append("ch1-test.md", "\n详见第2章《一直没改的旧标题》。\n")
        code, out = _fixture.run_inproc(self.root, "crossrefs.py")
        self.assertEqual(code, 1, out)
        self.assertIn("MISMATCHES: 1", out)
        self.assertIn('actual "测试章节"', out)

    def test_a_continuation_file_covering_several_chapters_is_listed_not_counted(self):
        """It cannot be attributed to one chapter, so it is reported, never guessed."""
        self._append("ch1-test.md", "\n## 1.12 附录小节\n\n详见第2章《测试章节》。\n")
        self._append("ch3-test.md", "续写内容，详见第2章《测试章节》。\n")
        book = os.path.join(self.root, "data", "book", "book.toml")
        with open(book, encoding="utf-8") as fh:
            text = fh.read()
        text = text.replace('    "ch2-test.md",\n]', '    "ch2-test.md",\n    "ch3-test.md",\n]', 1)
        text = text.replace("[chapters.coverage]", '[chapters.coverage]\n"ch3-test.md" = [2, 3]', 1)
        with open(book, "w", encoding="utf-8") as fh:
            fh.write(text)
        code, out = _fixture.run_inproc(self.root, "crossrefs.py")
        self.assertIn("declares no chapter and covers several", out)
        self.assertNotIn("ch3 ", out.replace("ch3-test.md", ""))

    def test_a_continuation_file_covering_one_chapter_is_attributed_to_it(self):
        """One chapter is the only case where the answer is not a guess."""
        self._append("ch1-test.md", "\n续写，详见第2章《测试章节》。\n")
        self._append("ch4-test.md", "无关内容，没有 H1，也不在任何章节的覆盖表里。\n")
        self._append("ch5-test.md", "续写，详见第2章《测试章节》。\n")
        book = os.path.join(self.root, "data", "book", "book.toml")
        with open(book, encoding="utf-8") as fh:
            text = fh.read()
        text = text.replace(
            '    "ch2-test.md",\n]',
            '    "ch2-test.md",\n    "ch4-test.md",\n    "ch5-test.md",\n]',
            1,
        )
        text = text.replace("[chapters.coverage]", '[chapters.coverage]\n"ch5-test.md" = [2]', 1)
        with open(book, "w", encoding="utf-8") as fh:
            fh.write(text)
        code, out = _fixture.run_inproc(self.root, "crossrefs.py")
        self.assertEqual(code, 0, out)
        self.assertNotIn("declares no chapter and covers several", out)
        self.assertIn("ch2-test.md, ch5-test.md", out)

    def test_the_audit_can_be_imported_and_driven_by_a_runner(self):
        """The gate is also called in-process, where the module is not `__main__`."""
        module = _fixture.load_module(self.root, "crossrefs")
        self.assertTrue(callable(module.main))


if __name__ == "__main__":
    unittest.main()
