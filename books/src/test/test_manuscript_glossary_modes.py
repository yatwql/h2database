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

TAGS = ('layer:manuscript', 'tier:fast')

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

class TestGlossaryValidateMode(FixtureCase):
    def test_validate_resolves_chapters(self):
        code, out = self.run_script('glossary.py', '--validate')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertIn('Entries', out)

    def test_validate_flags_invalid_chapter(self):
        self.write('data/manuscript/back/glossary.md',
                   '# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n  **章节**：第99章 §99.1\n')
        code, out = self.run_script('glossary.py', '--validate')
        self.assertEqual(code, 1)
        self.assertIn('INVALID', out)

if __name__ == '__main__':
    unittest.main()

class TestGlossaryCoverageMode(FixtureCase):
    def test_coverage_mode_runs(self):
        code, out = self.run_script('glossary.py', '--coverage')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('术语不足', out)
        self.assertNotIn('Traceback', out)

    def test_check_mode_with_rich_glossary(self):
        self.write('data/manuscript/back/glossary.md',
                   '# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n'
                   '  **章节**：第1章 §1.1\n  **相关**：[[MVStore]]\n\n'
                   '## M\n\n- **MVStore**: 存储引擎。\n  **章节**：第2章 §2.1\n')
        code, out = self.run_script('glossary.py', '--check')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('自动生成', out)

class TestGlossaryBuilderBranches(FixtureCase):
    def test_missing_glossary_exits_cleanly(self):
        os.unlink(os.path.join(self.root, 'data', 'manuscript', 'back', 'glossary.md'))
        code, out = self.run_script('glossary.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('自动生成', out)
        self.assertNotIn('Traceback', out)

    def test_check_mode_on_missing_terms(self):
        self.write('data/manuscript/back/glossary.md',
                   '# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n  **章节**：第1章 §1.1\n')
        code, out = self.run_script('glossary.py', '--check')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('自动生成', out)
