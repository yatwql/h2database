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


class TestExerciseParser(unittest.TestCase):
    def test_slots_detected(self):
        slots = _audit_exercises.parse_chapter_slots(CHAPTER_FIXTURE.splitlines())
        chapters = [s['chapter'] for s in slots if s['chapter'] is not None]
        self.assertIn(3, chapters)

    def test_section_lines_are_one_indexed(self):
        lines = CHAPTER_FIXTURE.splitlines()
        slots = _audit_exercises.parse_chapter_slots(lines)
        slot = next(s for s in slots if s['chapter'] == 3)
        for key in ('summary_line', 'exercises_line', 'further_line'):
            if slot[key] is not None:
                self.assertGreaterEqual(slot[key], 1)
                self.assertLessEqual(slot[key], len(lines))

    def test_find_section_end_bounded(self):
        lines = CHAPTER_FIXTURE.splitlines()
        end = _audit_exercises.find_section_end(lines, 10)
        self.assertGreater(end, 10)


if __name__ == '__main__':
    unittest.main()
