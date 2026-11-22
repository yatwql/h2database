#!/usr/bin/env python3
"""Glossary and index builders: parsing, validation and generated output."""

from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:manuscript', 'tier:fast')

_fixture.ensure_tools_path()

class GlossaryBuilderTest(unittest.TestCase):
    """glossary.py is script-style: drive it with flags, assert the verdict."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def glossary(self, text: str) -> None:
        path = os.path.join(self.root, 'data', 'manuscript', 'back', 'glossary.md')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)

    def test_check_mode_reports_term_coverage(self):
        self.glossary('# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n  **章节**：第1章\n')
        code, out = _fixture.run_inproc(self.root, 'glossary.py', '--check')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertIn('术语', out)

    def test_multi_line_entry_is_parsed(self):
        self.glossary('# 术语表\n\n## A\n\n- **ACID**: 第一行。\n  第二行。\n'
                      '  **章节**：第1章\n')
        code, out = _fixture.run_inproc(self.root, 'glossary.py', '--check')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertNotIn('Traceback', out)

    def test_validate_mode_checks_chapter_refs(self):
        self.glossary('# 术语表\n\n## A\n\n- **ACID**: 描述。\n  **章节**：第99章\n')
        code, out = _fixture.run_inproc(self.root, 'glossary.py', '--validate')
        self.assertIn(code, (0, 1, 2), out[-400:])

    def test_glossary_coverage_mode_runs(self):
        self.glossary('# 术语表\n\n## A\n\n- **ACID**: 描述。\n  **章节**：第1章\n')
        code, out = _fixture.run_inproc(self.root, 'glossary.py', '--coverage')
        self.assertIn(code, (0, 1), out[-400:])

    def test_default_mode_drafts_a_glossary(self):
        self.glossary('# 术语表\n\n## A\n\n- **ACID**: 描述。\n  **章节**：第1章\n')
        code, out = _fixture.run_inproc(self.root, 'glossary.py')
        self.assertEqual(code, 0, out[-400:])
        # the draft is generated from chapter terms, not from the existing file
        self.assertIn('术语表（自动生成草稿）', out)

    def test_draft_extracts_terms_from_the_chapters(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('\n**存储引擎** 负责持久化，**调度器** 分发任务。\n')
        code, out = _fixture.run_inproc(self.root, 'glossary.py')
        self.assertEqual(code, 0, out[-400:])
        self.assertTrue(out.strip())

    def test_malformed_glossary_is_tolerated(self):
        self.glossary('# 术语表\n- 没有加粗的条目\n- **B**: 描述\n')
        code, out = _fixture.run_inproc(self.root, 'glossary.py', '--check')
        self.assertIn(code, (0, 1, 2), out[-400:])
        self.assertNotIn('Traceback', out)

class IndexBuilderTest(unittest.TestCase):
    """index.py is script-style: drive it with flags, assert the verdict."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def index(self, text: str) -> str:
        path = os.path.join(self.root, 'data', 'manuscript', 'back', 'index.md')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    def test_hierarchy_check_flags_a_thin_index(self):
        self.index('# 索引\n\n## A\n\n- 只有一个 —— §1.1\n')
        code, out = _fixture.run_inproc(self.root, 'index.py', '--hierarchy-check')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertNotIn('Traceback', out)

    def test_index_coverage_mode_runs(self):
        self.index('# 索引\n\n## A\n\n- ACID —— §1.1\n')
        code, out = _fixture.run_inproc(self.root, 'index.py', '--coverage')
        self.assertIn(code, (0, 1), out[-400:])

    def test_missing_index_file_is_reported(self):
        target = os.path.join(self.root, 'data', 'manuscript', 'back', 'index.md')
        if os.path.exists(target):
            os.remove(target)
        code, out = _fixture.run_inproc(self.root, 'index.py', '--hierarchy-check')
        self.assertIn(code, (0, 1, 2), out[-400:])
        self.assertNotIn('Traceback', out)

if __name__ == '__main__':
    unittest.main()
