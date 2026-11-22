#!/usr/bin/env python3
"""PDF verification and TOC-link injection, driven by synthetic PDFs.

`verify()` judges a finished PDF against its HTML; `add_links()` writes the
clickable printed-TOC annotations. Both are pure pypdf work once the coordinates
are supplied, so the whole decision chain runs without a browser.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
import tempfile
import unittest

import _fixture

TAGS = ('layer:render', 'tier:fast')  # needs pypdf only; other deps are skipped

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python')
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

HAS_PYPDF = importlib.util.find_spec('pypdf') is not None

HTML = """<!DOCTYPE html><html><body>
<h1 id="a">第1章</h1><h2 id="b">1.1 小节</h2>
<nav id="toc-page-nav">
  <a href="#a">第1章</a>
  <a href="#b">1.1 小节</a>
</nav></body></html>
"""


@unittest.skipUnless(HAS_PYPDF, 'pypdf not installed')
class PdfFixtureCase(unittest.TestCase):
    """Synthetic PDFs and the book fixture; no test methods of its own."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.verify_pdf = _fixture.load_module(self.root, 'verify_pdf')
        self.pdf = os.path.join(self.tmp.name, 'book.pdf')
        self.html = os.path.join(self.tmp.name, 'book.html')
        with open(self.html, 'w', encoding='utf-8') as fh:
            fh.write(HTML)

    def build(self, size=(595, 842), pages=2, outline=True, rotate=0,
              non_embedded=False, same_size=True, with_toc=True) -> str:
        from pypdf import PdfWriter
        writer = PdfWriter()
        for index in range(pages):
            width, height = size if same_size or index == 0 else (612, 792)
            page = writer.add_blank_page(width=width, height=height)
            if rotate:
                from pypdf.generic import NameObject, NumberObject
                page[NameObject('/Rotate')] = NumberObject(rotate)
            if non_embedded:
                from pypdf.generic import DictionaryObject, NameObject
                font = DictionaryObject()
                font[NameObject('/Type')] = NameObject('/Font')
                font[NameObject('/Subtype')] = NameObject('/Type1')
                font[NameObject('/BaseFont')] = NameObject('/Helvetica')
                page[NameObject('/Resources')] = DictionaryObject(
                    {NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        if outline:
            first = writer.add_outline_item(title='第1章', page_number=0)
            writer.add_outline_item(title='1.1 小节', page_number=0, parent=first)
        with open(self.pdf, 'wb') as fh:
            writer.write(fh)
        if not with_toc:
            with open(self.html, 'w', encoding='utf-8') as fh:
                fh.write(HTML.replace('<a href="#b">1.1 小节</a>', ''))
        return self.pdf

    def failures(self, report) -> list[str]:
        return [name for name, _detail in report.failures]


@unittest.skipUnless(HAS_PYPDF, 'pypdf not installed')
class VerifyPdfTest(PdfFixtureCase):
    def test_a_healthy_pdf_passes_every_check(self):
        self.build()
        report = self.verify_pdf.verify(self.pdf, self.html)
        self.assertEqual(report.failures, [])
        self.assertTrue(report.to_dict()['ok'])

    def test_a_missing_pdf_or_html_is_reported(self):
        report = self.verify_pdf.verify(self.pdf, self.html)
        self.assertIn('EXISTS', self.failures(report))
        with open(self.pdf, 'wb') as fh:
            fh.write(b'%PDF-1.4 placeholder')
        report = self.verify_pdf.verify(self.pdf, os.path.join(self.tmp.name, 'no.html'))
        self.assertIn('SOURCE_HTML', self.failures(report))

    def test_a_letter_page_fails_the_size_check(self):
        self.build(size=(612, 792))
        self.assertIn('PAGE_SIZE', self.failures(self.verify_pdf.verify(self.pdf, self.html)))

    def test_a_rotated_page_fails(self):
        self.build(rotate=90)
        self.assertIn('ROTATION', self.failures(self.verify_pdf.verify(self.pdf, self.html)))

    def test_a_non_embedded_font_is_named(self):
        self.build(non_embedded=True)
        failures = dict(self.verify_pdf.verify(self.pdf, self.html).failures)
        self.assertIn('FONTS', failures)
        self.assertIn('Helvetica', failures['FONTS'])

    def test_missing_outline_fails(self):
        self.build(outline=False)
        self.assertIn('OUTLINE', self.failures(self.verify_pdf.verify(self.pdf, self.html)))

    def test_the_printed_toc_count_must_match_the_headings(self):
        self.build(with_toc=False)
        self.assertIn('TOC_COUNT', self.failures(self.verify_pdf.verify(self.pdf, self.html)))

    def test_links_are_optional_until_required(self):
        self.build()
        relaxed = self.verify_pdf.verify(self.pdf, self.html, require_toc_links=False)
        self.assertNotIn('TOC_LINKS', self.failures(relaxed))
        strict = self.verify_pdf.verify(self.pdf, self.html, require_toc_links=True)
        self.assertIn('TOC_LINKS', self.failures(strict))

    def first_annotation(self, reader):
        """First annotation object of page 1 (pypdf's array is untyped)."""
        references = reader.pages[0].get('/Annots') or []
        for reference in references:
            return reference.get_object()
        raise AssertionError('the page carries no annotation')

    def test_a_link_annotation_outside_the_page_is_rejected(self):
        from pypdf import PdfReader, PdfWriter
        from pypdf.annotations import Link
        from pypdf.generic import (ArrayObject, FloatObject, NameObject,
                                   TextStringObject)
        self.build()
        writer = PdfWriter()
        writer.append(PdfReader(self.pdf))
        writer.add_annotation(0, Link(rect=(10.0, 10.0, 60.0, 22.0), target_page_index=0))
        with open(self.pdf, 'wb') as fh:
            writer.write(fh)
        reader = PdfReader(self.pdf)
        annot = self.first_annotation(reader)
        # the injected links carry an /NM name; the check then judges the rect
        annot[NameObject('/NM')] = TextStringObject('toc-link-0')
        annot[NameObject('/Rect')] = ArrayObject(
            [FloatObject(-10.0), FloatObject(-10.0), FloatObject(5.0), FloatObject(5.0)])
        writer = PdfWriter()
        writer.append(reader)
        with open(self.pdf, 'wb') as fh:
            writer.write(fh)
        self.assertIn('TOC_LINKS', self.failures(self.verify_pdf.verify(self.pdf, self.html)))

    def test_annotation_rect_tolerates_missing_or_short_rectangles(self):
        self.assertEqual(self.verify_pdf._annotation_rect(object()), [])
        from pypdf.generic import ArrayObject, FloatObject
        annot = {'/Rect': ArrayObject([FloatObject(1), FloatObject(2)])}
        self.assertEqual(self.verify_pdf._annotation_rect(annot), [1.0, 2.0])

    def test_annotation_target_page_reads_named_destinations(self):
        from pypdf import PdfReader
        self.build()
        reader = PdfReader(self.pdf)
        self.assertIsNone(self.verify_pdf._annotation_target_page(reader, {'/Dest': 'nope'}))

    def test_non_embedded_fonts_accepts_type3_glyphs(self):
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import DictionaryObject, NameObject
        self.build()
        writer = PdfWriter()
        writer.append(PdfReader(self.pdf))
        page = writer.pages[0]
        type3 = DictionaryObject()
        type3[NameObject('/Type')] = NameObject('/Font')
        type3[NameObject('/Subtype')] = NameObject('/Type3')
        type3[NameObject('/BaseFont')] = NameObject('/T3')
        page[NameObject('/Resources')] = DictionaryObject(
            {NameObject('/Font'): DictionaryObject({NameObject('/F3'): type3})})
        with open(self.pdf, 'wb') as fh:
            writer.write(fh)
        self.assertEqual(self.verify_pdf.non_embedded_fonts(PdfReader(self.pdf)), [])


@unittest.skipUnless(HAS_PYPDF, 'pypdf not installed')
class TocLinkInjectionTest(PdfFixtureCase):
    def setUp(self):
        super().setUp()
        self.mod = _fixture.load_module(self.root, 'pdf_toc_links')
        self.build()

    def link(self, index: int, y: float, *, width: float = 100.0) -> dict:
        return {'index': index, 'text': '第1章', 'href': '#a',
                'rect': {'x': 100.0, 'y': y, 'w': width, 'h': 12.0}}

    def inject(self, links) -> str:
        target = os.path.join(self.tmp.name, 'out.pdf')
        self.mod.add_links(pdf_path=pathlib.Path(self.pdf),
                           html_path=pathlib.Path(self.html),
                           tmp_path=pathlib.Path(target),
                           toc_links=links)
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
            self.mod.add_links(pdf_path=pathlib.Path(os.path.join(self.tmp.name, 'no.pdf')),
                               html_path=pathlib.Path(self.html),
                               toc_links=[self.link(0, 100.0)])

    def test_a_missing_html_is_refused(self):
        with self.assertRaises(SystemExit):
            self.mod.add_links(pdf_path=pathlib.Path(self.pdf),
                               html_path=pathlib.Path(
                                   os.path.join(self.tmp.name, 'no.html')),
                               toc_links=[self.link(0, 100.0)])

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
        links = [{**self.link(0, 200.0), 'text': '别的标题'}, self.link(1, 240.0)]
        self.inject(links)
        self.assertEqual(len(self.verify_pdf.toc_link_annotations(PdfReader(self.pdf))), 2)


if __name__ == '__main__':
    unittest.main()
