"""The two Markdown fixes an EPUB needs, tested without running pandoc.

Both rules exist because pandoc splits chapters on what it reads as a level-one
heading; getting them wrong is silent until a chapter file is missing or a caption
becomes its own chapter.
"""
from __future__ import annotations

import unittest

import _fixture

TAGS = ('layer:render', 'tier:fast')

_fixture.ensure_tools_path()

_source = __import__('render.epub_source', fromlist=['normalise_headings', 'is_caption'])
normalise = _source.normalise_headings
is_caption = _source.is_caption


class CaptionTest(unittest.TestCase):
    def test_a_bold_caption_line_is_a_caption(self):
        self.assertTrue(is_caption('**图 11-6: MVStore 的四层结构**'))

    def test_a_numbered_figure_line_without_bold_is_a_caption(self):
        self.assertTrue(is_caption('图 3-2 — 分层调用路径'))
        self.assertTrue(is_caption('Table 4.1: 字段说明'))

    def test_prose_is_not_a_caption(self):
        self.assertFalse(is_caption('如图 3-2 所示，调用沿栈向下。'))
        self.assertFalse(is_caption('## 3.2 存储引擎'))


class NormaliseHeadingsTest(unittest.TestCase):
    def test_an_atx_heading_under_text_gets_a_blank_line(self):
        text = '- 列表项\n## 3.2 小节\n正文'
        out, fixes = normalise(text)
        self.assertEqual(out, '- 列表项\n\n## 3.2 小节\n正文')
        self.assertEqual(fixes, {'spaced': 1, 'dropped': 0})

    def test_a_heading_already_after_a_blank_line_is_untouched(self):
        text = '- 列表项\n\n## 3.2 小节'
        out, fixes = normalise(text)
        self.assertEqual(out, text)
        self.assertEqual(fixes['spaced'], 0)

    def test_a_decorative_underline_under_a_caption_is_dropped(self):
        text = '**图 11-6: 四层结构**\n=======\n正文'
        out, fixes = normalise(text)
        self.assertEqual(out, '**图 11-6: 四层结构**\n正文')
        self.assertEqual(fixes['dropped'], 1)

    def test_a_setext_heading_that_is_not_a_caption_is_kept(self):
        text = '第一章 总体架构\n=========\n正文'
        out, fixes = normalise(text)
        self.assertEqual(out, text)
        self.assertEqual(fixes['dropped'], 0)

    def test_an_underline_with_nothing_before_it_is_kept(self):
        out, fixes = normalise('=======\n正文')
        self.assertEqual(out, '=======\n正文')
        self.assertEqual(fixes['dropped'], 0)

    def test_several_fixes_are_counted(self):
        text = ('- 项\n## 一\n**图 1-1: 甲**\n===\n## 二\n**图 1-2: 乙**\n===')
        out, fixes = normalise(text)
        self.assertEqual(fixes, {'spaced': 2, 'dropped': 2})
        self.assertNotIn('===', out)

    def test_empty_text_is_returned_unchanged(self):
        self.assertEqual(normalise(''), ('', {'spaced': 0, 'dropped': 0}))

    def test_the_text_is_not_otherwise_reshaped(self):
        text = '# 一\n\n正文\n\n- 项'
        self.assertEqual(normalise(text)[0], text)


if __name__ == '__main__':
    unittest.main()
