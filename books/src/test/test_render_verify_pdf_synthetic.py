#!/usr/bin/env python3
"""Unit tests for the helper functions behind the audits.

These target the pure logic (counting, parsing, clustering, PDF checks) that the
end-to-end tests exercise only indirectly.
"""
import importlib.util
import os
import sys
import tempfile
import unittest

import _fixture

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


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def module(self, name: str):
        return _fixture.load_module(self.root, name)

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path


class TestVerifyPdfOnSyntheticFile(FixtureCase):
    """Exercise the PDF checker against a PDF we build ourselves."""

    def build_pdf(self) -> tuple[str, str]:
        from pypdf import PdfReader, PdfWriter

        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=595, height=842)
        writer.add_outline_item(title='第1章 测试章节', page_number=0)
        writer.add_outline_item(title='1.1 小节', page_number=1)

        pdf_path = os.path.join(self.root, 'dist', 'synthetic.pdf')
        with open(pdf_path, 'wb') as fh:
            writer.write(fh)

        # A TOC link annotation pointing at page 0, named toc-link-0.
        reader = PdfReader(pdf_path, strict=False)
        html = ('<h1 id="a">第1章 测试章节</h1><h2 id="b">1.1 小节</h2>'
                '<nav id="toc-page-nav"><a href="#a">第1章 测试章节</a>'
                '<a href="#b">1.1 小节</a></nav>')
        html_path = os.path.join(self.root, 'dist', 'synthetic.html')
        with open(html_path, 'w', encoding='utf-8') as fh:
            fh.write(html)
        del reader
        return pdf_path, html_path

    def test_outline_and_toc_checks_run(self):
        verify_pdf = self.module('verify_pdf')
        pdf_path, html_path = self.build_pdf()
        report = verify_pdf.verify(pdf_path, html_path)
        names = [name for name, _ok, _d in report.checks]
        self.assertIn('OUTLINE', names)
        self.assertIn('TOC_COUNT', names)
        self.assertIn('PAGES', names)
        outline_check = next(c for c in report.checks if c[0] == 'OUTLINE')
        self.assertTrue(outline_check[1], outline_check[2])

    def test_missing_html_reported(self):
        verify_pdf = self.module('verify_pdf')
        pdf_path, _ = self.build_pdf()
        report = verify_pdf.verify(pdf_path, os.path.join(self.root, 'nope.html'))
        self.assertIn('SOURCE_HTML', [n for n, _d in report.failures])


if __name__ == '__main__':
    unittest.main()
