#!/usr/bin/env python3
"""Error and fallback paths of the delivery scripts.

Missing optional tools (pandoc, chromium), missing prerequisites and malformed
artifacts are the branches that never run in the happy path but do fire in real
use — and they are where a toolchain silently misbehaves instead of reporting.
"""

import os
import sys
import unittest

from _cases import Base

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


class TestExerciseEdgeCases(Base):
    def test_chapter_without_exercises(self):
        self.write('data/manuscript/ch1-test.md', '# 第1章 测试章节\n\n仅正文。\n')
        code, out = self.run_script('exercises.py')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertIn('延伸思考', out)

    def test_caption_below_minimum(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n**图 1-1: 短**\n')
        code, out = self.run_script('captions.py', '--threshold', 'strict')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('TOO_SHORT', out)

if __name__ == '__main__':
    unittest.main()
