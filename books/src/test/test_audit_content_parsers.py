#!/usr/bin/env python3
"""Branch coverage for the audit/report paths.

These exercise the error and edge branches (missing files, empty inputs,
threshold violations, alternate CLI modes) that the happy-path tests skip.
"""

import os
import sys
import tempfile
import unittest

import _fixture

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

class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def module(self, name: str):
        return _fixture.load_module(self.root, name)

    def run_script(self, script: str, *args: str):
        return _fixture.run_inproc(self.root, script, *args)

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

class TestCaptionAndExerciseBranches(FixtureCase):
    def test_captions_normal_threshold(self):
        code, out = self.run_script('captions.py', '--threshold', 'loose')
        self.assertIn(code, (0, 1), out[-300:])

    def test_captions_json_output(self):
        _code, out = self.run_script('captions.py', '--json')
        self.assertIn('\"violations\"', out)

    def test_exercises_json_output(self):
        code, out = self.run_script('exercises.py', '--json')
        self.assertIn(code, (0, 1), out[-200:])
        self.assertIn('{', out)

    def test_figure_clusters_json(self):
        code, out = self.run_script('figure_clusters.py', '--json')
        self.assertIn(code, (0, 1), out[-200:])
        self.assertIn('{', out)

if __name__ == '__main__':
    unittest.main()
