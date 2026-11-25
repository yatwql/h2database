#!/usr/bin/env python3
"""Tests for the markdown parsers the audits rely on.

Fixtures are inline strings written to a temporary file so the tests never
depend on the current manuscript contents.
"""

import importlib
import unittest

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

_audit_captions = importlib.import_module('captions')


class TestCaptionClassifier(unittest.TestCase):
    threshold = _audit_captions.thresholds()['normal']

    def classify(self, title: str) -> str | None:
        kind, _hint = _audit_captions._classify(title, self.threshold)
        return kind

    def test_verb_leading_caption_passes(self):
        self.assertIsNone(self.classify('展示 B-Tree 的页面分裂与根节点替换'))

    def test_short_caption_flagged(self):
        # Length is checked before the verb gate, so a 4-char noun phrase
        # reports TOO_SHORT rather than NO_VERB.
        self.assertEqual(self.classify('页面分裂'), 'TOO_SHORT')

    def test_bare_noun_has_no_verb(self):
        self.assertEqual(self.classify('MVStore 架构'), 'NO_VERB')

    def test_vague_suffix_flagged(self):
        # Trailing vague noun with a <=4-char prefix is flagged as VAGUE.
        self.assertEqual(self.classify('页面分裂过程'), 'VAGUE')

    def test_qualified_suffix_passes(self):
        self.assertIsNone(self.classify('展示 MVStore 四层架构与写入路径对比'))

    def test_fence_detection(self):
        lines = ['正文', '```text', '**图 1-1: 代码块内不算**:', '```', '结尾']
        flags = _audit_captions._strip_fences(lines)
        self.assertEqual(len(flags), len(lines))
        self.assertTrue(flags[2], 'caption inside a fence must be skipped')
        self.assertFalse(flags[0])

if __name__ == '__main__':
    unittest.main()
