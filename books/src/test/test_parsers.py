#!/usr/bin/env python3
"""Tests for the markdown parsers the audits rely on.

Fixtures are inline strings written to a temporary file so the tests never
depend on the current manuscript contents.
"""
import importlib
import os
import sys
import tempfile
import unittest

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'sources'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

_annotate_terms = importlib.import_module('_annotate_terms')
_audit_captions = importlib.import_module('_audit_captions')
_audit_exercises = importlib.import_module('_audit_exercises')
_audit_index_xrefs = importlib.import_module('_audit_index_xrefs')

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


class TestCaptionClassifier(unittest.TestCase):
    threshold = _audit_captions.THRESHOLDS['normal']

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


class TestIndexParser(unittest.TestCase):
    def test_main_entries_parsed(self):
        with _TempFile(INDEX_FIXTURE) as path:
            main, _sub, _sa, sections = _audit_index_xrefs.parse_index(path)
        self.assertTrue(sections)
        joined = ' '.join(main)
        self.assertIn('acid', joined.lower())

    def test_see_also_parsed(self):
        with _TempFile(INDEX_FIXTURE) as path:
            _main, _sub, see_alsos, _sections = _audit_index_xrefs.parse_index(path)
        targets = [t for sa in see_alsos for t in sa['targets']]
        self.assertIn('MVCC', targets)


if __name__ == '__main__':
    unittest.main()
