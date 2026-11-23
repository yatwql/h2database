#!/usr/bin/env python3
"""The EPUB build against a real pandoc: the only place that needs one."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest

import _fixture

TAGS = ('layer:render', 'tier:slow')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

HAS_PANDOC = bool(shutil.which('pandoc'))


class ToEpubWithPandocTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    @unittest.skipUnless(HAS_PANDOC, 'pandoc not on PATH')
    def test_the_epub_is_built_from_the_merged_manuscript(self):
        code, out = _fixture.run_inproc(self.root, 'to_epub.py')
        self.assertEqual(code, 0, out[-600:])
        produced = os.path.join(self.root, 'dist', 'test-book.epub')
        self.assertTrue(os.path.isfile(produced), out[-300:])


if __name__ == '__main__':
    unittest.main()
