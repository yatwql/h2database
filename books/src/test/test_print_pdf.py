#!/usr/bin/env python3
"""Tests for the print-grade PDF pipeline (fake Chromium engine)."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout

import _fixture
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

TAGS = ('layer:infra', 'tier:slow')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

def write_text_pdf(path: str, pages: list[list[str]]) -> str:
    """A4 pages carrying the given ASCII text lines."""
    writer = PdfWriter()
    font_ref = writer._add_object(DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    }))
    for lines in pages:
        page = writer.add_blank_page(width=595, height=842)
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): DictionaryObject({NameObject('/F1'): font_ref})})
        stream = DecodedStreamObject()
        body = ['BT', '/F1 12 Tf', '14 TL', '40 800 Td']
        for line in lines:
            escaped = line.replace('(', r'\(').replace(')', r'\)')
            body.append(f'({escaped}) Tj T*')
        body.append('ET')
        stream.set_data('\n'.join(body).encode('utf-8'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    with open(path, 'wb') as fh:
        writer.write(fh)
    return path

class RecordingPage:
    def __init__(self, target: str, pages: list[list[str]]):
        self.target = target
        self.pages = pages
        self.pdf_kwargs: dict = {}

    def goto(self, url: str, **kwargs) -> None:
        return None

    def wait_for_timeout(self, ms: int) -> None:
        return None

    def evaluate(self, script: str):
        return None

    def pdf(self, path: str, **kwargs) -> None:
        self.pdf_kwargs = kwargs
        write_text_pdf(path or self.target, self.pages)

class FakeBrowser:
    def __init__(self, page):
        self._page = page

    def new_page(self):
        return self._page

    def close(self) -> None:
        return None

class FakeChromium:
    def __init__(self, page):
        self._page = page

    def launch(self, **kwargs):
        return FakeBrowser(self._page)

class FakePlaywright:
    def __init__(self, page):
        self.chromium = FakeChromium(page)

def fake_engine(page):
    @contextmanager
    def engine():
        yield FakePlaywright(page)

    return engine

class PrintGradePdfTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.module = _fixture.load_module(self.root, 'print_pdf')
        self.html = os.path.join(self.tmp.name, 'book.html')
        self.pdf = os.path.join(self.tmp.name, 'print.pdf')
        with open(self.html, 'w', encoding='utf-8') as fh:
            fh.write('<html><head></head><body><h1 id="a">Chapter One</h1>'
                     '<h2 id="b">Section</h2></body></html>')

    def test_parse_headings_matches_the_pdf_step(self):
        found = self.module.parse_headings('<h1 id="a">T <b>x</b></h1><h3 id="b">Deep</h3>')
        self.assertEqual([(h['level'], h['text'], h['id']) for h in found],
                         [(1, 'T x', 'a'), (3, 'Deep', 'b')])

    def test_inject_css_is_idempotent(self):
        once = self.module.inject_css('<head></head>')
        self.assertIn('print-grade-css', once)
        self.assertEqual(self.module.inject_css(once), once)

    def test_templates_carry_title_and_page_numbers(self):
        header = self.module.header_template('我的书', '印刷版 v0.1')
        self.assertIn('我的书', header)
        self.assertIn('印刷版 v0.1', header)
        footer = self.module.footer_template()
        self.assertIn('pageNumber', footer)
        self.assertIn('totalPages', footer)

    def test_render_pdf_passes_print_options(self):
        page = RecordingPage(self.pdf, [['cover']])
        self.module.render_pdf(self.html, self.pdf, engine=fake_engine(page),
                               running_head='书', label='印刷版 v0.1')
        self.assertEqual(page.pdf_kwargs['format'], 'A4')
        self.assertTrue(page.pdf_kwargs['display_header_footer'])
        self.assertIn('书', page.pdf_kwargs['header_template'])
        self.assertTrue(os.path.exists(self.pdf))

    def test_page_texts_and_content_start(self):
        write_text_pdf(self.pdf, [['cover'], ['__CONTENT__body']])
        texts = self.module.page_texts(self.pdf)
        self.assertEqual(self.module.content_start(texts), 1)
        self.assertEqual(self.module.content_start(['a', 'b']), 0)

    def test_add_outlines_writes_entries_and_reports_missing(self):
        write_text_pdf(self.pdf, [['cover'], ['__CONTENT__', '__hdr_0__Chapter One']])
        found, missing = self.module.add_outlines(self.pdf, [
            {'index': 0, 'level': 1, 'id': 'a', 'text': 'Chapter One'},
            {'index': 9, 'level': 2, 'id': 'z', 'text': 'Missing'},
        ])
        self.assertEqual((found, missing), (1, ['Missing']))
        self.assertTrue(PdfReader(self.pdf).outline)

    def test_build_runs_the_whole_pipeline(self):
        page = RecordingPage(self.pdf, [['cover'], ['__CONTENT__', '__hdr_0__Chapter One'],
                                        ['__hdr_1__Section']])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            found, missing = self.module.build(self.html, self.pdf, fake_engine(page))
        self.assertEqual((found, missing), (2, []))
        self.assertIn('Created 2', buffer.getvalue())
        self.assertFalse(os.path.exists(
            os.path.join(self.root, 'dist', f'_{self.module._config.MERGED_NAME}-print.html')))

    def test_main_skips_html_regeneration_and_reports_failure(self):
        def broken():
            raise RuntimeError('no chromium')

        with redirect_stdout(io.StringIO()), \
                __import__('contextlib').redirect_stderr(io.StringIO()):
            code = self.module.main(['--skip-html', '--html', self.html,
                                     '--pdf', self.pdf], engine=broken)
        self.assertEqual(code, 1)

    def test_main_returns_zero_on_success(self):
        page = RecordingPage(self.pdf, [['cover'], ['__CONTENT__', '__hdr_0__Chapter One']])
        with redirect_stdout(io.StringIO()):
            code = self.module.main(['--skip-html', '--html', self.html, '--pdf', self.pdf],
                                    engine=fake_engine(page))
        self.assertEqual(code, 0)

if __name__ == '__main__':
    unittest.main()
