#!/usr/bin/env python3
"""The print edition is the delivery renderer plus one print-only stylesheet.

What this pins down: the print edition goes through the split renderer (one page box,
one column, no scale of its own), the profile is injected into a staging file and
removed afterwards, and nothing in the pipeline decides a margin or a size on its own.
"""

from __future__ import annotations

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

TAGS = ('layer:infra', 'tier:fast')  # fake chromium engine: no browser

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


def write_text_pdf(path: str, pages: list[list[str]]) -> None:
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
    with open(path, 'wb') as handle:
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
        if 'holder' in script:          # the splitter's chapter split
            return self.parts
        if '__CONTENT__' in script:     # the marker injection
            return self.headings
        return None

    def pdf(self, path: str | None = None, **kwargs) -> None:
        self.pdf_kwargs = kwargs
        write_text_pdf(path or self.target, [['__CONTENT__', '__hdr_0__Chapter One']])


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
        self.module = _fixture.load_module(self.root, 'print_pdf')
        self.profile = _fixture.load_module(self.root, 'print_profile')
        self.html = os.path.join(self.tmp.name, 'book.html')
        self.pdf = os.path.join(self.tmp.name, 'print.pdf')
        with open(self.html, 'w', encoding='utf-8') as handle:
            handle.write('<html><head></head><body><div id="content">'
                         '<h1 id="a">Chapter One</h1><p>text</p>'
                         '<h1 id="b">Chapter Two</h1></div></body></html>')
        self.parts = [{'html': '<h1 id="a">Chapter One</h1>',
                       'headings': [{'level': 1, 'text': 'Chapter One'}]},
                      {'html': '<h1 id="b">Chapter Two</h1>',
                       'headings': [{'level': 1, 'text': 'Chapter Two'}]}]
        self.headings = [{'index': 0, 'id': 'a', 'level': 1, 'text': 'Chapter One'}]

    def test_the_profile_is_injected_once_before_the_head_closes(self):
        once = self.profile.inject('<head></head>')
        self.assertIn('print-grade-css', once)
        self.assertIn('@media print', once)
        self.assertEqual(self.profile.inject(once), once)

    def test_the_profile_does_not_fix_type_in_pixels(self):
        block = self.profile.style_block()
        self.assertNotRegex(block, r'font-size:\s*[\d.]+px')
        self.assertNotRegex(block, r'(padding|margin)[^;]*\d+px')
        self.assertIn('em', block)

    def test_the_accent_comes_from_the_books_display_copy(self):
        # accent() resolves the config at call time, so patch the module it imports
        with mock.patch('lib._config.project', return_value='#123456'):
            self.assertIn('#123456', self.profile.style_block())

    def test_build_renders_through_the_splitter(self):
        page = SplitPage(self.pdf, self.parts, self.headings)
        with redirect_stdout(io.StringIO()):
            count = self.module.build(self.html, self.pdf, fake_engine(page))
        self.assertEqual(count, 3)   # front matter + one page per chapter part
        self.assertEqual(page.viewport, {'width': 794, 'height': 1123})
        self.assertTrue(page.pdf_kwargs['prefer_css_page_size'])
        self.assertNotIn('scale', page.pdf_kwargs)     # no per-edition magnification
        self.assertTrue(os.path.exists(self.pdf))

    def test_the_staged_html_carries_the_profile_and_is_removed(self):
        seen: dict[str, str] = {}

        def capture(path: str, _target: str, **_kwargs) -> int:
            with open(path, encoding='utf-8') as handle:
                seen['html'] = handle.read()
            seen['path'] = path
            return 3

        with mock.patch.object(self.module.pdf_split, 'render_html', side_effect=capture), \
                redirect_stdout(io.StringIO()):
            count = self.module.build(self.html, self.pdf)
        self.assertEqual(count, 3)
        self.assertIn('print-grade-css', seen['html'])
        self.assertFalse(os.path.exists(seen['path']))

    def test_a_missing_source_is_reported_not_raised(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = self.module._errors.run(self.module.main, [
                '--skip-html', '--html', os.path.join(self.tmp.name, 'nope.html'),
                '--pdf', self.pdf])
        self.assertEqual(code, 1)

    def test_main_returns_zero_on_success(self):
        page = SplitPage(self.pdf, self.parts, self.headings)
        with redirect_stdout(io.StringIO()):
            code = self.module.main(['--skip-html', '--html', self.html,
                                     '--pdf', self.pdf], engine=fake_engine(page))
        self.assertEqual(code, 0)


if __name__ == '__main__':
    unittest.main()
