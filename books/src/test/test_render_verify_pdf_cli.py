#!/usr/bin/env python3
"""verify_pdf's command line: the two output modes and the strict TOC switch.

The checks themselves are covered elsewhere; what was never driven is the
entry point — the JSON shape, the human summary, and the exit code each mode
returns when a check fails. A PDF built with pypdf is enough: no browser, no
pandoc, so this stays in the fast tier.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

TAGS = ('layer:render', 'tier:fast')

_fixture.ensure_tools_path()

HAS_PYPDF = importlib.util.find_spec('pypdf') is not None

HTML = ('<h1 id="a">第1章 测试章节</h1><h2 id="b">1.1 小节</h2>'
        '<nav id="toc-page-nav"><a href="#a">第1章 测试章节</a>'
        '<a href="#b">1.1 小节</a></nav>')


@unittest.skipUnless(HAS_PYPDF, 'pypdf not installed')
class VerifyPdfCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'verify_pdf')
        self.pdf = os.path.join(self.root, 'dist', 'print.pdf')
        self.html = os.path.join(self.root, 'dist', 'print.html')
        os.makedirs(os.path.dirname(self.pdf), exist_ok=True)
        with open(self.html, 'w', encoding='utf-8') as fh:
            fh.write(HTML)

    def build_pdf(self, *, pages: int = 3) -> None:
        from pypdf import PdfWriter

        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=595, height=842)
        writer.add_outline_item(title='第1章 测试章节', page_number=0)
        writer.add_outline_item(title='1.1 小节', page_number=1)
        with open(self.pdf, 'wb') as fh:
            writer.write(fh)

    def run_main(self, *args: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(['--pdf', self.pdf, '--html', self.html, *args])
        return code, buffer.getvalue()

    def test_the_json_mode_reports_every_check(self):
        self.build_pdf()
        code, out = self.run_main('--json')
        payload = json.loads(out)
        self.assertEqual(code, 0 if payload['ok'] else 1)
        self.assertIn('checks', payload)
        self.assertTrue(payload['checks'])
        self.assertTrue(all({'name', 'ok', 'detail'} <= set(item) for item in payload['checks']))

    def test_the_human_mode_states_the_verdict(self):
        self.build_pdf()
        code, out = self.run_main()
        self.assertEqual(code, 0, out[-400:])
        self.assertIn('PDF 交付校验', out)
        self.assertIn('✅', out)

    def test_requiring_toc_links_fails_without_them(self):
        self.build_pdf()
        code, out = self.run_main('--require-toc-links')
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('未通过', out)

    def test_a_missing_pdf_is_a_failure_not_a_crash(self):
        code, out = self.run_main()
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('未通过', out)
        self.assertNotIn('Traceback', out)

    def test_the_defaults_come_from_the_book_config(self):
        self.build_pdf()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([])
        self.assertEqual(code, 1, buffer.getvalue()[-400:])
        self.assertIn('PDF 交付校验', buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
