#!/usr/bin/env python3
"""Tests for the HTML->PDF step, with a fake Chromium engine."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from typing import Any

import _fixture
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

TAGS = ('layer:infra', 'tier:fast')  # fake chromium engine: no browser

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

def write_text_pdf(path: str, pages: list[list[str]]) -> str:
    """Write a PDF whose pages contain the given text lines (Helvetica)."""
    writer = PdfWriter()
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    })
    font_ref = writer._add_object(font)
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

class FakePage:
    def __init__(self, target: str, headings: list[dict], pages: list[list[str]]):
        self.target = target
        self.headings = headings
        self.pages = pages
        self.calls: list[str] = []

    def goto(self, url: str, **kwargs) -> None:
        self.calls.append('goto')

    def wait_for_timeout(self, ms: int) -> None:
        self.calls.append('wait')

    def evaluate(self, script: str):
        self.calls.append('evaluate')
        return self.headings if 'querySelectorAll' in script else None

    def pdf(self, path: str, **kwargs) -> None:
        write_text_pdf(path or self.target, self.pages)

class FakeBrowser:
    def __init__(self, page: FakePage):
        self._page = page
        self.closed = False

    def new_page(self):
        return self._page

    def close(self) -> None:
        self.closed = True

class FakeChromium:
    def __init__(self, page: FakePage):
        self._page = page

    def launch(self, **kwargs):
        return FakeBrowser(self._page)

class FakePlaywright:
    def __init__(self, page: FakePage):
        self.chromium = FakeChromium(page)

def fake_engine(page: FakePage):
    @contextmanager
    def engine():
        yield FakePlaywright(page)

    return engine

class PdfBuildPipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.module = _fixture.load_module(self.root, 'pdf_from_html')
        self.html = os.path.join(self.tmp.name, 'book.html')
        self.pdf = os.path.join(self.tmp.name, 'book.pdf')
        with open(self.html, 'w', encoding='utf-8') as fh:
            fh.write('<h1 id="a">Chapter One</h1><h2 id="b">Section</h2>')

    def test_parse_headings_returns_level_text_and_id(self):
        found = self.module.parse_headings(
            '<h1 id="a">标题 <em>强调</em></h1><h4 id="b">深</h4>')
        self.assertEqual(found, [(1, '标题 强调', 'a'), (4, '深', 'b')])

    def test_plain_strips_tags_and_zero_width_space(self):
        self.assertEqual(self.module.plain('<b>x</b>\u200b'), 'x')

    def test_page_texts_collapses_whitespace(self):
        write_text_pdf(self.pdf, [['__hdr_0__', 'Chapter One']])
        texts = self.module.page_texts(self.pdf)
        self.assertEqual(len(texts), 1)
        self.assertIn('__hdr_0__', texts[0])

    def test_content_start_uses_content_marker(self):
        texts = ['cover', '__content__body', 'body']
        keys = [(1, 'Chapter One', '__hdr_0__')]
        self.assertEqual(self.module.content_start(texts, keys), 1)

    def test_content_start_falls_back_to_heading_density(self):
        texts = ['cover', 'contents' * 12, 'body']
        keys = [(1, f'Heading{i}', f'Heading{i}') for i in range(12)] + \
               [(1, 'Body Heading', 'Body Heading')]
        self.assertEqual(self.module.content_start(texts, keys), 2)

    def test_content_start_defaults_to_first_body_pages(self):
        self.assertEqual(self.module.content_start(['a', 'b', 'c'], []), 2)

    def test_build_outline_creates_nested_items(self):
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        writer.add_blank_page(width=595, height=842)
        texts = ['cover', '__hdr_0__Chapter One__hdr_1__Section']
        keys = [(1, 'Chapter One', '__hdr_0__'), (2, 'Section', '__hdr_1__')]
        added, missing = self.module.build_outline(writer, texts, keys)
        self.assertEqual((added, missing), (2, []))
        out = os.path.join(self.tmp.name, 'out.pdf')
        with open(out, 'wb') as fh:
            writer.write(fh)
        outline = PdfReader(out).outline
        titles = []
        for item in outline:
            entry: Any = item
            if hasattr(entry, 'get'):
                titles.append(entry.get('/Title'))
        self.assertEqual(titles, ['Chapter One'])

    def test_build_outline_reports_missing_titles(self):
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        added, missing = self.module.build_outline(
            writer, ['cover'], [(1, 'Missing Title', '__hdr_9__')])
        self.assertEqual(added, 0)
        self.assertEqual(missing, ['Missing Title'])

    def test_build_outline_uses_short_key_fallback(self):
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        texts = ['cover mentions ABCDEFGHIJKLMNOPQRSTUVWXYZ and more']
        added, missing = self.module.build_outline(
            writer, texts, [(1, 'Title', 'ABCDEFGHIJKLMNOPQRSTUVWXYZXX')])
        self.assertEqual((added, missing), (1, []))

    def test_build_end_to_end_with_markers(self):
        headings = [{'index': 0, 'id': 'a', 'text': 'Chapter One', 'level': 1},
                    {'index': 1, 'id': 'b', 'text': 'Section', 'level': 2}]
        page = FakePage(self.pdf, headings,
                        [['cover'], ['__content__', '__hdr_0__', 'Chapter One'],
                         ['__hdr_1__', 'Section']])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            added, missing = self.module.build(self.html, self.pdf, fake_engine(page))
        self.assertEqual((added, missing), (2, []))
        self.assertIn('PDF saved', buffer.getvalue())
        self.assertTrue(os.path.exists(self.pdf))

    def test_build_falls_back_when_markers_are_absent(self):
        headings = [{'index': 0, 'id': 'a', 'text': 'Chapter One', 'level': 1}]
        page = FakePage(self.pdf, headings,
                        [['cover'], ['body'], ['Chapter One??']])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            added, _missing = self.module.build(self.html, self.pdf, fake_engine(page))
        self.assertEqual(added, 1)
        self.assertIn('falling back', buffer.getvalue())

    def test_main_reports_browser_error(self):
        def broken():
            raise RuntimeError('no chromium')

        with redirect_stdout(io.StringIO()), \
                redirect_stderr(io.StringIO()) as err:
            code = self.module.main(['--html', self.html, '--pdf', self.pdf],
                                    engine=broken)
        self.assertEqual(code, 2)
        self.assertIn('chromium', err.getvalue())

if __name__ == '__main__':
    unittest.main()
