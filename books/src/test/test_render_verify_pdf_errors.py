#!/usr/bin/env python3
"""Error and fallback paths of the delivery scripts.

Missing optional tools (pandoc, chromium), missing prerequisites and malformed
artifacts are the branches that never run in the happy path but do fire in real
use — and they are where a toolchain silently misbehaves instead of reporting.
"""

import importlib.util
import os
import sys
import unittest

import _fixture
from _cases import Base

TAGS = ('layer:render', 'tier:fast')  # pypdf only; heavy deps stay skipped

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

HAS_PYPDF = importlib.util.find_spec('pypdf') is not None


class TestVerifyPdfErrorPaths(Base):
    @unittest.skipUnless(HAS_PYPDF, 'pypdf not installed')
    def test_require_toc_links_without_annotations(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        for _ in range(2):
            writer.add_blank_page(width=595, height=842)
        writer.add_outline_item(title='第1章 测试', page_number=0)
        pdf = os.path.join(self.root, 'dist', 'no-links.pdf')
        with open(pdf, 'wb') as fh:
            writer.write(fh)
        html = os.path.join(self.root, 'dist', 'no-links.html')
        with open(html, 'w', encoding='utf-8') as fh:
            fh.write('<h1 id="a">第1章 测试</h1>'
                     '<nav id="toc-page-nav"><a href="#a">第1章 测试</a></nav>')
        code, out = self.run_script('verify_pdf.py', '--pdf', pdf, '--html', html,
                                    '--require-toc-links')
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('TOC_LINKS', out)

    def test_missing_pdf_json(self):
        _code, out = self.run_script('verify_pdf.py', '--json')
        self.assertIn('"ok"', out)

    def test_epub_json(self):
        _code, out = self.run_script('verify_epub.py', '--json')
        self.assertIn('"ok"', out)


class TestVerifyPdfTocLinkSuccess(Base):
    @unittest.skipUnless(HAS_PYPDF, 'pypdf not installed')
    def test_valid_toc_annotation_targets_outline_page(self):
        from pypdf import PdfWriter
        from pypdf.annotations import Link
        from pypdf.generic import NameObject, TextStringObject

        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=595, height=842)
        writer.add_outline_item(title='第1章 测试', page_number=0)
        writer.add_outline_item(title='1.1 小节', page_number=1)
        annot = Link(rect=(50, 700, 300, 720), target_page_index=0)
        annot[NameObject('/NM')] = TextStringObject('toc-link-0')
        writer.add_annotation(0, annot)
        pdf = os.path.join(self.root, 'dist', 'links.pdf')
        with open(pdf, 'wb') as fh:
            writer.write(fh)
        html = os.path.join(self.root, 'dist', 'links.html')
        with open(html, 'w', encoding='utf-8') as fh:
            fh.write('<h1 id="a">第1章 测试</h1><h2 id="b">1.1 小节</h2>'
                     '<nav id="toc-page-nav"><a href="#a">第1章 测试</a></nav>')
        code, out = self.run_script('verify_pdf.py', '--pdf', pdf, '--html', html,
                                    '--require-toc-links')
        self.assertIn(code, (0, 1), out[-600:])
        self.assertIn('TOC_LINKS', out)

    def test_annotation_rect_and_target_helpers(self):
        verify_pdf = _fixture.load_module(self.root, 'verify_pdf')
        self.assertEqual(verify_pdf._annotation_rect(object()), [])
        self.assertIsNone(verify_pdf._annotation_target_page(None, {'/A': {'/S': '/URI'}}))


if __name__ == '__main__':
    unittest.main()
