#!/usr/bin/env python3
"""Doc drift: paths, script names, versions and chapter names must exist."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))


class DocDriftTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.drift = _fixture.load_module(self.root, 'doc_drift')
        self.real_root = BOOK_ROOT

    def doc(self, text: str) -> str:
        path = os.path.join(self.tmp.name, 'doc.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    # -- paths ------------------------------------------------------------
    def test_missing_path_is_reported(self):
        path = self.doc('见 `books/no-such-file.md` 一节。\n')
        findings = self.drift.check_paths([path])
        self.assertTrue(findings)
        self.assertEqual(findings[0]['kind'], 'PATH')

    def test_existing_path_is_accepted(self):
        path = self.doc('见 `books/README.md`。\n')
        self.assertEqual(self.drift.check_paths([path], os.path.dirname(BOOK_ROOT)), [])

    def test_illustrative_paths_are_skipped(self):
        path = self.doc('例如 `books/…/x.md` 或 `<name>`。\n')
        self.assertEqual(self.drift.check_paths([path]), [])

    def test_glob_paths_are_checked_by_expansion(self):
        path = self.doc('见 `books/src/python/*.py`。\n')
        self.assertEqual(self.drift.check_paths([path], os.path.dirname(BOOK_ROOT)), [])

    # -- scripts ----------------------------------------------------------
    def test_unknown_script_is_reported(self):
        path = self.doc('运行 `no_such_script.py`。\n')
        findings = self.drift.check_scripts([path])
        self.assertEqual(findings[0]['kind'], 'SCRIPT')

    def test_known_script_is_accepted(self):
        path = self.doc('运行 `make.py`。\n')
        self.assertEqual(self.drift.check_scripts([path], BOOK_ROOT), [])

    # -- versions ---------------------------------------------------------
    def test_mismatched_document_version_is_reported(self):
        path = self.doc('> 版本：v0.0\n')
        findings = self.drift.check_versions([path])
        self.assertTrue(findings)
        self.assertEqual(findings[0]['kind'], 'VERSION')

    def test_matching_version_is_accepted(self):
        version = self.drift._config.VERSION
        path = self.doc(f'> 版本：v{version}\n')
        self.assertEqual(self.drift.check_versions([path]), [])

    def test_non_header_lines_are_ignored(self):
        path = self.doc('版本号写在正文里不算标题 v0.0\n')
        self.assertEqual(self.drift.check_versions([path]), [])

    # -- chapters ---------------------------------------------------------
    def test_unknown_chapter_reference_is_reported(self):
        path = self.doc('见 `ch99-missing.md`。\n')
        findings = self.drift.check_chapters([path])
        self.assertEqual(findings[0]['kind'], 'CHAPTER')

    def test_unconfigured_chapter_is_reported(self):
        self.drift._config.MANUSCRIPT_DIR = os.path.join(self.root, 'data', 'manuscript')
        path = self.doc('见 `ch99-missing.md`。\n')
        self.assertTrue(self.drift.check_chapters([path]))

    # -- CLI --------------------------------------------------------------
    def test_json_output_reports_the_count(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.drift.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertIn('count', payload)

    def test_human_output_states_the_verdict(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.drift.main([])
        self.assertIn(code, (0, 1))
        self.assertTrue(buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
