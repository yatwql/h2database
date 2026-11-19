#!/usr/bin/env python3
"""Edge inputs: empty, zero-byte, BOM, CRLF, long lines, awkward paths."""
from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

_fixture.ensure_tools_path()


class EdgeCaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def chapter(self, name: str) -> str:
        return os.path.join(self.root, 'data', 'manuscript', name)

    def write(self, name: str, text: str, *, raw: bytes | None = None) -> None:
        path = self.chapter(name)
        if raw is not None:
            with open(path, 'wb') as fh:
                fh.write(raw)
            return
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)

    def read(self, name: str) -> str:
        with open(self.chapter(name), encoding='utf-8') as fh:
            return fh.read()

    # -- content edges ---------------------------------------------------
    def test_empty_chapter_does_not_crash_the_gates(self):
        self.write('ch1-test.md', '')
        for script in ('structure.py', 'links.py', 'captions.py'):
            with self.subTest(script=script):
                code, out = _fixture.run_inproc(self.root, script)
                self.assertIn(code, (0, 1, 2), out[-300:])
                self.assertNotIn('Traceback', out)

    def test_zero_byte_chapter_is_treated_as_empty(self):
        self.write('ch1-test.md', '', raw=b'')
        code, out = _fixture.run_inproc(self.root, 'merge.py')
        self.assertIn(code, (0, 1, 2), out[-300:])

    def test_utf8_bom_is_tolerated(self):
        self.write('ch1-test.md', '', raw=b'\xef\xbb\xbf' + self.read('ch1-test.md').encode())
        code, out = _fixture.run_inproc(self.root, 'structure.py')
        self.assertIn(code, (0, 1, 2), out[-300:])
        self.assertNotIn('Traceback', out)

    def test_crlf_chapter_keeps_its_sections(self):
        text = self.read('ch2-test.md').replace('\n', '\r\n')
        self.write('ch2-test.md', '')
        with open(self.chapter('ch2-test.md'), 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
        code, out = _fixture.run_inproc(self.root, 'merge.py')
        self.assertIn(code, (0, 1, 2), out[-300:])

    def test_very_long_line_does_not_break_the_gates(self):
        self.write('ch1-test.md', self.read('ch1-test.md') + '\n' + 'x' * 10000 + '\n')
        code, out = _fixture.run_inproc(self.root, 'readability.py')
        self.assertIn(code, (0, 1, 2), out[-300:])
        self.assertNotIn('Traceback', out)

    # -- filesystem edges ------------------------------------------------
    def test_missing_state_files_exit_cleanly(self):
        for state in ('source-inventory.json', 'outline.json'):
            path = os.path.join(self.root, 'data', 'state', state)
            if os.path.exists(path):
                os.remove(path)
        code, out = _fixture.run_inproc(self.root, 'chapters.py')
        self.assertIn(code, (0, 1, 2), out[-300:])
        self.assertNotIn('Traceback', out)

    def test_book_in_a_path_with_spaces_and_cjk(self):
        nested = os.path.join(self.tmp.name, '带 空格 的 目录')
        os.makedirs(nested, exist_ok=True)
        root = _fixture.build_book(nested)
        code, out = _fixture.run_inproc(root, 'merge.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertTrue(os.path.isfile(os.path.join(root, 'dist', 'test-book.md')))

    def test_corrupt_json_state_is_reported_not_raised(self):
        path = os.path.join(self.root, 'data', 'state', 'source-inventory.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('{not json')
        code, out = _fixture.run_inproc(self.root, 'chapters.py')
        self.assertEqual(code, 2, out[-400:])
        self.assertNotIn('Traceback', out)


if __name__ == '__main__':
    unittest.main()
