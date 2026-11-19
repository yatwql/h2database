#!/usr/bin/env python3
"""In-process smoke + behaviour tests for every delivery script.

Each script is executed with ``runpy`` against the fixture book, so coverage
counts the real code paths (a subprocess run would not) while staying
deterministic and offline.

Environment-dependent scripts (PDF/EPUB toolchain) run only when their
optional dependencies are importable; otherwise they are skipped by name so the
gap stays visible instead of silently passing.
"""

import importlib.util
import os
import sys
import tempfile
import unittest

import _fixture

TAGS = ('layer:render', 'tier:slow')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

SLOW = os.environ.get('BOOK_SLOW') == '1'
HAS_PYPDF = importlib.util.find_spec('pypdf') is not None
HAS_PLAYWRIGHT = importlib.util.find_spec('playwright') is not None
HAS_PANDOC = bool(__import__('shutil').which('pandoc'))

BUILD_SCRIPTS = ['cover.py', 'merge.py', 'to_html.py']

ALL_SCRIPTS = [
    'cover.py', 'merge.py', 'to_html.py',
    'pdf_toc_links.py', 'to_epub.py', 'pdf_from_html.py',
    'structure.py',
]

AUDIT_SCRIPTS = [
    'links.py',
    'diagrams.py',
    'captions.py',
    'figures.py',
    'crossrefs.py',
    'exercises.py',
    'figure_clusters.py',
    'index_xrefs.py',
    'smart.py',
    'balance.py',
    'style.py',
    'readability.py',
    'source_refs.py',
    'glossary.py',
    'index.py',
]

class ScriptTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def run_script(self, script: str, *args: str) -> tuple[int, str]:
        return _fixture.run_inproc(self.root, script, *args)

    def path(self, *parts: str) -> str:
        return os.path.join(self.root, *parts)

    def read(self, *parts: str) -> str:
        with open(self.path(*parts), encoding='utf-8') as fh:
            return fh.read()

class TestPdfToolchain(ScriptTestBase):
    """Chromium-backed pipeline: PDF render -> verify -> TOC links -> print PDF."""

    def setUp(self):
        super().setUp()
        self.run_script('merge.py')
        self.run_script('to_html.py')

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_to_pdf_then_verify(self):
        code, out = self.run_script('to_pdf.py')
        self.assertIn(code, (0, 1), out)
        self.assertNotIn('Traceback', out)
        if code == 0:
            code2, out2 = self.run_script('verify_pdf.py')
            self.assertIn(code2, (0, 1), out2)
            self.assertNotIn('Traceback', out2)

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_add_pdf_toc_links_runs(self):
        self.run_script('to_pdf.py')
        code, out = self.run_script('pdf_toc_links.py')
        self.assertIn(code, (0, 1), out)
        self.assertNotIn('Traceback', out)

    @unittest.skipUnless(SLOW and HAS_PLAYWRIGHT, 'slow suite: set BOOK_SLOW=1')
    def test_pdf_print_grade_runs(self):
        code, out = self.run_script('print_pdf.py')
        self.assertIn(code, (0, 1), out)
        self.assertNotIn('Traceback', out)

if __name__ == '__main__':
    unittest.main()
