#!/usr/bin/env python3
"""Tests for the markdown parsers the audits rely on.

Fixtures are inline strings written to a temporary file so the tests never
depend on the current manuscript contents.
"""

import importlib
import unittest

import _fixture
from _cases import TempFile

TAGS = ('layer:manuscript', 'tier:fast')

_fixture.ensure_tools_path()

_annotate_terms = importlib.import_module('terms')

GLOSSARY_FIXTURE = """# 附录 C：术语表

## A

- **ACID**: 数据库事务四大特性。
  原子性保证要么全部提交要么全部回滚。
  **章节**：第10章 §10.5
  **相关**：[[MVCC]]、[[Undo Log]]

- **Append-Only**: 仅追加写入策略，见第6章。

## B

- **B-Tree**: 平衡树索引结构。
  **章节**：第6章 §6.2
"""


class TestGlossaryParser(unittest.TestCase):
    def test_multi_line_entry_collects_chapters(self):
        with TempFile(GLOSSARY_FIXTURE) as path:
            terms = _annotate_terms.parse_glossary_terms(path)
        self.assertEqual(terms['ACID'], [10])
        self.assertEqual(terms['Append-Only'], [6])

    def test_all_terms_found(self):
        with TempFile(GLOSSARY_FIXTURE) as path:
            terms = _annotate_terms.parse_glossary_terms(path)
        self.assertEqual(sorted(terms), ['ACID', 'Append-Only', 'B-Tree'])

    def test_related_links_parsed(self):
        with TempFile(GLOSSARY_FIXTURE) as path:
            entries = _annotate_terms.parse_glossary_with_related(path)
        self.assertEqual(entries['ACID']['related'], ['MVCC', 'Undo Log'])

    def test_chapters_deduplicated(self):
        with TempFile(GLOSSARY_FIXTURE) as path:
            entries = _annotate_terms.parse_glossary_with_related(path)
        chapters = entries['ACID']['chapters']
        self.assertEqual(len(chapters), len(set(chapters)))

if __name__ == '__main__':
    unittest.main()
