#!/usr/bin/env python3
"""Tests for the print/delivery gates: _audit_ascii, verify_epub, verify_pdf."""

import importlib
import os
import sys
import unittest
from typing import ClassVar

TAGS = ('layer:audit', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

audit_ascii = importlib.import_module('diagrams')
verify_epub = importlib.import_module('verify_epub')
verify_pdf = importlib.import_module('verify_pdf')

class TestDisplayWidth(unittest.TestCase):
    def test_ascii_is_one_column(self):
        self.assertEqual(audit_ascii.display_width('abc'), 3)

    def test_cjk_counts_two_columns(self):
        self.assertEqual(audit_ascii.display_width('架构'), 4)

    def test_display_width_counts_cjk_as_two(self):
        self.assertEqual(audit_ascii.display_width('MV 存储'), 7)


class TestTextBlocks(unittest.TestCase):
    LINES: ClassVar[list[str]] = [
        '正文',
        '```text',
        '┌──────┐',
        '│ 架构 │',
        '└──────┘',
        '```',
        '```java',
        'class A {}',
        '```',
    ]

    def test_only_text_blocks_collected(self):
        blocks = audit_ascii.text_blocks(self.LINES)
        self.assertEqual(len(blocks), 1)
        start, block = blocks[0]
        self.assertEqual(start, 3)
        self.assertEqual(block[0], '┌──────┐')

    def test_java_block_ignored(self):
        blocks = audit_ascii.text_blocks(self.LINES)
        self.assertNotIn('class A {}', [line for _s, b in blocks for line in b])

class TestMixedBorders(unittest.TestCase):
    def test_mixed_border_styles_are_reported(self):
        block = ['┌────┐', '+----+', '│ 组件 │']
        self.assertTrue(audit_ascii._mixes_borders(block))

    def test_box_only_is_fine(self):
        block = ['┌────┐', '│ 组件 │', '└────┘']
        self.assertFalse(audit_ascii._mixes_borders(block))

    def test_ascii_only_is_fine(self):
        block = ['+----+', '| ab |', '+----+']
        self.assertFalse(audit_ascii._mixes_borders(block))

if __name__ == '__main__':
    unittest.main()
