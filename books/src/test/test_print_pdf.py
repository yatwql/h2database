#!/usr/bin/env python3
"""The print edition is the delivery renderer plus one print-only stylesheet.

What this pins down: the print edition goes through the split renderer (one page box,
one column, no scale of its own), the profile is injected into a staging file and
removed afterwards, and nothing in the pipeline decides a margin or a size on its own.
"""

from __future__ import annotations

import importlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from unittest import mock

import _fixture
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

_MISSING = object()

TAGS = ("layer:infra", "tier:fast")  # fake chromium engine: no browser

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


def write_text_pdf(path: str, pages: list[list[str]]) -> None:
    """A4 pages carrying the given ASCII text lines."""
    writer = PdfWriter()
    font_ref = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    for lines in pages:
        page = writer.add_blank_page(width=595, height=842)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
        )
        stream = DecodedStreamObject()
        body = ["BT", "/F1 12 Tf", "14 TL", "40 800 Td"]
        for line in lines:
            escaped = line.replace("(", r"\(").replace(")", r"\)")
            body.append(f"({escaped}) Tj T*")
        body.append("ET")
        stream.set_data("\n".join(body).encode("utf-8"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    with open(path, "wb") as handle:
        writer.write(handle)


class SplitPage:
    """A browser page that answers the two scripts the splitter runs."""

    def __init__(self, target: str, parts: list[dict], headings: list[dict]):
        self.target = target
        self.parts = parts
        self.headings = headings
        self.viewport: dict = {}
        self.pdf_kwargs: dict = {}
        self.urls: list[str] = []

    def goto(self, url: str, **_kwargs) -> None:
        self.urls.append(url)

    def wait_for_timeout(self, _ms: int) -> None:
        return None

    def set_viewport_size(self, size: dict) -> None:
        self.viewport = size

    def evaluate(self, script: str, _payload=None):
        if "holder" in script:  # the splitter's chapter split
            return self.parts
        if "__CONTENT__" in script:  # the marker injection
            return self.headings
        return None

    def pdf(self, path: str | None = None, **kwargs) -> None:
        self.pdf_kwargs = kwargs
        write_text_pdf(path or self.target, [["__CONTENT__", "__hdr_0__Chapter One"]])


class FakeBrowser:
    def __init__(self, page):
        self._page = page
        self.closed = False

    def new_page(self):
        return self._page

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, page):
        self._page = page

    def launch(self, **_kwargs):
        return FakeBrowser(self._page)


class FakePlaywright:
    def __init__(self, page):
        self.chromium = FakeChromium(page)


def fake_engine(page):
    @contextmanager
    def engine():
        yield FakePlaywright(page)

    return engine


class PrintEditionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.module = _fixture.load_module(self.root, "print_pdf")
        self.profile = _fixture.load_module(self.root, "print_profile")
        self.layout = _fixture.load_module(self.root, "layout")
        self.html = os.path.join(self.tmp.name, "book.html")
        self.pdf = os.path.join(self.tmp.name, "print.pdf")
        with open(self.html, "w", encoding="utf-8") as handle:
            handle.write(
                '<html><head></head><body><div id="content">'
                '<h1 id="a">Chapter One</h1><p>text</p>'
                '<h1 id="b">Chapter Two</h1></div></body></html>'
            )
        self.parts = [
            {
                "html": '<h1 id="a">Chapter One</h1>',
                "headings": [{"level": 1, "text": "Chapter One"}],
            },
            {
                "html": '<h1 id="b">Chapter Two</h1>',
                "headings": [{"level": 1, "text": "Chapter Two"}],
            },
        ]
        self.headings = [{"index": 0, "id": "a", "level": 1, "text": "Chapter One"}]

    def test_the_profile_is_injected_once_before_the_head_closes(self):
        once = self.profile.inject("<head></head>")
        self.assertIn("print-grade-css", once)
        self.assertIn("@media print", once)
        self.assertEqual(self.profile.inject(once), once)

    def test_a_wider_face_solves_to_a_smaller_body(self):
        """Chars per line come from the set type, so the font decides the scale."""
        # a face whose line holds fewer characters than the reading measure wants is
        # set too large for the column, so the printed body shrinks; a narrower face
        # that already fits is left at the screen size (never enlarged)
        wide = self.profile.solve_print_type(
            {"chars_per_line": 30}, body_px=16, chars_per_line=40, lead_target=1.4
        )
        narrow = self.profile.solve_print_type(
            {"chars_per_line": 55}, body_px=16, chars_per_line=40, lead_target=1.4
        )
        self.assertEqual(wide["scale"], 0.8)  # floored: 30/40 would be 0.75
        self.assertEqual(wide["body_px"], 13)
        mid = self.profile.solve_print_type(
            {"chars_per_line": 34}, body_px=16, chars_per_line=40, lead_target=1.4
        )
        self.assertEqual(mid["scale"], 0.85)
        self.assertEqual(mid["body_px"], 14)
        self.assertEqual(narrow["body_px"], 16)
        self.assertEqual(narrow["scale"], 1.0)
        self.assertEqual(narrow["line_height"], 1.4)

    def test_a_measurement_that_says_nothing_keeps_the_screen_type(self):
        numbers = self.profile.solve_print_type({}, body_px=16, chars_per_line=40, lead_target=1.4)
        self.assertEqual(numbers["body_px"], 16)
        self.assertEqual(numbers["scale"], 1.0)

    def test_the_density_rule_only_applies_to_paper(self):
        numbers = self.profile.solve_print_type(
            {"chars_per_line": 50, "code_px": 9.5}, body_px=16, chars_per_line=40, lead_target=1.4
        )
        block = self.profile.inject("<head></head>", numbers)
        self.assertIn("@media print", block)
        self.assertIn(f"font-size: {numbers['body_px']}px", block)
        self.assertIn(f"line-height: {numbers['line_height']}", block)
        self.assertIn("font-size: 9.5px", block)

    def test_listings_get_their_own_leading(self):
        """A page of listings is set by its column, so its leading is its own knob."""
        numbers = self.profile.solve_print_type(
            {"chars_per_line": 40, "code_px": 9.5},
            body_px=16,
            chars_per_line=40,
            lead_target=1.4,
            code_lead_target=1.1,
        )
        self.assertEqual(numbers["line_height"], 1.4)
        self.assertEqual(numbers["code_line_height"], 1.1)
        block = self.profile.inject("<head></head>", numbers)
        self.assertIn("line-height: 1.4", block)
        self.assertIn("line-height: 1.1", block)

    def test_the_listing_lead_follows_the_prose_lead_when_unconfigured(self):
        numbers = self.profile.solve_print_type(
            {"chars_per_line": 40}, body_px=16, chars_per_line=40, lead_target=1.4
        )
        self.assertEqual(numbers["code_line_height"], 1.4)

    def test_the_profile_does_not_fix_type_in_pixels(self):
        block = self.profile.style_block()
        self.assertNotRegex(block, r"font-size:\s*[\d.]+px")
        self.assertNotRegex(block, r"(padding|margin)[^;]*\d+px")
        self.assertIn("em", block)

    def test_the_accent_comes_from_the_books_display_copy(self):
        # accent() resolves the config at call time, so patch the module it imports
        with mock.patch("lib._config.project", return_value="#123456"):
            self.assertIn("#123456", self.profile.style_block())

    def test_the_reference_measurement_reads_the_delivery_pdf(self):
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with open(self.pdf, "wb") as handle:
            writer.write(handle)
        metrics = self.module.reference_metrics(self.pdf)
        self.assertIn("pages", metrics)
        self.assertEqual(self.module.reference_metrics(os.path.join(self.tmp.name, "nope.pdf")), {})

    def test_adaptation_needs_a_measurement_to_solve_from(self):
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with open(self.pdf, "wb") as handle:
            writer.write(handle)
        # a blank page has no text, so there is nothing to adapt to
        self.assertIsNone(self.module.adaptive_numbers(self.pdf))
        measured = {"chars_per_line": 14, "code_px": 9.0}
        with mock.patch.object(self.module, "reference_metrics", lambda _path=None, m=measured: m):
            numbers = self.module.adaptive_numbers(self.pdf)
        self.assertIsNotNone(numbers)
        self.assertLess(numbers["body_px"], 16)

    def test_the_printed_numbers_come_from_the_configuration(self):
        """The reading measure and both leadings are configuration, not defaults."""
        measured = {"chars_per_line": 18, "code_px": 9.0}
        thresholds = {
            "layout_print_chars_per_line": 36,
            "layout_print_lead_target": 0.4,
            "layout_print_code_lead_target": 0.1,
        }
        with (
            mock.patch.object(self.module, "reference_metrics", lambda _path=None, m=measured: m),
            mock.patch.object(self.module._config, "THRESHOLDS", thresholds),
        ):
            numbers = self.module.adaptive_numbers(self.pdf)
        self.assertEqual(numbers["scale"], 0.8)  # 18/36, floored
        self.assertEqual(numbers["line_height"], 1.4)
        self.assertEqual(numbers["code_line_height"], 1.1)

    def test_the_adaptive_flag_hands_the_solver_to_build(self):
        page = SplitPage(self.pdf, self.parts, self.headings)
        numbers = {"body_px": 13, "line_height": 1.4, "code_px": 9.0, "scale": 0.8}
        out = io.StringIO()
        with (
            mock.patch.object(self.module, "adaptive_numbers", return_value=numbers),
            redirect_stdout(out),
        ):
            code = self.module.main(
                ["--skip-html", "--html", self.html, "--pdf", self.pdf, "--adaptive"],
                engine=fake_engine(page),
            )
        self.assertEqual(code, 0)
        self.assertIn("自适应印刷参数", out.getvalue())

    def test_build_renders_through_the_splitter(self):
        page = SplitPage(self.pdf, self.parts, self.headings)
        with redirect_stdout(io.StringIO()):
            count = self.module.build(self.html, self.pdf, fake_engine(page), linker=None)
        self.assertEqual(count, 3)  # front matter + one page per chapter part
        self.assertEqual(page.viewport, {"width": 794, "height": 1123})
        self.assertTrue(page.pdf_kwargs["prefer_css_page_size"])
        self.assertNotIn("scale", page.pdf_kwargs)  # no per-edition magnification
        self.assertTrue(os.path.exists(self.pdf))

    def test_the_staged_html_carries_the_profile_and_is_removed(self):
        seen: dict[str, str] = {}

        def capture(path: str, _target: str, **_kwargs) -> int:
            with open(path, encoding="utf-8") as handle:
                seen["html"] = handle.read()
            seen["path"] = path
            return 3

        with (
            mock.patch.object(self.module.pdf_split, "render_html", side_effect=capture),
            redirect_stdout(io.StringIO()),
        ):
            count = self.module.build(self.html, self.pdf, linker=None)
        self.assertEqual(count, 3)
        self.assertIn("print-grade-css", seen["html"])
        self.assertFalse(os.path.exists(seen["path"]))

    def test_the_printed_toc_gets_its_link_targets_stamped(self):
        """Chromium's split render leaves TOC links without destinations."""
        seen: dict[str, object] = {}

        def capture(path: str, _target: str, **_kwargs) -> int:
            seen["html"] = path
            return 3

        def linker(**kwargs) -> None:
            seen["pdf"] = str(kwargs["pdf_path"])
            seen["linker_html"] = str(kwargs["html_path"])
            seen["html_existed"] = os.path.exists(kwargs["html_path"])

        with (
            mock.patch.object(self.module.pdf_split, "render_html", side_effect=capture),
            redirect_stdout(io.StringIO()),
        ):
            self.module.build(self.html, self.pdf, linker=linker)
        self.assertEqual(seen["pdf"], self.pdf)
        self.assertEqual(seen["linker_html"], seen["html"])
        self.assertTrue(seen["html_existed"])

    def test_a_missing_browser_engine_only_skips_the_link_step(self):
        """A plain environment renders the PDF; the TOC links are the only casualty.

        The engine probe answers, so the case does not depend on whether an earlier case
        already imported the linker (an import that has succeeded cannot be made to fail).
        """
        page = SplitPage(self.pdf, self.parts, self.headings)
        out = io.StringIO()
        real_find_spec = importlib.util.find_spec

        def find_spec(name, *args, **kwargs):
            if name == "playwright":
                return None
            return real_find_spec(name, *args, **kwargs)

        with (
            mock.patch.object(importlib.util, "find_spec", find_spec),
            redirect_stdout(out),
        ):
            count = self.module.build(self.html, self.pdf, fake_engine(page))
        self.assertEqual(count, 3)
        self.assertIn("playwright 未安装", out.getvalue())

    def test_a_missing_source_is_reported_not_raised(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = self.module._errors.run(
                self.module.main,
                [
                    "--skip-html",
                    "--html",
                    os.path.join(self.tmp.name, "nope.html"),
                    "--pdf",
                    self.pdf,
                ],
            )
        self.assertEqual(code, 1)

    def test_main_returns_zero_on_success(self):
        page = SplitPage(self.pdf, self.parts, self.headings)
        with redirect_stdout(io.StringIO()):
            code = self.module.main(
                ["--skip-html", "--html", self.html, "--pdf", self.pdf], engine=fake_engine(page)
            )
        self.assertEqual(code, 0)

    def test_an_empty_content_area_is_a_loud_failure(self):
        page = SplitPage(self.pdf, [], self.headings)
        work = os.path.join(self.tmp.name, "split-work")
        os.makedirs(work)
        with self.assertRaises(RuntimeError) as caught:
            self.module.pdf_split.render_parts(page, work, {}, self.headings)
        self.assertEqual(str(caught.exception), "no chapters found in #content")
        self.assertEqual(os.listdir(work), [])  # nothing rendered before the raise

    def test_rendering_without_optimising_leaves_the_merge_alone(self):
        page = SplitPage(self.pdf, self.parts, self.headings)
        with (
            mock.patch.object(self.module.pdf_split, "_optimize") as optimise,
            redirect_stdout(io.StringIO()),
        ):
            count = self.module.pdf_split.render(page, self.pdf, {}, self.headings, optimize=False)
        optimise.assert_not_called()
        self.assertEqual(count, 3)
        self.assertTrue(os.path.exists(self.pdf))

    def test_a_failed_html_regeneration_is_reported(self):
        failure = mock.Mock(returncode=1, stdout="", stderr="pandoc missing")
        with (
            mock.patch.object(self.module.subprocess, "run", return_value=failure),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            code = self.module.main(["--html", self.html, "--pdf", self.pdf])
        self.assertEqual(code, 1)

    def test_a_broken_build_is_reported_not_raised(self):
        with (
            mock.patch.object(self.module, "build", side_effect=RuntimeError("boom")),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            code = self.module.main(["--skip-html", "--html", self.html, "--pdf", self.pdf])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
