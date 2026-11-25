"""The EPUB comparison reads its numbers out of the container, and judging is separate."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

_epub_diff = __import__("audit.epub_diff", fromlist=["check", "compare", "measure"])
measure = _epub_diff.measure
compare = _epub_diff.compare
check = _epub_diff.check

CSS = 'body { font-family: "Source Han Serif", serif; font-size: 1em; line-height: 1.55; }'


def build(directory: str, name: str, chapters: int, css: str = CSS) -> str:
    """A minimal EPUB-shaped zip: CSS plus one XHTML file per chapter."""
    path = os.path.join(directory, name)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("EPUB/styles/stylesheet1.css", css)
        for index in range(1, chapters + 1):
            archive.writestr(
                f"EPUB/text/ch{index:03d}.xhtml", f"<html><body><p>{'字' * 10}</p></body></html>"
            )
    return path


class MeasureTest(unittest.TestCase):
    def test_chapters_and_characters_are_counted_from_the_container(self):
        with tempfile.TemporaryDirectory() as directory:
            stats = measure(build(directory, "b.epub", 3))
        self.assertEqual(stats["chapters"], 3)
        self.assertEqual(stats["chars"], 30)

    def test_css_rules_are_surfaced_for_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            stats = measure(build(directory, "b.epub", 1))
        self.assertEqual(stats["sizes"], ["1em"])
        self.assertEqual(stats["leads"], ["1.55"])
        self.assertEqual(stats["fonts"], ['"Source Han Serif", serif'])


class CompareTest(unittest.TestCase):
    def test_identical_builds_report_no_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            left = build(directory, "a.epub", 2)
            right = build(directory, "b.epub", 2)
            self.assertEqual(compare(left, right), 0)

    def test_a_changed_font_size_is_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            left = build(directory, "a.epub", 1)
            right = build(directory, "b.epub", 1, css="body { font-size: 1.1em; }")
            self.assertEqual(compare(left, right), 1)


class CheckTest(unittest.TestCase):
    def test_cover_plus_one_file_per_heading_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            epub = build(directory, "b.epub", 3)
            merged = os.path.join(directory, "merged.md")
            with open(merged, "w", encoding="utf-8") as handle:
                handle.write("# one\n\n# two\n")
            self.assertEqual(check(epub, merged), 0)

    def test_a_missing_chapter_file_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            epub = build(directory, "b.epub", 2)
            merged = os.path.join(directory, "merged.md")
            with open(merged, "w", encoding="utf-8") as handle:
                handle.write("# one\n\n# two\n\n# three\n")
            self.assertEqual(check(epub, merged), 1)

    def test_an_unreadable_merged_file_fails_without_raising(self):
        with tempfile.TemporaryDirectory() as directory:
            epub = build(directory, "b.epub", 1)
            self.assertEqual(check(epub, os.path.join(directory, "missing.md")), 1)

    def test_bitmap_figures_are_not_compared_for_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            epub = build_with(directory, "b.epub", chapters=2, bitmaps=1)
            merged = os.path.join(directory, "merged.md")
            with open(merged, "w", encoding="utf-8") as handle:
                handle.write("# one\n")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = check(epub, merged)
        self.assertEqual(code, 0, buffer.getvalue())
        self.assertNotIn("figures are text", buffer.getvalue())

    def test_an_invocation_with_nothing_to_do_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as caught:
            _epub_diff.main([])
        self.assertEqual(caught.exception.code, 2)

    def test_the_script_entrypoint_reports_the_usage_error(self):
        code, out = _fixture.run_inproc(BOOK_ROOT, "epub_diff.py")
        self.assertEqual(code, 2, out[-300:])

    def test_help_exits_zero_through_the_script_guard(self):
        done = _fixture.run(BOOK_ROOT, "epub_diff.py", "--help")
        self.assertEqual(done.returncode, 0, done.stderr[-300:])
        self.assertIn("usage: epub_diff.py", done.stdout)
        self.assertIn("--check", done.stdout)


def build_with(
    directory: str, name: str, css: str = CSS, chapters: int = 1, bitmaps: int = 0
) -> str:
    """An EPUB-shaped zip with optional bitmaps and a chosen stylesheet."""
    path = os.path.join(directory, name)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("EPUB/styles/stylesheet1.css", css)
        for index in range(1, chapters + 1):
            archive.writestr(
                f"EPUB/text/ch{index:03d}.xhtml", f"<html><body><p>{'字' * 10}</p></body></html>"
            )
        for index in range(bitmaps):
            archive.writestr(f"EPUB/images/fig{index}.png", b"\x89PNG")
    return path


class MeasureBranchesTest(unittest.TestCase):
    def test_bitmaps_are_counted_and_text_figures_are_not(self):
        with tempfile.TemporaryDirectory() as directory:
            with_images = measure(build_with(directory, "a.epub", bitmaps=2))
            without = measure(build_with(directory, "b.epub"))
        self.assertEqual(with_images["bitmaps"], 2)
        self.assertEqual(without["bitmaps"], 0)

    def test_several_font_stacks_are_deduplicated(self):
        css = (
            'body { font-family: "A", serif; }\n'
            'code { font-family: "B", monospace; }\n'
            'pre { font-family: "A", serif; }\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            stats = measure(build_with(directory, "a.epub", css=css))
        self.assertEqual(stats["fonts"], ['"A", serif', '"B", monospace'])

    def test_a_stylesheet_without_rules_yields_empty_lists(self):
        with tempfile.TemporaryDirectory() as directory:
            stats = measure(build_with(directory, "a.epub", css="/* empty */"))
        self.assertEqual((stats["fonts"], stats["sizes"], stats["leads"]), ([], [], []))


class LeadAndDeltaTest(unittest.TestCase):
    def test_the_leading_family_of_each_stack_is_extracted(self):
        self.assertEqual(_epub_diff._leads(['"A B", serif', "'C', sans-serif"]), ["A B", "C"])

    def test_a_new_axis_from_nothing_is_marked_new(self):
        self.assertEqual(_epub_diff._delta(5, 0), "new")
        self.assertEqual(_epub_diff._delta(0, 0), "0.0%")

    def test_a_growth_is_a_percentage(self):
        self.assertEqual(_epub_diff._delta(150, 100), "+50.0%")


class CompareBranchesTest(unittest.TestCase):
    def test_a_stack_that_only_gains_fallbacks_is_not_drift(self):
        narrow = 'body { font-family: "A", serif; }'
        wide = 'body { font-family: "A", serif, "B"; }'
        with tempfile.TemporaryDirectory() as directory:
            left = build_with(directory, "a.epub", css=narrow)
            right = build_with(directory, "b.epub", css=wide)
            self.assertEqual(compare(left, right), 0)

    def test_a_changed_leading_family_is_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            left = build_with(directory, "a.epub")
            right = build_with(directory, "b.epub", css='body { font-family: "Other", serif; }')
            self.assertEqual(compare(left, right), 1)

    def test_a_changed_line_height_is_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            left = build_with(directory, "a.epub")
            right = build_with(directory, "b.epub", css="body { line-height: 1.8; }")
            self.assertEqual(compare(left, right), 1)


class CheckBranchesTest(unittest.TestCase):
    def test_a_chapter_files_message_names_the_expected_count(self):
        import io
        from contextlib import redirect_stdout

        with tempfile.TemporaryDirectory() as directory:
            epub = build_with(directory, "a.epub", chapters=1)
            merged = os.path.join(directory, "merged.md")
            with open(merged, "w", encoding="utf-8") as handle:
                handle.write("# one\n")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = check(epub, merged)
        self.assertEqual(code, 1)
        self.assertIn("expected 2", buffer.getvalue())


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.left = build_with(self.tmp.name, "a.epub", chapters=2)
        self.right = build_with(self.tmp.name, "b.epub", chapters=2)
        self.merged = os.path.join(self.tmp.name, "merged.md")
        with open(self.merged, "w", encoding="utf-8") as handle:
            handle.write("# one\n")

    def run_cli(self, *argv):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = _epub_diff.main(list(argv))
        return code, buffer.getvalue()

    def test_compare_prints_a_table(self):
        code, out = self.run_cli("--compare", self.left, self.right)
        self.assertEqual(code, 0)
        self.assertIn("chapter files", out)

    def test_compare_json_prints_both_measurements(self):
        import json

        code, out = self.run_cli("--compare", self.left, self.right, "--json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["built"]["chapters"], 2)

    def test_check_reports_the_counts(self):
        code, out = self.run_cli("--check", self.left, "--merged", self.merged)
        self.assertEqual(code, 0)
        self.assertIn("OK", out)

    def test_check_json_prints_the_measurement(self):
        import json

        code, out = self.run_cli("--check", self.left, "--merged", self.merged, "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["chapters"], 2)

    def test_check_without_merged_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as raised:
            self.run_cli("--check", self.left)
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
