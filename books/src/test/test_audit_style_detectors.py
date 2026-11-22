#!/usr/bin/env python3
"""The style detectors, one row per rule: a line that must trip it, a line that must not.

The gate as a whole is covered by the end-to-end tests; this table answers a
narrower question — does each detector still fire on its trigger, and does it
stay quiet on ordinary prose?
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

TAGS = ('layer:audit', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python')
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

CLEAN = ['这一段说明存储层的写入顺序，先落盘再更新索引。']


class DetectorTableTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        with redirect_stdout(io.StringIO()):
            self.style = _fixture.load_module(self.root, 'style')

    def findings(self, detector, lines: list[str], name: str) -> int:
        self.style.chapter_stats.clear()
        detector(lines, name)
        entry = self.style.chapter_stats.get(name) or {}
        return len(entry.get('warnings') or []) + len(entry.get('infos') or [])

    def test_each_detector_fires_on_its_trigger_and_quiet_on_clean_prose(self):
        table = [
            (self.style.detect_redundant_adverbs, ['这项设计实际上是幂等的。']),
            (self.style.detect_vague_modifiers, ['这条路径非常快。']),
            (self.style.detect_long_sentences, ['字' * 220]),
            (self.style.detect_passive_abuse, ['数据被写入，锁被持有，页被刷出，索引被更新，'
                                               '事务被提交，状态被清理。']),
            (self.style.detect_excessive_de, ['的' * 30]),
        ]
        for detector, lines in table:
            with self.subTest(detector=detector.__name__):
                self.assertGreater(self.findings(detector, lines, 'trip.md'), 0,
                                   f'{detector.__name__} missed its trigger')
                self.assertEqual(self.findings(detector, CLEAN, 'clean.md'), 0,
                                 f'{detector.__name__} fired on clean prose')

    def test_fenced_code_is_never_judged(self):
        lines = ['```java', '实际上非常快' * 20, '```']
        self.assertEqual(self.findings(self.style.detect_redundant_adverbs, lines, 'f.md'), 0)

    def test_repeated_openings_are_reported(self):
        lines = ['本节说明 A。', '本节说明 B。', '本节说明 C。']
        self.assertGreater(self.findings(self.style.detect_sentence_monotony, lines, 'm.md'), 0)


if __name__ == '__main__':
    unittest.main()
