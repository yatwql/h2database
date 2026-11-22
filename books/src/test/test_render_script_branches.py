#!/usr/bin/env python3
"""Branches of the delivery scripts: the paths a healthy build never takes.

Chromium and pandoc are real here, so the expensive branches are driven through
the seams the scripts already expose (an injectable engine, a missing input
file) rather than by rendering anything.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock

import _fixture

TAGS = ('layer:render', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python')
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

HAS_PYPDF = importlib.util.find_spec('pypdf') is not None
HAS_PANDOC = bool(shutil.which('pandoc'))


class FakePage:
    def __init__(self) -> None:
        self.pdf_calls: list[dict] = []
        self.visited: list[str] = []

    def goto(self, url: str, **_kwargs) -> None:
        self.visited.append(url)

    def evaluate(self, _script: str):
        return [{'level': 1, 'text': '第1章', 'id': 'a'}]

    def wait_for_timeout(self, _ms: int) -> None:
        return None

    def pdf(self, **kwargs) -> None:
        self.pdf_calls.append(kwargs)


class FakeBrowser:
    def __init__(self, page: FakePage) -> None:
        self.page = page
        self.closed = False

    def new_page(self, **_kwargs) -> FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser

    def launch(self, **_kwargs) -> FakeBrowser:
        return self.browser


class FakeEngine:
    """Minimal stand-in for ``sync_playwright``."""

    def __init__(self) -> None:
        self.page = FakePage()
        self.browser = FakeBrowser(self.page)
        self.chromium = FakeChromium(self.browser)

    def __call__(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> bool:
        return False


class PdfFromHtmlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'pdf_from_html')

    def test_render_pdf_drives_the_engine_and_returns_headings(self):
        engine = FakeEngine()
        target = os.path.join(self.tmp.name, 'out.pdf')
        headings = self.mod.render_pdf('<h1 id="a">第1章</h1>', target, engine=engine)
        self.assertTrue(engine.page.visited[0].startswith('file:///'))
        self.assertEqual(engine.page.pdf_calls[0]['format'], 'A4')
        self.assertTrue(engine.browser.closed)
        self.assertEqual(headings[0]['id'], 'a')

    def test_parse_headings_keeps_level_text_and_id(self):
        found = self.mod.parse_headings('<h2 id="b">1.1 小节</h2><h3>无 id</h3>')
        self.assertEqual(found, [(2, '1.1 小节', 'b')])

    def test_a_missing_html_source_stops_the_script(self):
        html = os.path.join(self.tmp.name, 'missing.html')
        code, out = _fixture.run_inproc(self.root, 'pdf_from_html.py', html,
                                        os.path.join(self.tmp.name, 'x.pdf'))
        self.assertNotEqual(code, 0, out[-300:])


class ToEpubTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    @unittest.skipUnless(HAS_PANDOC, 'pandoc not on PATH')
    def test_the_epub_is_built_from_the_merged_manuscript(self):
        code, out = _fixture.run_inproc(self.root, 'to_epub.py')
        self.assertEqual(code, 0, out[-600:])
        produced = os.path.join(self.root, 'dist', 'test-book.epub')
        self.assertTrue(os.path.isfile(produced), out[-300:])

    def test_without_pandoc_the_script_explains_the_install(self):
        saved = os.environ.get('PATH', '')
        os.environ['PATH'] = ''
        try:
            code, out = _fixture.run_inproc(self.root, 'to_epub.py')
        finally:
            os.environ['PATH'] = saved
        self.assertNotEqual(code, 0, out[-400:])
        self.assertIn('pandoc', out.lower())


@unittest.skipUnless(HAS_PYPDF, 'pypdf not installed')
class VerifyPdfHelpersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'verify_pdf')

    def build(self, outline: bool = True, annot: bool = False) -> str:
        from pypdf import PdfWriter
        from pypdf.annotations import Link
        from pypdf.generic import NameObject, TextStringObject
        path = os.path.join(self.tmp.name, 'x.pdf')
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        if outline:
            top = writer.add_outline_item(title='第1章', page_number=0)
            writer.add_outline_item(title='1.1 小节', page_number=0, parent=top)
        if annot:
            link = Link(rect=(10.0, 10.0, 60.0, 22.0), target_page_index=0)
            writer.add_annotation(0, link)
        with open(path, 'wb') as fh:
            writer.write(fh)
        if annot:
            from pypdf import PdfReader
            reader = PdfReader(path)
            refs = reader.pages[0].get('/Annots') or []
            obj = next(iter(refs)).get_object()
            obj[NameObject('/NM')] = TextStringObject('toc-link-0')
            writer = PdfWriter()
            writer.append(reader)
            with open(path, 'wb') as fh:
                writer.write(fh)
        return path

    def test_nested_outline_entries_carry_their_depth(self):
        from pypdf import PdfReader
        entries = self.mod.outline_entries(PdfReader(self.build()))
        self.assertEqual([depth for _t, _p, depth in entries], [0, 1])

    def test_a_link_without_a_name_is_not_a_toc_link(self):
        from pypdf import PdfReader
        self.assertEqual(self.mod.toc_link_annotations(PdfReader(self.build(annot=True)))[0][0], 0)
        path = self.build()
        self.assertEqual(self.mod.toc_link_annotations(PdfReader(path)), [])

    def test_an_unnamed_annotation_is_skipped(self):
        from pypdf import PdfReader, PdfWriter
        path = self.build()
        writer = PdfWriter()
        writer.append(PdfReader(path))
        with open(path, 'wb') as fh:
            writer.write(fh)
        self.assertEqual(self.mod.toc_link_annotations(PdfReader(path)), [])

    def test_a_type0_font_without_an_embedded_program_is_reported(self):
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import ArrayObject, DictionaryObject, NameObject
        path = self.build()
        writer = PdfWriter()
        writer.append(PdfReader(path))
        font = DictionaryObject()
        font[NameObject('/Type')] = NameObject('/Font')
        font[NameObject('/Subtype')] = NameObject('/Type0')
        font[NameObject('/BaseFont')] = NameObject('/Noto')
        font[NameObject('/DescendantFonts')] = ArrayObject([])
        writer.pages[0][NameObject('/Resources')] = DictionaryObject(
            {NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        with open(path, 'wb') as fh:
            writer.write(fh)
        self.assertIn('/Noto', self.mod.non_embedded_fonts(PdfReader(path)))

    def html(self, body: str = '<h1 id="a">第1章</h1><h2 id="b">1.1 小节</h2>') -> str:
        path = os.path.join(self.tmp.name, 'book.html')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(f'<!DOCTYPE html><html><body>{body}</body></html>')
        return path

    def test_a_pdf_over_the_size_budget_fails(self):
        html = self.html()
        with unittest.mock.patch.dict(self.mod._config.THRESHOLDS, {'pdf_max_mb': 0.000001}):
            report = self.mod.verify(self.build(), html)
        self.assertIn('SIZE', [name for name, _d in report.failures])

    def test_a_page_without_a_printed_toc_fails_the_count(self):
        report = self.mod.verify(self.build(), self.html())
        self.assertIn('TOC_COUNT', [name for name, _d in report.failures])

    def test_an_outline_deeper_than_the_headings_is_flagged(self):
        report = self.mod.verify(self.build(), self.html('<h1 id="a">第1章</h1>'))
        self.assertIn('OUTLINE', [name for name, _d in report.failures])

    def test_an_annotation_pointing_at_the_wrong_page_is_reported(self):
        path = self.build(annot=True)
        from pypdf import PdfReader, PdfWriter
        from pypdf.annotations import Link
        writer = PdfWriter()
        writer.append(PdfReader(path))
        writer.add_blank_page(width=595, height=842)
        writer.add_annotation(0, Link(rect=(10.0, 10.0, 60.0, 22.0), target_page_index=1))
        with open(path, 'wb') as fh:
            writer.write(fh)
        report = self.mod.verify(path, self.html())
        self.assertIn('TOC_LINKS', [name for name, _d in report.failures])


    def test_a_malformed_rectangle_yields_nothing(self):
        from pypdf.generic import ArrayObject, TextStringObject
        self.assertEqual(self.mod._annotation_rect({'/Rect': TextStringObject('x')}), [])
        self.assertEqual(self.mod._annotation_rect({'/Rect': ArrayObject([])}), [])


if __name__ == '__main__':
    unittest.main()
