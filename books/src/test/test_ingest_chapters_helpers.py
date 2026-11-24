"""Chapter-rendering helpers: the small rules that decide what a rendered page says.

They are pure or near-pure, so they can be judged without the ingest pipeline: a
template that cannot be filled, a truncated package table, CJK spacing that must leave
fences and headings alone, and the cross-chapter title lookup.
"""
from __future__ import annotations

import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:ingest', 'tier:fast')

_fixture.ensure_tools_path()


class TplTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, 'chapters')

    def test_a_template_is_filled_from_the_facts(self):
        with mock.patch.object(self.chapters, '_templates',
                               return_value={'intro': '章节 {cn}: {title}'}):
            self.assertEqual(self.chapters.tpl('intro', 'fallback', cn=3, title='架构'),
                             '章节 3: 架构')

    def test_a_template_missing_a_placeholder_falls_back(self):
        with mock.patch.object(self.chapters, '_templates',
                               return_value={'intro': '章节 {cn}: {missing}'}):
            self.assertEqual(self.chapters.tpl('intro', '章节 {cn}', cn=3),
                             '章节 3')

    def test_an_unknown_key_falls_back(self):
        with mock.patch.object(self.chapters, '_templates', return_value={}):
            self.assertEqual(self.chapters.tpl('nope', '默认 {cn}', cn=2), '默认 2')


class SpaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, 'chapters')

    def test_prose_gains_the_cjk_latin_space(self):
        self.assertEqual(self.chapters._space('H2数据库'), 'H2 数据库')

    def test_a_fence_keeps_its_content_untouched(self):
        text = '```\nH2数据库\n```'
        self.assertEqual(self.chapters._space(text), text)

    def test_a_heading_line_is_left_alone(self):
        self.assertEqual(self.chapters._space('## H2数据库'), '## H2数据库')


class CrossTitleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, 'chapters')

    def test_a_known_number_returns_its_title(self):
        self.assertEqual(self.chapters._cross_title([(1, '一'), (2, '二')], 2), '二')

    def test_an_unknown_number_falls_back_to_the_first_entry(self):
        self.assertEqual(self.chapters._cross_title([(1, '一'), (2, '二')], 9), '一')


if __name__ == '__main__':
    unittest.main()
