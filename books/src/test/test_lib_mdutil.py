#!/usr/bin/env python3
"""Markdown/HTML helpers: heading parsing and plain-text extraction."""

from __future__ import annotations

import importlib
import os
import sys
import unittest

import _fixture  # noqa: F401 - installs the offline network guard

TAGS = ('layer:lib', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

class HtmlHeadingParserTest(unittest.TestCase):
    """One parser feeds the print, outline and verification steps."""

    def setUp(self):
        self.mdutil = importlib.import_module('lib._mdutil')

    def test_parses_levels_ids_and_plain_text(self):
        found = self.mdutil.html_headings(
            '<h1 id="a">A <code>x</code></h1><h4 id="b">B</h4>')
        self.assertEqual([(h['index'], h['level'], h['id'], h['text']) for h in found],
                         [(0, 1, 'a', 'A x'), (1, 4, 'b', 'B')])

    def test_ignores_headings_without_an_id(self):
        self.assertEqual(self.mdutil.html_headings('<h2>no id</h2>'), [])

    def test_drops_zero_width_space(self):
        found = self.mdutil.html_headings('<h2 id="z">第1章\u200b标题</h2>')
        self.assertEqual(found[0]['text'], '第1章标题')

if __name__ == '__main__':
    unittest.main()
