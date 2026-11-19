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

class TestVerifyEpubFailures(FixtureCase):
    def test_manifest_missing_entry(self):
        verify_epub = self.module('verify_epub')
        import zipfile
        path = os.path.join(self.root, 'dist', 'broken.epub')
        opf = ('<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" '
               'version="3.0"><metadata/><manifest>'
               '<item id="x" href="missing.xhtml" media-type="application/xhtml+xml"/>'
               '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
               'properties="nav"/></manifest><spine><itemref idref="x"/></spine></package>')
        container = ('<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:'
                     'opendocument:xmlns:container" version="1.0"><rootfiles>'
                     '<rootfile full-path="EPUB/content.opf" media-type="application/'
                     'oebps-package+xml"/></rootfiles></container>')
        nav = ('<html xmlns="http://www.w3.org/1999/xhtml"><body><nav>'
               '<a href="missing.xhtml">x</a></nav></body></html>')
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('mimetype', 'application/epub+zip', zipfile.ZIP_STORED)
            zf.writestr('META-INF/container.xml', container)
            zf.writestr('EPUB/content.opf', opf)
            zf.writestr('EPUB/nav.xhtml', nav)
        report = verify_epub.verify(path)
        self.assertIn('MANIFEST', [n for n, _d in report.failures])

if __name__ == '__main__':
    unittest.main()
