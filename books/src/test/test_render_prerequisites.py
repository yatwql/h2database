#!/usr/bin/env python3
"""Error and fallback paths of the delivery scripts.

Missing optional tools (pandoc, chromium), missing prerequisites and malformed
artifacts are the branches that never run in the happy path but do fire in real
use — and they are where a toolchain silently misbehaves instead of reporting.
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

SLOW = os.environ.get('BOOK_SLOW') == '1'
HAS_PANDOC = bool(__import__('shutil').which('pandoc'))
HAS_PYPDF = importlib.util.find_spec('pypdf') is not None

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def run_script(self, script: str, *args: str, env: dict | None = None):
        if env is None:
            return _fixture.run_inproc(self.root, script, *args)
        previous = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            return _fixture.run_inproc(self.root, script, *args)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

class TestDeliveryPrerequisites(Base):
    def test_epub_without_pandoc_exits_cleanly(self):
        code, out = self.run_script('to_epub.py', env={'PATH': '/nonexistent'})
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('pandoc', out.lower())

    def test_pdf_without_html_exits_cleanly(self):
        code, out = self.run_script('pdf_from_html.py')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('cannot read', out)

    def test_print_grade_builds_from_the_html(self):
        self.run_script('merge.py')
        self.run_script('to_html.py')
        code, out = self.run_script('print_pdf.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('Print-grade PDF', out)

    def test_toc_links_without_pdf(self):
        self.run_script('merge.py')
        self.run_script('to_html.py')
        code, out = self.run_script('pdf_toc_links.py')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('PDF', out)

if __name__ == '__main__':
    unittest.main()
