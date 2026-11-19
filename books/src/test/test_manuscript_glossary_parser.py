#!/usr/bin/env python3
"""Tests for the markdown parsers the audits rely on.

Fixtures are inline strings written to a temporary file so the tests never
depend on the current manuscript contents.
"""

import importlib
import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:manuscript', 'tier:fast')

_fixture.ensure_tools_path()

_annotate_terms = importlib.import_module('terms')
_audit_captions = importlib.import_module('captions')
_audit_exercises = importlib.import_module('exercises')
_audit_index_xrefs = importlib.import_module('index_xrefs')

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

INDEX_FIXTURE = """# 索引

## A

- ACID —— §10.5
  - 与 MVCC 的关系 —— §9.6
  see also: MVCC, Undo Log

## B

- B-Tree —— §6.2
"""

CHAPTER_FIXTURE = """# 第3章 包结构与模块划分

## 3.1 包结构

正文。

## 3.9 本章小结

小结内容。

## 3.10 延伸思考

1. 练习一

## 3.11 延展阅读

- 参考
"""

class _TempFile:
    """Context manager that materialises fixture text to a temp .md file."""

    def __init__(self, text: str):
        self.text = text

    def __enter__(self) -> str:
        self._tmp = tempfile.NamedTemporaryFile(
            'w', suffix='.md', delete=False, encoding='utf-8'
        )
        self._tmp.write(self.text)
        self._tmp.close()
        return self._tmp.name

    def __exit__(self, *exc) -> None:
        os.unlink(self._tmp.name)

class TestGlossaryParser(unittest.TestCase):
    def test_multi_line_entry_collects_chapters(self):
        with _TempFile(GLOSSARY_FIXTURE) as path:
            terms = _annotate_terms.parse_glossary_terms(path)
        self.assertEqual(terms['ACID'], [10])
        self.assertEqual(terms['Append-Only'], [6])

    def test_all_terms_found(self):
        with _TempFile(GLOSSARY_FIXTURE) as path:
            terms = _annotate_terms.parse_glossary_terms(path)
        self.assertEqual(sorted(terms), ['ACID', 'Append-Only', 'B-Tree'])

    def test_related_links_parsed(self):
        with _TempFile(GLOSSARY_FIXTURE) as path:
            entries = _annotate_terms.parse_glossary_with_related(path)
        self.assertEqual(entries['ACID']['related'], ['MVCC', 'Undo Log'])

    def test_chapters_deduplicated(self):
        with _TempFile(GLOSSARY_FIXTURE) as path:
            entries = _annotate_terms.parse_glossary_with_related(path)
        chapters = entries['ACID']['chapters']
        self.assertEqual(len(chapters), len(set(chapters)))

if __name__ == '__main__':
    unittest.main()
