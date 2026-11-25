#!/usr/bin/env python3
"""Tests for the PDF verification helpers, using synthetic PDFs."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

TAGS = ("layer:infra", "tier:fast")  # fake chromium engine: no browser

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


def make_pdf(
    path: str,
    pages: int = 2,
    titles: list[tuple[str, int]] | None = None,
    size: tuple[float, float] = (595, 842),
    rotate: int = 0,
    annots: list[dict] | None = None,
) -> str:
    writer = PdfWriter()
    for _index in range(pages):
        page = writer.add_blank_page(width=size[0], height=size[1])
        page[NameObject("/Rotate")] = NumberObject(rotate)
    for title, page_number in titles or []:
        writer.add_outline_item(title=title, page_number=page_number)
    for entry in annots or []:
        page = writer.pages[entry["page"]]
        rect = ArrayObject(
            [
                NumberObject(entry["rect"][0]),
                NumberObject(entry["rect"][1]),
                NumberObject(entry["rect"][2]),
                NumberObject(entry["rect"][3]),
            ]
        )
        dest = ArrayObject([page.indirect_reference, NameObject("/Fit")])
        annot = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Link"),
                NameObject("/Rect"): rect,
                NameObject("/NM"): TextStringObject(entry["name"]),
                NameObject("/Dest"): dest,
            }
        )
        page[NameObject("/Annots")] = ArrayObject(
            list(page.get("/Annots") or []) + [writer._add_object(annot)]
        )
    with open(path, "wb") as fh:
        writer.write(fh)
    return path


HTML_TWO_HEADINGS = (
    '<html><body><nav id="toc-page-nav">'
    '<a href="#a">第一章</a><a href="#b">第二章</a></nav>'
    '<h2 id="a">第一章</h2><p>x</p><h2 id="b">第二章</h2></body></html>'
)


class PdfVerificationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.module = _fixture.load_module(self.root, "verify_pdf")
        self.pdf = os.path.join(self.tmp.name, "book.pdf")
        self.html = os.path.join(self.tmp.name, "book.html")
        with open(self.html, "w", encoding="utf-8") as fh:
            fh.write(HTML_TWO_HEADINGS)

    def check(self, report, name: str) -> tuple[bool, str]:
        for check_name, ok, detail in report.checks:
            if check_name == name:
                return ok, detail
        self.fail(f"check {name} missing: {[c[0] for c in report.checks]}")

    def test_happy_path_passes_every_check(self):
        make_pdf(
            self.pdf,
            titles=[("第一章", 0), ("第二章", 1)],
            annots=[
                {"page": 0, "rect": (10, 10, 100, 20), "name": "toc-link-0"},
                {"page": 1, "rect": (10, 30, 100, 40), "name": "toc-link-1"},
            ],
        )
        report = self.module.verify(self.pdf, self.html)
        self.assertTrue(report.to_dict()["ok"], report.to_dict())

    def test_missing_html_reports_source_html(self):
        make_pdf(self.pdf)
        report = self.module.verify(self.pdf, os.path.join(self.tmp.name, "no.html"))
        self.assertFalse(self.check(report, "SOURCE_HTML")[0])

    def test_outline_mismatch_is_reported(self):
        make_pdf(self.pdf, titles=[("别的标题", 0)])
        report = self.module.verify(self.pdf, self.html)
        self.assertFalse(self.check(report, "OUTLINE")[0])

    def test_non_a4_page_fails_page_size(self):
        make_pdf(self.pdf, size=(612, 792), titles=[("第一章", 0), ("第二章", 1)])
        report = self.module.verify(self.pdf, self.html)
        self.assertFalse(self.check(report, "PAGE_SIZE")[0])

    def test_rotated_page_fails_rotation(self):
        make_pdf(self.pdf, rotate=90, titles=[("第一章", 0), ("第二章", 1)])
        report = self.module.verify(self.pdf, self.html)
        self.assertFalse(self.check(report, "ROTATION")[0])

    def test_missing_toc_links_when_required(self):
        make_pdf(self.pdf, titles=[("第一章", 0), ("第二章", 1)])
        report = self.module.verify(self.pdf, self.html, require_toc_links=True)
        ok, detail = self.check(report, "TOC_LINKS")
        self.assertFalse(ok)
        self.assertIn("link annotations", detail)

    def test_toc_links_without_enhancement_are_allowed(self):
        make_pdf(self.pdf, titles=[("第一章", 0), ("第二章", 1)])
        report = self.module.verify(self.pdf, self.html)
        self.assertTrue(self.check(report, "TOC_LINKS")[0])

    def test_annotation_out_of_bounds_is_reported(self):
        make_pdf(
            self.pdf,
            titles=[("第一章", 0), ("第二章", 1)],
            annots=[
                {"page": 0, "rect": (900, 10, 950, 20), "name": "toc-link-0"},
                {"page": 1, "rect": (10, 30, 100, 40), "name": "toc-link-1"},
            ],
        )
        report = self.module.verify(self.pdf, self.html)
        ok, detail = self.check(report, "TOC_LINKS")
        self.assertFalse(ok)
        self.assertIn("bounds", detail)

    def test_unembedded_font_is_reported(self):
        writer = PdfWriter()
        page = writer.add_blank_page(width=595, height=842)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        resources = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        page[NameObject("/Resources")] = resources
        with open(self.pdf, "wb") as fh:
            writer.write(fh)
        reader = PdfReader(self.pdf)
        self.assertEqual(self.module.non_embedded_fonts(reader), ["/Helvetica"])

    def test_html_headings_parses_levels_and_strips_tags(self):
        html = '<h1 id="a">Title <em>x</em></h1><h4 id="b">Deep</h4>'
        self.assertEqual(self.module.html_headings(html), [(1, "Title x"), (4, "Deep")])

    def test_outline_entries_flatten_nested_items(self):
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        writer.add_blank_page(width=595, height=842)
        parent = writer.add_outline_item(title="父", page_number=0)
        writer.add_outline_item(title="子", page_number=1, parent=parent)
        with open(self.pdf, "wb") as fh:
            writer.write(fh)
        entries = self.module.outline_entries(PdfReader(self.pdf))
        self.assertEqual([(t, d) for t, _p, d in entries], [("父", 0), ("子", 1)])

    def test_toc_link_annotations_are_sorted_by_index(self):
        make_pdf(
            self.pdf,
            titles=[("第一章", 0)],
            annots=[
                {"page": 0, "rect": (10, 30, 100, 40), "name": "toc-link-1"},
                {"page": 0, "rect": (10, 10, 100, 20), "name": "toc-link-0"},
            ],
        )
        annots = self.module.toc_link_annotations(PdfReader(self.pdf))
        self.assertEqual([index for index, _page, _annot in annots], [0, 1])

    def test_main_json_reports_failure_for_missing_pdf(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.module.main(["--pdf", self.pdf, "--html", self.html, "--json"])
        self.assertEqual(code, 1)
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["ok"])

    def test_main_prints_human_summary(self):
        make_pdf(self.pdf, titles=[("第一章", 0), ("第二章", 1)])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.module.main(["--pdf", self.pdf, "--html", self.html])
        self.assertEqual(code, 0)
        self.assertIn("OUTLINE", buffer.getvalue())


class _FakePage:
    def __init__(self, links):
        self._links = links

    def goto(self, url: str, **kwargs) -> None:
        return None

    def wait_for_timeout(self, ms: int) -> None:
        return None

    def evaluate(self, script: str):
        return self._links


class _FakeBrowser:
    def __init__(self, page):
        self._page = page

    def new_page(self, **kwargs):
        return self._page

    def close(self) -> None:
        return None


class _FakeChromium:
    def __init__(self, page):
        self._page = page

    def launch(self, **kwargs):
        return _FakeBrowser(self._page)


class _FakePlaywright:
    def __init__(self, page):
        self.chromium = _FakeChromium(page)


def _fake_engine(links):
    from contextlib import contextmanager

    @contextmanager
    def engine():
        yield _FakePlaywright(_FakePage(links))

    return engine


class TocLinkInjectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.module = _fixture.load_module(self.root, "pdf_toc_links")
        self.pdf = os.path.join(self.tmp.name, "book.pdf")
        self.html = os.path.join(self.tmp.name, "book.html")
        with open(self.html, "w", encoding="utf-8") as fh:
            fh.write(HTML_TWO_HEADINGS)

    def test_collect_outline_returns_titles_and_pages(self):
        make_pdf(self.pdf, titles=[("第一章", 0), ("第二章", 1)])
        reader = PdfReader(self.pdf)
        self.assertEqual(self.module.collect_outline(reader), [("第一章", 0), ("第二章", 1)])

    def test_an_outline_entry_without_a_title_is_skipped(self):
        make_pdf(self.pdf, titles=[("第一章", 0), ("  ", 1), ("第二章", 1)])
        reader = PdfReader(self.pdf)
        self.assertEqual(self.module.collect_outline(reader), [("第一章", 0), ("第二章", 1)])

    def test_a_pdf_that_cannot_be_read_is_reported_as_a_tool_error(self):
        with open(self.pdf, "w", encoding="utf-8") as fh:
            fh.write("not a pdf")
        with self.assertRaises(SystemExit) as caught:
            self.module.add_links(self.pdf, self.html, toc_links=[])
        self.assertIn("cannot read", str(caught.exception))
        self.assertEqual(getattr(caught.exception, "exit_code", None), 1)

    def test_an_empty_manifest_still_produces_a_pdf(self):
        make_pdf(self.pdf)
        self.module.add_links(self.pdf, self.html, toc_links=[])
        reader = PdfReader(self.pdf)
        self.assertEqual(len(reader.pages), 2)
        self.assertFalse(any(page.get("/Annots") for page in reader.pages))
        self.assertFalse(os.path.exists(self.pdf + ".tmp"))

    def test_the_toc_is_read_from_the_html_when_none_is_passed(self):
        make_pdf(self.pdf, titles=[("第一章", 0), ("第二章", 1)])
        links = [
            {
                "index": 0,
                "text": "第一章",
                "href": "#a",
                "rect": {"x": 20, "y": 30, "w": 120, "h": 14},
            },
            {
                "index": 1,
                "text": "第二章",
                "href": "#b",
                "rect": {"x": 20, "y": 60, "w": 120, "h": 14},
            },
        ]
        original = self.module.sync_playwright
        self.module.__dict__["sync_playwright"] = _fake_engine(links)
        try:
            self.module.add_links(self.pdf, self.html)
        finally:
            self.module.__dict__["sync_playwright"] = original
        annots = [
            annot for page in PdfReader(self.pdf).pages for annot in (page.get("/Annots") or [])
        ]
        self.assertEqual(len(annots), 2)

    def test_get_toc_links_reads_printed_toc(self):
        links = [
            {
                "index": 0,
                "text": "第一章",
                "href": "#a",
                "rect": {"x": 10, "y": 10, "w": 90, "h": 12},
            },
            {
                "index": 1,
                "text": "第二章",
                "href": "#b",
                "rect": {"x": 10, "y": 40, "w": 90, "h": 12},
            },
        ]
        engine = _fake_engine(links)
        original = self.module.sync_playwright
        self.module.__dict__["sync_playwright"] = engine
        try:
            found = self.module.get_toc_links(self.html)
        finally:
            self.module.__dict__["sync_playwright"] = original
        self.assertEqual([item["text"] for item in found], ["第一章", "第二章"])
        self.assertEqual([item["text"] for item in links], ["第一章", "第二章"])

    def toc_links(self) -> list[dict]:
        return [
            {
                "index": 0,
                "text": "第一章",
                "href": "#a",
                "rect": {"x": 20, "y": 30, "w": 120, "h": 14},
            },
            {
                "index": 1,
                "text": "第二章",
                "href": "#b",
                "rect": {"x": 20, "y": 60, "w": 120, "h": 14},
            },
        ]

    def test_add_links_writes_annotations(self):
        make_pdf(self.pdf, titles=[("第一章", 0), ("第二章", 1)])
        self.module.add_links(self.pdf, self.html, toc_links=self.toc_links())
        annots = [
            annot for page in PdfReader(self.pdf).pages for annot in (page.get("/Annots") or [])
        ]
        self.assertEqual(len(annots), 2)

    def test_add_links_warns_when_titles_differ(self):
        make_pdf(self.pdf, titles=[("另一个标题", 0)])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.module.add_links(self.pdf, self.html, toc_links=self.toc_links()[:1])
        self.assertIn("Note:", buffer.getvalue())

    def test_add_links_rejects_more_toc_entries_than_outline(self):
        make_pdf(self.pdf, titles=[("第一章", 0)])
        with self.assertRaises(RuntimeError):
            self.module.add_links(self.pdf, self.html, toc_links=self.toc_links())

    def test_add_links_clamps_links_at_the_page_edge(self):
        make_pdf(self.pdf, titles=[("第一章", 0)])
        edge = [
            {
                "index": 0,
                "text": "第一章",
                "href": "#a",
                "rect": {"x": 780, "y": 1060, "w": 40, "h": 20},
            }
        ]
        self.module.add_links(self.pdf, self.html, toc_links=edge)
        self.assertTrue(os.path.exists(self.pdf))

    def test_add_links_rejects_an_empty_rectangle(self):
        make_pdf(self.pdf, titles=[("第一章", 0)])
        degenerate = [
            {"index": 0, "text": "第一章", "href": "#a", "rect": {"x": 10, "y": 10, "w": 0, "h": 0}}
        ]
        with self.assertRaises(RuntimeError):
            self.module.add_links(self.pdf, self.html, toc_links=degenerate)

    def test_add_links_requires_html(self):
        make_pdf(self.pdf, titles=[("第一章", 0)])
        with self.assertRaises(SystemExit):
            self.module.add_links(self.pdf, os.path.join(self.tmp.name, "none.html"))

    def test_add_links_requires_pdf(self):
        with self.assertRaises(SystemExit):
            self.module.add_links(os.path.join(self.tmp.name, "none.pdf"), self.html)


if __name__ == "__main__":
    unittest.main()
