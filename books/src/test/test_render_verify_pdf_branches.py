#!/usr/bin/env python3
"""PDF verification and TOC-link injection, driven by synthetic PDFs.

`verify()` judges a finished PDF against its HTML; `add_links()` writes the
clickable printed-TOC annotations. Both are pure pypdf work once the coordinates
are supplied, so the whole decision chain runs without a browser.
"""

from __future__ import annotations

import importlib
import importlib.util
import io
import os
import pathlib
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:render", "tier:fast")  # needs pypdf only; other deps are skipped

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

HAS_PYPDF = importlib.util.find_spec("pypdf") is not None

HTML = """<!DOCTYPE html><html><body>
<h1 id="a">第1章</h1><h2 id="b">1.1 小节</h2>
<nav id="toc-page-nav">
  <a href="#a">第1章</a>
  <a href="#b">1.1 小节</a>
</nav></body></html>
"""


@unittest.skipUnless(HAS_PYPDF, "pypdf not installed")
class PdfFixtureCase(unittest.TestCase):
    """Synthetic PDFs and the book fixture; no test methods of its own."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.verify_pdf = _fixture.load_module(self.root, "verify_pdf")
        self.pdf = os.path.join(self.tmp.name, "book.pdf")
        self.html = os.path.join(self.tmp.name, "book.html")
        with open(self.html, "w", encoding="utf-8") as fh:
            fh.write(HTML)

    def build(
        self,
        size=(595, 842),
        pages=2,
        outline=True,
        rotate=0,
        non_embedded=False,
        same_size=True,
        with_toc=True,
    ) -> str:
        from pypdf import PdfWriter

        writer = PdfWriter()
        for index in range(pages):
            width, height = size if same_size or index == 0 else (612, 792)
            page = writer.add_blank_page(width=width, height=height)
            if rotate:
                from pypdf.generic import NameObject, NumberObject

                page[NameObject("/Rotate")] = NumberObject(rotate)
            if non_embedded:
                from pypdf.generic import DictionaryObject, NameObject

                font = DictionaryObject()
                font[NameObject("/Type")] = NameObject("/Font")
                font[NameObject("/Subtype")] = NameObject("/Type1")
                font[NameObject("/BaseFont")] = NameObject("/Helvetica")
                page[NameObject("/Resources")] = DictionaryObject(
                    {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
                )
        if outline:
            first = writer.add_outline_item(title="第1章", page_number=0)
            writer.add_outline_item(title="1.1 小节", page_number=0, parent=first)
        with open(self.pdf, "wb") as fh:
            writer.write(fh)
        if not with_toc:
            with open(self.html, "w", encoding="utf-8") as fh:
                fh.write(HTML.replace('<a href="#b">1.1 小节</a>', ""))
        return self.pdf

    def failures(self, report) -> list[str]:
        return [name for name, _detail in report.failures]


@unittest.skipUnless(HAS_PYPDF, "pypdf not installed")
class VerifyPdfTest(PdfFixtureCase):
    def test_a_healthy_pdf_passes_every_check(self):
        self.build()
        report = self.verify_pdf.verify(self.pdf, self.html)
        self.assertEqual(report.failures, [])
        self.assertTrue(report.to_dict()["ok"])

    def test_a_missing_pdf_or_html_is_reported(self):
        report = self.verify_pdf.verify(self.pdf, self.html)
        self.assertIn("EXISTS", self.failures(report))
        with open(self.pdf, "wb") as fh:
            fh.write(b"%PDF-1.4 placeholder")
        report = self.verify_pdf.verify(self.pdf, os.path.join(self.tmp.name, "no.html"))
        self.assertIn("SOURCE_HTML", self.failures(report))

    def test_a_letter_page_fails_the_size_check(self):
        self.build(size=(612, 792))
        self.assertIn("PAGE_SIZE", self.failures(self.verify_pdf.verify(self.pdf, self.html)))

    def test_a_rotated_page_fails(self):
        self.build(rotate=90)
        self.assertIn("ROTATION", self.failures(self.verify_pdf.verify(self.pdf, self.html)))

    def test_a_non_embedded_font_is_named(self):
        self.build(non_embedded=True)
        failures = dict(self.verify_pdf.verify(self.pdf, self.html).failures)
        self.assertIn("FONTS", failures)
        self.assertIn("Helvetica", failures["FONTS"])

    def test_missing_outline_fails(self):
        self.build(outline=False)
        self.assertIn("OUTLINE", self.failures(self.verify_pdf.verify(self.pdf, self.html)))

    def test_the_printed_toc_count_must_match_the_headings(self):
        self.build(with_toc=False)
        self.assertIn("TOC_COUNT", self.failures(self.verify_pdf.verify(self.pdf, self.html)))

    def test_links_are_optional_until_required(self):
        self.build()
        relaxed = self.verify_pdf.verify(self.pdf, self.html, require_toc_links=False)
        self.assertNotIn("TOC_LINKS", self.failures(relaxed))
        strict = self.verify_pdf.verify(self.pdf, self.html, require_toc_links=True)
        self.assertIn("TOC_LINKS", self.failures(strict))

    def first_annotation(self, reader):
        """First annotation object of page 1 (pypdf's array is untyped)."""
        references = reader.pages[0].get("/Annots") or []
        for reference in references:
            return reference.get_object()
        raise AssertionError("the page carries no annotation")

    def test_a_link_annotation_outside_the_page_is_rejected(self):
        from pypdf import PdfReader, PdfWriter
        from pypdf.annotations import Link
        from pypdf.generic import ArrayObject, FloatObject, NameObject, TextStringObject

        self.build()
        writer = PdfWriter()
        writer.append(PdfReader(self.pdf))
        writer.add_annotation(0, Link(rect=(10.0, 10.0, 60.0, 22.0), target_page_index=0))
        with open(self.pdf, "wb") as fh:
            writer.write(fh)
        reader = PdfReader(self.pdf)
        annot = self.first_annotation(reader)
        # the injected links carry an /NM name; the check then judges the rect
        annot[NameObject("/NM")] = TextStringObject("toc-link-0")
        annot[NameObject("/Rect")] = ArrayObject(
            [FloatObject(-10.0), FloatObject(-10.0), FloatObject(5.0), FloatObject(5.0)]
        )
        writer = PdfWriter()
        writer.append(reader)
        with open(self.pdf, "wb") as fh:
            writer.write(fh)
        self.assertIn("TOC_LINKS", self.failures(self.verify_pdf.verify(self.pdf, self.html)))

    def test_annotation_rect_tolerates_missing_or_short_rectangles(self):
        self.assertEqual(self.verify_pdf._annotation_rect(object()), [])
        from pypdf.generic import ArrayObject, FloatObject

        annot = {"/Rect": ArrayObject([FloatObject(1), FloatObject(2)])}
        self.assertEqual(self.verify_pdf._annotation_rect(annot), [1.0, 2.0])

    def test_annotation_target_page_reads_named_destinations(self):
        from pypdf import PdfReader

        self.build()
        reader = PdfReader(self.pdf)
        self.assertIsNone(self.verify_pdf._annotation_target_page(reader, {"/Dest": "nope"}))

    def test_non_embedded_fonts_accepts_type3_glyphs(self):
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import DictionaryObject, NameObject

        self.build()
        writer = PdfWriter()
        writer.append(PdfReader(self.pdf))
        page = writer.pages[0]
        type3 = DictionaryObject()
        type3[NameObject("/Type")] = NameObject("/Font")
        type3[NameObject("/Subtype")] = NameObject("/Type3")
        type3[NameObject("/BaseFont")] = NameObject("/T3")
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F3"): type3})}
        )
        with open(self.pdf, "wb") as fh:
            writer.write(fh)
        self.assertEqual(self.verify_pdf.non_embedded_fonts(PdfReader(self.pdf)), [])

    def test_a_font_entry_without_a_dictionary_is_skipped(self):
        page = types.SimpleNamespace()
        page.get = lambda key: {"/Font": {"/F1": 7}} if key == "/Resources" else None
        reader = types.SimpleNamespace(pages=[page])
        self.assertEqual(self.verify_pdf.non_embedded_fonts(reader), [])


@unittest.skipUnless(HAS_PYPDF, "pypdf not installed")
class TocLinkInjectionTest(PdfFixtureCase):
    def setUp(self):
        super().setUp()
        self.mod = _fixture.load_module(self.root, "pdf_toc_links")
        self.build()

    def link(self, index: int, y: float, *, width: float = 100.0) -> dict:
        return {
            "index": index,
            "text": "第1章",
            "href": "#a",
            "rect": {"x": 100.0, "y": y, "w": width, "h": 12.0},
        }

    def inject(self, links) -> str:
        target = os.path.join(self.tmp.name, "out.pdf")
        self.mod.add_links(
            pdf_path=pathlib.Path(self.pdf),
            html_path=pathlib.Path(self.html),
            tmp_path=pathlib.Path(target),
            toc_links=links,
        )
        return target

    def test_links_land_on_the_outline_pages(self):
        from pypdf import PdfReader

        self.inject([self.link(0, 200.0), self.link(1, 240.0)])
        annots = self.verify_pdf.toc_link_annotations(PdfReader(self.pdf))
        self.assertEqual(len(annots), 2)
        report = self.verify_pdf.verify(self.pdf, self.html)
        self.assertEqual(self.failures(report), [])

    def test_a_missing_pdf_is_refused(self):
        with self.assertRaises(SystemExit):
            self.mod.add_links(
                pdf_path=pathlib.Path(os.path.join(self.tmp.name, "no.pdf")),
                html_path=pathlib.Path(self.html),
                toc_links=[self.link(0, 100.0)],
            )

    def test_a_missing_html_is_refused(self):
        with self.assertRaises(SystemExit):
            self.mod.add_links(
                pdf_path=pathlib.Path(self.pdf),
                html_path=pathlib.Path(os.path.join(self.tmp.name, "no.html")),
                toc_links=[self.link(0, 100.0)],
            )

    def test_more_links_than_outline_entries_is_an_error(self):
        with self.assertRaises(RuntimeError):
            self.inject([self.link(index, 100.0) for index in range(5)])

    def test_an_empty_rectangle_is_an_error(self):
        with self.assertRaises(RuntimeError):
            self.inject([self.link(0, 100.0, width=0.0)])

    def test_a_link_beyond_the_page_range_is_an_error(self):
        with self.assertRaises(RuntimeError):
            self.inject([self.link(0, 5000.0)])

    def test_a_mismatched_first_title_is_only_noted(self):
        from pypdf import PdfReader

        links = [{**self.link(0, 200.0), "text": "别的标题"}, self.link(1, 240.0)]
        self.inject(links)
        self.assertEqual(len(self.verify_pdf.toc_link_annotations(PdfReader(self.pdf))), 2)


class FontEmbeddingTest(unittest.TestCase):
    """One font dictionary decides embedded-or-not; no PDF needed."""

    def setUp(self):
        self.verify = importlib.import_module("render.verify_pdf")

    def test_a_font_with_a_direct_program_is_embedded(self):
        font = {"/Subtype": "/TrueType", "/FontDescriptor": {"/FontFile2": object()}}
        self.assertTrue(self.verify.font_is_embedded(font))

    def test_a_composite_face_keeps_its_program_on_the_descendant(self):
        child = {"/FontDescriptor": {"/FontFile3": object()}}
        self.assertTrue(self.verify.font_is_embedded({"/DescendantFonts": [child]}))

    def test_a_type3_font_counts_as_embedded(self):
        self.assertTrue(self.verify.font_is_embedded({"/Subtype": "/Type3"}))

    def test_a_font_without_any_program_is_not_embedded(self):
        self.assertFalse(
            self.verify.font_is_embedded({"/Subtype": "/TrueType", "/FontDescriptor": {}})
        )

    def test_an_unreadable_dictionary_is_unclassifiable(self):
        class Blind:
            def get(self, *_args):
                raise AttributeError("no dictionary")

        self.assertIsNone(self.verify.font_is_embedded(Blind()))

    def test_the_reader_walk_reports_each_missing_family_once(self):
        font = {"/BaseFont": "/Loose", "/FontDescriptor": {}}
        page = types.SimpleNamespace()
        page.get = lambda key: {"/Font": {"/F1": font}} if key == "/Resources" else None
        reader = types.SimpleNamespace(pages=[page, page])
        self.assertEqual(self.verify.non_embedded_fonts(reader), ["/Loose"])

    def test_a_font_map_that_is_not_a_mapping_is_skipped(self):
        class OddMap:
            def values(self):
                raise AttributeError("not a mapping")

        page = types.SimpleNamespace()
        page.get = lambda key: {"/Font": OddMap()} if key == "/Resources" else None
        self.assertEqual(self.verify.non_embedded_fonts(types.SimpleNamespace(pages=[page])), [])




class VerifyPdfSkipAndDensityTest(PdfFixtureCase):
    """A missing optional reader, an unavailable metric, and the density verdict."""

    def test_a_missing_pypdf_is_reported_and_skips_the_rest(self):
        report = self.verify_pdf.Report()
        with mock.patch.object(self.verify_pdf, "PdfReader", None):
            self.assertIsNone(self.verify_pdf._open_inputs(report, self.pdf, self.html))
        self.assertEqual([name for name, ok, _d in report.checks], ["PYPDF"])
        self.assertFalse(report.checks[0][1])

    def test_a_named_destination_that_is_not_a_list_has_no_target(self):
        reader = mock.Mock(pages=[mock.Mock()])
        self.assertIsNone(self.verify_pdf._annotation_target_page(reader, {"/Dest": "nope"}))

    def test_a_goto_action_must_be_a_goto_and_point_at_a_real_page(self):
        reader = mock.Mock(pages=[mock.Mock(), mock.Mock()])
        skipped = {"/A": {"/S": "/URI"}}
        self.assertIsNone(self.verify_pdf._annotation_target_page(reader, skipped))
        beyond = {"/A": {"/S": "/GoTo", "/D": [99]}}
        self.assertIsNone(self.verify_pdf._annotation_target_page(reader, beyond))
        inside = {"/A": {"/S": "/GoTo", "/D": [1]}}
        self.assertEqual(self.verify_pdf._annotation_target_page(reader, inside), 1)

    def test_a_page_reference_is_matched_by_its_indirect_object(self):
        first, second = mock.Mock(), mock.Mock()
        first.indirect_reference, second.indirect_reference = "ref-a", "ref-b"
        reader = mock.Mock(pages=[first, second])
        self.assertEqual(self.verify_pdf._annotation_target_page(reader, {"/Dest": ["ref-b"]}), 1)
        self.assertIsNone(self.verify_pdf._annotation_target_page(reader, {"/Dest": ["ref-z"]}))

    def test_a_page_that_is_mostly_empty_has_no_rhythm_to_judge(self):
        self.build()
        render = importlib.import_module("render")
        fake = types.SimpleNamespace(
            measure=lambda _path: {"body_pt": 10.0, "pitch_pt": 8.3,
                                   "lines_per_page": 11, "pages": 4}
        )
        report = self.verify_pdf.Report()
        with (
            mock.patch.dict(sys.modules, {"render.pdf_metrics": fake}),
            mock.patch.object(render, "pdf_metrics", fake, create=True),
            redirect_stdout(io.StringIO()),
        ):
            self.verify_pdf._check_density(report, self.pdf)
        _name, ok, detail = report.checks[0]
        self.assertTrue(ok, detail)
        self.assertIn("too little text to judge", detail)

    def test_the_density_ratio_is_judged_against_the_leading_window(self):
        self.build()
        render = importlib.import_module("render")
        fake = types.SimpleNamespace(
            measure=lambda _path: {"body_pt": 10.0, "pitch_pt": 14.0,
                                   "lines_per_page": 50, "pages": 10}
        )
        report = self.verify_pdf.Report()
        with (
            mock.patch.dict(sys.modules, {"render.pdf_metrics": fake}),
            mock.patch.object(render, "pdf_metrics", fake, create=True),
            mock.patch.dict(
                self.verify_pdf._config.THRESHOLDS,
                {"pdf_leading_ratio_min": 1.15, "pdf_leading_ratio_max": 1.75},
            ),
            redirect_stdout(io.StringIO()),
        ):
            self.verify_pdf._check_density(report, self.pdf)
        self.assertEqual([name for name, _ok, _d in report.checks], ["DENSITY"])
        self.assertTrue(report.checks[0][1], report.checks[0][2])
        self.assertIn("1.40x", report.checks[0][2])


class VerifyPdfLoopEdgesTest(PdfFixtureCase):
    """Loop guards inside the outline, font and annotation scans."""

    def test_an_outline_item_without_a_title_is_skipped(self):
        item = mock.Mock()
        item.get = lambda key, default="": {"/Title": ""}.get(key, default)
        reader = types.SimpleNamespace(
            outline=[item, [item]], get_destination_page_number=lambda _i: 0
        )
        self.assertEqual(self.verify_pdf.outline_entries(reader), [])

    def test_a_malformed_type3_font_resource_is_skipped(self):
        class Blind:
            def get(self, *_args):
                raise AttributeError("no dict")

        class FontMap:
            def get_object(self):
                return self

            def values(self):
                return [Blind()]

        class Resources:
            def get_object(self):
                return self

            def get(self, key):
                return FontMap() if key == "/Font" else None

        page = types.SimpleNamespace(get=lambda key: Resources() if key == "/Resources" else None)
        reader = types.SimpleNamespace(pages=[page])
        self.assertEqual(self.verify_pdf._type3_fonts(reader), set())

    def test_annotation_order_gap_and_missing_destination_are_reported(self):
        page = mock.Mock()
        page.mediabox.width = 595.0
        page.mediabox.height = 842.0
        reader = mock.Mock(pages=[page])
        outline = [("第1章", 0, 0)]

        out_of_order = [(3, 0, {})]
        self.assertIn(
            "order gap", self.verify_pdf._check_toc_links(reader, out_of_order, outline)[0]
        )

        no_target = [(0, 0, {"/Rect": [10.0, 10.0, 60.0, 22.0], "/Dest": "nope"})]
        self.assertIn(
            "destination not found", self.verify_pdf._check_toc_links(reader, no_target, outline)[0]
        )

    def test_a_link_that_targets_the_wrong_page_is_reported(self):
        page = mock.Mock()
        page.mediabox.width = 595.0
        page.mediabox.height = 842.0
        reader = mock.Mock(pages=[page, page])
        annot = {"/Dest": [1], "/Rect": [10.0, 10.0, 60.0, 22.0]}
        outline = [("第1章", 0, 0)]
        problems = self.verify_pdf._check_toc_links(reader, [(0, 0, annot)], outline)
        self.assertIn("expected 1", problems[0])


class _Ref:
    """A pypdf-shaped indirect reference over a plain dict."""

    def __init__(self, payload):
        self.idnum = id(self)
        self._payload = payload

    def get_object(self):
        return self._payload


class FontAndLinkStructureTest(unittest.TestCase):
    """The annotation and font dictionaries the checks classify.

    Every case builds the PDF object graph by hand, so the classification of one
    dictionary can be judged without a renderer.
    """

    @classmethod
    def setUpClass(cls):
        cls.mod = importlib.import_module("verify_pdf")

    def page(self, annots=None, resources=None):
        page = {}
        if annots is not None:
            page["/Annots"] = annots
        if resources is not None:
            page["/Resources"] = resources
        return page

    def reader(self, *pages):
        return types.SimpleNamespace(pages=list(pages))

    def test_annotations_that_are_not_links_are_ignored(self):
        annots = [_Ref({"/Subtype": "/Text"}), _Ref({"/Subtype": "/Link", "/NM": "toc-link-7"})]
        found = self.mod.toc_link_annotations(self.reader(self.page(annots=annots)))
        self.assertEqual([index for index, _page, _annot in found], [7])

    def test_a_composite_face_keeps_its_program_on_the_descendant(self):
        font = {"/DescendantFonts": [_Ref({"/FontDescriptor": {"/FontFile2": object()}})]}
        self.assertTrue(self.mod._has_program(font))

    def test_a_descendant_without_a_descriptor_is_not_embedded(self):
        font = {"/DescendantFonts": [_Ref({})]}
        self.assertFalse(self.mod._has_program(font))

    def test_an_unreadable_font_is_unclassifiable_rather_than_unembedded(self):
        class Unreadable:
            def get(self, _key, _default=None):
                raise AttributeError("not a PDF dictionary")

        self.assertIsNone(self.mod.font_is_embedded(Unreadable()))

    def test_a_page_without_a_font_resource_has_no_type3_fonts(self):
        pages = [self.page(), self.page(resources=_Ref({}))]
        self.assertEqual(self.mod._type3_fonts(self.reader(*pages)), set())

    def test_a_type3_font_reference_is_recorded_by_object_id(self):
        type3 = _Ref({"/Subtype": "/Type3"})
        truetype = _Ref({"/Subtype": "/TrueType"})
        resources = _Ref({"/Font": _Ref({"F1": type3, "F2": truetype})})
        found = self.mod._type3_fonts(self.reader(self.page(resources=resources)))
        self.assertEqual(found, {type3.idnum})

    def test_a_page_without_resources_contributes_no_fonts(self):
        face = {"/BaseFont": "/DejaVu", "/FontDescriptor": {"/FontFile2": object()}}
        pages = [self.page(), self.page(resources={"/Font": {"/F1": face}})]
        self.assertEqual(self.mod.non_embedded_fonts(self.reader(*pages)), [])

    def test_a_density_check_without_the_metrics_module_is_skipped(self):
        report = self.mod.Report()
        # the metrics module lives behind `render`; without the package the
        # import in the check cannot resolve, which is the case being judged
        with mock.patch.dict(sys.modules, {"render": None}):
            self.mod._check_density(report, "/nonexistent.pdf")
        name, ok, detail = report.checks[-1]
        self.assertEqual((name, ok), ("DENSITY", True))
        self.assertIn("pdf_metrics unavailable", detail)


if __name__ == "__main__":
    unittest.main()
