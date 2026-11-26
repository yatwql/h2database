#!/usr/bin/env python3
"""Branch coverage for the audit/report paths.

These exercise the error and edge branches (missing files, empty inputs,
threshold violations, alternate CLI modes) that the happy-path tests skip.
"""

import os
import sys
import unittest

from _cases import FixtureCase

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


class TestCaptionAndExerciseBranches(FixtureCase):
    def test_captions_normal_threshold(self):
        code, out = self.run_script('captions.py', '--threshold', 'loose')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('TOTAL', out)

    def test_captions_json_output(self):
        _code, out = self.run_script('captions.py', '--json')
        self.assertIn('\"violations\"', out)

    def test_exercises_json_output(self):
        code, out = self.run_script('exercises.py', '--json')
        self.assertEqual(code, 1, out[-200:])
        self.assertIn('chapters_pass', out)
        self.assertIn('{', out)

    def test_figure_clusters_json(self):
        code, out = self.run_script('figure_clusters.py', '--json')
        self.assertEqual(code, 0, out[-200:])
        self.assertIn('unbridged', out)
        self.assertIn('{', out)

if __name__ == '__main__':
    unittest.main()
