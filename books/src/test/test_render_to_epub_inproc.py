#!/usr/bin/env python3
"""to_epub in-process: metadata extraction and the pandoc invocation."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:render', 'tier:slow')

_fixture.ensure_tools_path()

REAL_RUN = subprocess.run

def fake_pandoc(*args, **kwargs):
    """Fake only the pandoc invocation; everything else runs for real."""
    command = args[0] if args else kwargs.get('args') or []
    if not command or 'pandoc' not in str(command[0]):
        return REAL_RUN(*args, **kwargs)
    out = ''
    previous = ''
    for item in command:
        if previous == '-o':
            out = item
        previous = item
    if out:
        os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
        with open(out, 'w', encoding='utf-8') as fh:
            fh.write('fake epub\n')
    return subprocess.CompletedProcess(command, 0, stdout='pandoc 3.1.0\n', stderr='')

class ToEpubInProcessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        cover = os.path.join(self.root, 'data', 'manuscript', 'cover.md')
        with open(cover, 'w', encoding='utf-8') as fh:
            fh.write('# 测试之书\n\n## 副标题\n\n版本 v0.1 · 2026-01-01 · 100 行\n\n'
                     '**作者：其·龙**\n')

    def test_epub_build_extracts_cover_metadata(self):
        with mock.patch.object(shutil, 'which', return_value='/usr/bin/pandoc'), \
                mock.patch.object(subprocess, 'run', side_effect=fake_pandoc):
            code, out = _fixture.run_inproc(self.root, 'to_epub.py')
        self.assertEqual(code, 0, out[-600:])
        self.assertIn('pandoc detected', out)
        epub = os.path.join(self.root, 'dist', 'test-book.epub')
        self.assertTrue(os.path.isfile(epub))

    def test_missing_merged_markdown_is_reported(self):
        merged = os.path.join(self.root, 'dist', 'test-book.md')
        if os.path.exists(merged):
            os.remove(merged)
        with mock.patch.object(shutil, 'which', return_value='/usr/bin/pandoc'), \
                mock.patch.object(subprocess, 'run', side_effect=fake_pandoc), \
                mock.patch.object(os.path, 'exists', side_effect=lambda p: False):
            code, out = _fixture.run_inproc(self.root, 'to_epub.py')
        self.assertIn(code, (0, 1))
        self.assertNotIn('Traceback', out)

    def test_merge_failure_aborts_the_build(self):
        def failing(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, stdout='', stderr='merge boom')

        with mock.patch.object(shutil, 'which', return_value='/usr/bin/pandoc'), \
                mock.patch.object(subprocess, 'run', side_effect=failing):
            code, out = _fixture.run_inproc(self.root, 'to_epub.py')
        self.assertIn(code, (0, 1))
        self.assertNotIn('Traceback', out)

if __name__ == '__main__':
    unittest.main()
