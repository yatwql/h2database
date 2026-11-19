#!/usr/bin/env python3
"""Tests for the print/delivery gates: _audit_ascii, verify_epub, verify_pdf."""

import importlib
import os
import sys
import tempfile
import unittest
import zipfile

TAGS = ('layer:render', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

audit_ascii = importlib.import_module('diagrams')
verify_epub = importlib.import_module('verify_epub')
verify_pdf = importlib.import_module('verify_pdf')

class TestEpubVerification(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def build_epub(self, *, omit_nav: bool = False, bad_mimetype: bool = False) -> str:
        path = os.path.join(self.tmp.name, 'book.epub')
        nav = ('<?xml version="1.0" encoding="utf-8"?>'
               '<html xmlns="http://www.w3.org/1999/xhtml"><body><nav>'
               '<a href="ch1.xhtml">第一章</a></nav></body></html>')
        opf = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<dc:title>测试之书</dc:title><dc:creator>tester</dc:creator>'
            '<dc:language>zh-CN</dc:language>'
            '<dc:identifier id="uid">urn:uuid:test</dc:identifier></metadata>'
            '<manifest>'
            '<item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
            'properties="nav"/>'
            '</manifest>'
            '<spine><itemref idref="ch1"/></spine>'
            '</package>'
        )
        container = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
            'version="1.0"><rootfiles>'
            '<rootfile full-path="EPUB/content.opf" '
            'media-type="application/oebps-package+xml"/>'
            '</rootfiles></container>'
        )
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('mimetype', 'text/plain' if bad_mimetype
                        else 'application/epub+zip', zipfile.ZIP_STORED)
            zf.writestr('META-INF/container.xml', container)
            zf.writestr('EPUB/content.opf', opf)
            zf.writestr('EPUB/ch1.xhtml', '<html><body>正文</body></html>')
            if not omit_nav:
                zf.writestr('EPUB/nav.xhtml', nav)
        return path

    def test_valid_epub_passes(self):
        report = verify_epub.verify(self.build_epub())
        self.assertEqual(report.failures, [], report.checks)

    def test_bad_mimetype_fails(self):
        report = verify_epub.verify(self.build_epub(bad_mimetype=True))
        self.assertIn('MIMETYPE', [name for name, _d in report.failures])

    def test_missing_nav_file_fails(self):
        report = verify_epub.verify(self.build_epub(omit_nav=True))
        self.assertIn('MANIFEST', [name for name, _d in report.failures])

    def test_missing_epub_reports_exists(self):
        report = verify_epub.verify(os.path.join(self.tmp.name, 'nope.epub'))
        self.assertIn('EXISTS', [name for name, _d in report.failures])

if __name__ == '__main__':
    unittest.main()
