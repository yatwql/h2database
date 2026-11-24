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

class FigureShapeTest(unittest.TestCase):
    """The caption shape lives here, so every audit reads the same one."""

    def setUp(self):
        self.mdutil = importlib.import_module('lib._mdutil')

    def test_a_numeric_caption_parses(self):
        self.assertEqual(self.mdutil.figure_caption('**图 7-1: 执行计划**'),
                         ('7-1', '执行计划'))

    def test_an_appendix_caption_parses(self):
        self.assertEqual(self.mdutil.figure_caption('**图 A-3a: 附录图**'),
                         ('A-3a', '附录图'))

    def test_trailing_blanks_are_tolerated(self):
        self.assertEqual(self.mdutil.figure_caption('**图 1-2: x**   '), ('1-2', 'x'))

    def test_a_body_line_is_not_a_caption(self):
        self.assertIsNone(self.mdutil.figure_caption('如图 7-1 所示，执行计划分三段。'))

    def test_the_prefix_matcher_accepts_a_caption_only(self):
        self.assertTrue(self.mdutil.FIGURE_PREFIX_RE.match('**图 9-4: 锁等待**'))
        self.assertFalse(self.mdutil.FIGURE_PREFIX_RE.match('**图 无编号**'))


class ShapingSamplesTest(unittest.TestCase):
    """Generated inputs: the shapes are pinned over a range, not one example."""

    def setUp(self):
        self.mdutil = importlib.import_module('lib._mdutil')

    def test_code_spans_and_links_survive_spacing(self):
        text = '用`MVStore.open()`打开，详见[图 1-1](ch1.md)。'
        spaced = self.mdutil.space_cjk_latin(text)
        self.assertIn('`MVStore.open()`', spaced)
        self.assertIn('[图 1-1](ch1.md)', spaced)

    def test_a_latin_only_line_is_untouched(self):
        self.assertEqual(self.mdutil.space_cjk_latin('plain ascii text'), 'plain ascii text')

    def test_slugify_is_stable_and_lowercases(self):
        for title in (f'第{n}章 主题 {n}' for n in range(1, 21)):
            slug = self.mdutil.slugify(title)
            self.assertEqual(slug, self.mdutil.slugify(title))
            self.assertEqual(slug, slug.lower())
            self.assertNotIn(' ', slug)

    def test_every_generated_caption_round_trips(self):
        for chapter in range(1, 13):
            for index in range(1, 6):
                line = f'**图 {chapter}-{index}: 展示第{index}张图**'
                self.assertEqual(self.mdutil.figure_caption(line),
                                 (f'{chapter}-{index}', f'展示第{index}张图'))


if __name__ == '__main__':
    unittest.main()
