#!/usr/bin/env python3
"""The TOC page-number stamp must never damage the document it writes into.

The bug this pins down: an entry whose title closes with an inline element had its
closing tag eaten by `rstrip('</a>')` — a character set, not a suffix — which left an
unterminated `<code>` and reparented the rest of the body.
"""
from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:render', 'tier:fast')

_fixture.ensure_tools_path()

_toc = __import__('render.toc_pages', fromlist=['inject', 'apply', 'balanced'])

KEYS = [(1, '第一章 构架', '#a'), (2, '第二章 code 收尾', '#b')]


def document(entries: str) -> str:
    return ('<html><body><nav id="toc-page-nav">' + entries + '</nav>'
            '<div id="content"><p>正文</p></div></body></html>')


class InjectTest(unittest.TestCase):
    def test_a_plain_entry_gets_its_page_number(self):
        html = document('<a href="#a">第一章 构架</a>')
        updated, stamps = _toc.inject(html, KEYS, [4, None])
        self.assertEqual(stamps, 1)
        self.assertIn('第一章 构架<span style="font-size:11px', updated)
        self.assertIn('</a>', updated)

    def test_an_entry_ending_with_an_inline_element_keeps_it_intact(self):
        html = document('<a href="#b">第二章 <code>code</code> 收尾</a>')
        updated, stamps = _toc.inject(html, KEYS, [7, 9])
        self.assertEqual(stamps, 1)
        self.assertIn('</code>', updated)
        self.assertTrue(_toc.balanced(updated))
        self.assertEqual(updated.count('</a>'), updated.count('<a'))

    def test_the_page_number_is_one_based(self):
        updated, _stamps = _toc.inject(document('<a href="#a">第一章 构架</a>'), KEYS, [4])
        self.assertIn('[5]', updated)

    def test_an_unknown_title_is_left_alone(self):
        html = document('<a href="#z">别的东西</a>')
        updated, stamps = _toc.inject(html, KEYS, [1, 2])
        self.assertEqual((updated, stamps), (html, 0))

    def test_a_document_without_a_toc_nav_is_untouched(self):
        html = '<html><body><p>x</p></body></html>'
        self.assertEqual(_toc.inject(html, KEYS, [1, 2]), (html, 0))

    def test_content_must_come_out_byte_identical(self):
        html = document('<a href="#a">第一章 构架</a>')
        updated, _stamps = _toc.inject(html, KEYS, [1, None])
        self.assertEqual(_toc.content_slice(updated), _toc.content_slice(html))

    def test_an_unbalanced_document_is_refused(self):
        # a stray `<code>` outside the anchors: refuse rather than add to the damage
        html = document('<a href="#a">第一章 构架</a><code>')
        self.assertFalse(_toc.balanced(html))
        updated, stamps = _toc.inject(html, KEYS, [1, None])
        self.assertEqual((stamps, updated), (0, html))


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, 'book.html')

    def write(self, text: str) -> None:
        with open(self.path, 'w', encoding='utf-8') as handle:
            handle.write(text)

    def read(self) -> str:
        with open(self.path, encoding='utf-8') as handle:
            return handle.read()

    def test_a_sound_rewrite_is_written(self):
        self.write(document('<a href="#b">第二章 <code>code</code> 收尾</a>'))
        self.assertEqual(_toc.apply(self.path, KEYS, [7, 9]), 1)
        self.assertIn('[10]', self.read())
        self.assertTrue(_toc.balanced(self.read()))

    def test_a_missing_file_is_not_an_error(self):
        self.assertEqual(_toc.apply(os.path.join(self.tmp.name, 'nope.html'),
                                    KEYS, [1, 2]), 0)


if __name__ == '__main__':
    unittest.main()
