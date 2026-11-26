"""The PDF invariants judge a build without a reference edition."""

from __future__ import annotations

import io
import os
import runpy
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()

_inv = __import__("audit.pdf_invariants", fromlist=["check", "main"])
check = _inv.check
main = _inv.main


class CheckTest(unittest.TestCase):
    def test_a_missing_pdf_is_refused(self):
        self.assertEqual(main([os.path.join(tempfile.gettempdir(), "nope.pdf")]), 2)

    def test_findings_are_returned_as_data(self):
        from pypdf import PdfWriter

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "one.pdf")
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            with open(path, "wb") as handle:
                writer.write(handle)
            merged = os.path.join(directory, "merged.md")
            with open(merged, "w", encoding="utf-8") as handle:
                handle.write("# 一\n\n## 二\n")
            report = check(path, merged)
        self.assertEqual(report["pages"], 1)
        self.assertEqual(report["outline"], 0)
        # the comparison counts headings down to the depth the outline uses, and an
        # empty outline is one level, so only the level-one heading is counted
        self.assertEqual(report["outline_depth"], 1)
        self.assertEqual(report["headings"], 1)
        self.assertTrue(any("大纲" in p for p in report["problems"]))

    def test_without_a_merged_file_the_outline_is_not_judged(self):
        from pypdf import PdfWriter

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "one.pdf")
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            with open(path, "wb") as handle:
                writer.write(handle)
            report = check(path, None)
        self.assertIsNone(report["headings"])
        self.assertFalse(any("大纲" in p for p in report["problems"]))


def fake_page(width: float = 595, height: float = 842, positions=(), fail: str = "", fonts=None):
    """A page whose text layer answers with crafted coordinates."""
    page = types.SimpleNamespace()
    page.mediabox = types.SimpleNamespace(width=width, height=height)

    def get(key):
        if key == "/Resources":
            return {"/Font": fonts or {}}
        return None

    def extract_text(visitor_text=None):
        if fail:
            raise RuntimeError(fail)
        for text, x, y in positions:
            if visitor_text is not None:
                visitor_text(text, [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, x, y], {}, 12)
        return ""

    page.get = get
    page.extract_text = extract_text
    return page


def fake_reader(pages, outline=()):
    return types.SimpleNamespace(pages=list(pages), outline=list(outline))


class OutlineShapeTest(unittest.TestCase):
    def test_nested_entries_count_and_report_their_depth(self):
        reader = fake_reader([], outline=["a", ["b", ["c"]]])
        self.assertEqual(_inv._outline_shape(reader), (3, 3))

    def test_an_empty_outline_is_one_level(self):
        self.assertEqual(_inv._outline_shape(fake_reader([]))[1], 1)

    def test_a_broken_outline_is_a_finding_not_a_crash(self):
        class Broken:
            pages: list = []

            @property
            def outline(self):
                raise RuntimeError("broken")

        self.assertEqual(_inv._outline_shape(Broken()), (0, 1))


class Type3CountTest(unittest.TestCase):
    def test_a_type3_font_is_counted_once_across_pages(self):
        font = {"/Subtype": "/Type3", "/BaseFont": "/F1"}
        reader = fake_reader([fake_page(fonts={"/F1": font}), fake_page(fonts={"/F1": font})])
        self.assertEqual(_inv._type3_count(reader), 1)

    def test_an_embedded_type1_font_is_not_counted(self):
        reader = fake_reader([fake_page(fonts={"/F1": {"/Subtype": "/Type1"}})])
        self.assertEqual(_inv._type3_count(reader), 0)

    def test_a_page_without_resources_contributes_nothing(self):
        page = types.SimpleNamespace(mediabox=None, get=lambda key: None)
        self.assertEqual(_inv._type3_count(fake_reader([page])), 0)


class OutsideColumnTest(unittest.TestCase):
    def test_text_inside_the_page_is_clean(self):
        page = fake_page(positions=[("ok", 100, 100)])
        self.assertEqual(_inv._outside_column(fake_reader([page])), ([], []))

    def test_text_beyond_the_edge_is_reported_with_its_page(self):
        page = fake_page(positions=[("far", 900, 100)])
        offenders, unreadable = _inv._outside_column(fake_reader([page]))
        self.assertEqual(unreadable, [])
        self.assertEqual(offenders, ["p1: x=900 y=100"])

    def test_the_tolerance_covers_rounding_not_a_column(self):
        page = fake_page(positions=[("edge", -1.0, 100)])
        self.assertEqual(_inv._outside_column(fake_reader([page])), ([], []))

    def test_negative_coordinates_are_reported(self):
        page = fake_page(positions=[("left", -30, 100)])
        offenders, _unreadable = _inv._outside_column(fake_reader([page]))
        self.assertEqual(len(offenders), 1)

    def test_a_page_whose_text_cannot_be_read_is_listed(self):
        page = fake_page(fail="broken ToUnicode")
        offenders, unreadable = _inv._outside_column(fake_reader([page]))
        self.assertEqual(offenders, [])
        self.assertEqual(unreadable, ["p1: broken ToUnicode"])

    def test_blank_text_is_ignored(self):
        page = fake_page(positions=[("   ", 900, 900)])
        self.assertEqual(_inv._outside_column(fake_reader([page])), ([], []))


class CheckBranchesTest(unittest.TestCase):
    """`check()` is the composition: every problem line has its own condition."""

    def setUp(self):
        from pypdf import PdfWriter

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = os.path.join(self.tmp.name, "book.pdf")
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with open(self.pdf, "wb") as handle:
            writer.write(handle)

    def test_without_a_merged_file_the_headings_are_not_judged(self):
        report = _inv.check(self.pdf, None)
        self.assertIsNone(report["headings"])

    def test_too_many_type3_fonts_is_a_problem(self):
        with mock.patch.object(_inv, "_type3_count", return_value=_inv.MAX_TYPE3 + 1):
            report = _inv.check(self.pdf, None)
        self.assertTrue(any("Type3" in problem for problem in report["problems"]))

    def test_text_outside_the_page_is_a_problem(self):
        with mock.patch.object(_inv, "_outside_column", return_value=(["p1: x=900 y=100"], [])):
            report = _inv.check(self.pdf, None)
        self.assertTrue(any("超出页面边界" in problem for problem in report["problems"]))

    def test_an_unreadable_page_is_a_problem(self):
        with mock.patch.object(_inv, "_outside_column", return_value=([], ["p1: boom"])):
            report = _inv.check(self.pdf, None)
        self.assertTrue(any("无法读取" in problem for problem in report["problems"]))

    def test_a_heading_gap_is_a_problem(self):
        merged = os.path.join(self.tmp.name, "merged.md")
        with open(merged, "w", encoding="utf-8") as handle:
            handle.write("# 一\n\n## 二\n")
        with (
            mock.patch.object(_inv.frontmatter, "split", return_value=([], ["# 一", "## 二"])),
            mock.patch.object(_inv.frontmatter, "count_headings", return_value=99),
        ):
            report = _inv.check(self.pdf, merged)
        self.assertTrue(any("大纲" in problem for problem in report["problems"]))

    def test_a_missing_merged_file_is_left_to_the_outline_only(self):
        report = _inv.check(self.pdf, os.path.join(self.tmp.name, "absent.md"))
        self.assertIsNone(report["headings"])
        self.assertEqual(report["problems"], [])


class CliTest(unittest.TestCase):
    def setUp(self):
        from pypdf import PdfWriter

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = os.path.join(self.tmp.name, "book.pdf")
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with open(self.pdf, "wb") as handle:
            writer.write(handle)

    def run_cli(self, *argv):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = _inv.main(list(argv))
        return code, buffer.getvalue()

    def test_a_clean_pdf_passes_and_prints_a_summary(self):
        code, out = self.run_cli(self.pdf)
        self.assertEqual(code, 0)
        self.assertIn("页", out)

    def test_json_prints_the_report(self):
        import json

        code, out = self.run_cli(self.pdf, "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["pages"], 1)
        self.assertEqual(payload["problems"], [])

    def test_a_problem_makes_the_exit_code_non_zero(self):
        with mock.patch.object(_inv, "_outside_column", return_value=(["p1: x=900 y=100"], [])):
            code, out = self.run_cli(self.pdf)
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)


class ScriptEntryPointTest(unittest.TestCase):
    """The file also runs as a script, from outside the tool root."""

    def test_the_script_puts_the_tool_root_on_the_path_and_exits(self):
        tools = os.path.abspath(_fixture.TOOLS_DIR)
        script = os.path.join(tools, "audit", "pdf_invariants.py")
        missing = os.path.join(tempfile.gettempdir(), "no-such-edition.pdf")
        saved_path = list(sys.path)
        saved_argv = sys.argv[:]
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        self.addCleanup(setattr, sys, "argv", saved_argv)
        sys.argv = ["pdf_invariants.py", missing]
        sys.path[:] = [entry for entry in sys.path if os.path.abspath(entry or ".") != tools]
        self.assertNotIn(tools, [os.path.abspath(entry or ".") for entry in sys.path])
        with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
            runpy.run_path(script, run_name="__main__")
        self.assertEqual(raised.exception.code, 2)
        self.assertIn(tools, [os.path.abspath(entry or ".") for entry in sys.path])


if __name__ == "__main__":
    unittest.main()
