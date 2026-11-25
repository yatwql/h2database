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

TAGS = ('layer:audit', 'tier:fast')

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

class TestCaptionClassifier(unittest.TestCase):
    threshold = _audit_captions.thresholds()['normal']

    def classify(self, title: str) -> str | None:
        kind, _hint = _audit_captions._classify(title, self.threshold)
        return kind

    def test_verb_leading_caption_passes(self):
        self.assertIsNone(self.classify('展示 B-Tree 的页面分裂与根节点替换'))

    def test_short_caption_flagged(self):
        # Length is checked before the verb gate, so a 4-char noun phrase
        # reports TOO_SHORT rather than NO_VERB.
        self.assertEqual(self.classify('页面分裂'), 'TOO_SHORT')

    def test_bare_noun_has_no_verb(self):
        self.assertEqual(self.classify('MVStore 架构'), 'NO_VERB')

    def test_vague_suffix_flagged(self):
        # Trailing vague noun with a <=4-char prefix is flagged as VAGUE.
        self.assertEqual(self.classify('页面分裂过程'), 'VAGUE')

    def test_qualified_suffix_passes(self):
        self.assertIsNone(self.classify('展示 MVStore 四层架构与写入路径对比'))

    def test_fence_detection(self):
        lines = ['正文', '```text', '**图 1-1: 代码块内不算**:', '```', '结尾']
        flags = _audit_captions._strip_fences(lines)
        self.assertEqual(len(flags), len(lines))
        self.assertTrue(flags[2], 'caption inside a fence must be skipped')
        self.assertFalse(flags[0])

if __name__ == '__main__':
    unittest.main()
