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

class TestIndexXrefBranches(FixtureCase):
    def test_runs_and_reports(self):
        code, out = self.run_script('index_xrefs.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('issues:          0', out)
        self.assertNotIn('Traceback', out)

    def test_an_empty_target_is_skipped_and_a_prefixed_one_is_resolved(self):
        self.write('data/manuscript/back/index.md',
                   '# 索引\n\n## A\n\n- ACID —— §1.1\n'
                   '  see also:\n'
                   '  see also: 见 ACID\n'
                   '  see also: see ACID\n')
        code, out = self.run_script('index_xrefs.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('every see-also target resolves', out)

    def test_an_invalid_sub_entry_chapter_is_reported(self):
        self.write('data/manuscript/back/index.md',
                   '# 索引\n\n## A\n\n- ACID —— §1.1\n  - 原子性 —— §9.9\n')
        code, out = self.run_script('index_xrefs.py')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('references invalid', out)
        self.assertIn('issues:          1', out)

    def test_broken_see_also_detected(self):
        self.write('data/manuscript/back/index.md',
                   '# 索引\n\n## A\n\n- ACID —— §1.1\n  see also: 不存在的词\n')
        code, out = self.run_script('index_xrefs.py')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('issues:          1', out)

if __name__ == '__main__':
    unittest.main()
