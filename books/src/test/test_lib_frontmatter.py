"""The cover/body split is shared, so the renderer and the outline check agree."""
from __future__ import annotations

import unittest

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()

_fm = __import__('lib.frontmatter', fromlist=['count_headings', 'split'])
split = _fm.split
count_headings = _fm.count_headings


class SplitTest(unittest.TestCase):
    def test_front_matter_before_the_title_is_body(self):
        lines = ['# 阅读指南', '', '正文', '# 测试之书', '', '**作者：甲**', '',
                 '# 第1章 起', '', '正文']
        cover, body = split(lines, ['测试之书'])
        self.assertIn('测试之书', cover)
        self.assertIn('# 阅读指南', body)
        self.assertIn('# 第1章 起', body)

    def test_a_document_with_no_chapter_heading_is_all_body(self):
        _cover, body = split(['# 一', '', '# 二'], ['测试之书'])
        self.assertEqual(len(body), 3)

    def test_without_a_matching_title_everything_before_chapter_one_is_cover(self):
        cover, body = split(['# 别的书名', '', '# 第1章 起'], ['测试之书'])
        self.assertIn('别的书名', cover)
        self.assertEqual(body, ['# 第1章 起'])

    def test_chinese_chapter_numerals_count_as_chapters(self):
        _cover, body = split(['# 封面', '', '# 第一章 起'], ['封面'])
        self.assertIn('# 第一章 起', body)


class CountHeadingsTest(unittest.TestCase):
    def test_only_headings_within_the_depth_are_counted(self):
        lines = ['# 一', '## 二', '### 三', '#### 四', '正文']
        self.assertEqual(count_headings(lines, 2), 2)

    def test_fenced_text_is_not_a_heading(self):
        self.assertEqual(count_headings(['# 一', '```', '# 不是标题', '```'], 4), 1)


if __name__ == '__main__':
    unittest.main()
