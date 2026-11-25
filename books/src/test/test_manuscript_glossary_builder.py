#!/usr/bin/env python3
"""Unit tests for the helper functions behind the audits.

These target the pure logic (counting, parsing, clustering, PDF checks) that the
end-to-end tests exercise only indirectly.
"""

import importlib.util
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

HAS_PYPDF = importlib.util.find_spec('pypdf') is not None

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

class TestGlossaryBuilder(FixtureCase):
    def test_parse_glossary_v6(self):
        builder = self.module('glossary')
        entries = builder.parse_glossary_v6()
        self.assertIn('ACID', entries)
        self.assertEqual(entries['ACID']['chapters'], [1])
        self.assertTrue(entries['ACID']['section_refs'])

    def test_parse_glossary_skips_malformed_lines(self):
        builder = self.module('glossary')
        self.write('data/manuscript/back/glossary.md',
                   '# 术语表\n\n## A\n\n- 无加粗术语\n- **Term**: 释义\n  **章节**：第2章 §2.1\n')
        entries = builder.parse_glossary_v6()
        self.assertEqual(list(entries), ['Term'])

    def test_parse_glossary_keeps_one_entry_per_chapter(self):
        builder = self.module('glossary')
        self.write('data/manuscript/back/glossary.md',
                   '# 术语表\n\n## A\n\n- **ACID**: 事务特性。第1章 与 第1章 §1.1\n')
        entries = builder.parse_glossary_v6()
        self.assertEqual(entries['ACID']['chapters'], [1])

    def test_parse_glossary_of_a_file_without_entries(self):
        builder = self.module('glossary')
        self.write('data/manuscript/back/glossary.md', '# 术语表\n\n## A\n\n')
        self.assertEqual(builder.parse_glossary_v6(), {})


class TestGlossaryDraft(FixtureCase):
    """The generated draft: definitions, truncation, and the skip rules."""

    def test_the_definition_after_a_colon_is_carried_over(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 起草\n\n**MVStore 引擎**：嵌入式存储引擎，负责页缓存。\n')
        code, out = self.run_script('glossary.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('- **MVStore 引擎**: 嵌入式存储引擎', out)

    def test_a_long_definition_is_truncated(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 起草\n\n**MVStore 引擎**：' + '长' * 200 + '\n')
        code, out = self.run_script('glossary.py')
        self.assertEqual(code, 0, out[-300:])
        entry = next(line for line in out.splitlines()
                     if line.startswith('- **MVStore 引擎**'))
        self.assertIn('长' * 147 + '...', entry)

    def test_the_metadata_markers_are_skipped(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 起草\n\n**核心文件** 与 **延展阅读** 是元数据标记。\n')
        code, out = self.run_script('glossary.py')
        self.assertEqual(code, 0, out[-300:])
        for skipped in ('核心文件', '延展阅读'):
            self.assertNotIn(f'- **{skipped}**', out)

    def test_a_repeated_term_keeps_its_first_chapter(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 起草\n\n**MVStore 引擎** 是存储层。\n')
        self.write('data/manuscript/ch2-test.md',
                   '# 第2章 起草\n\n**MVStore 引擎** 再次出现。\n')
        code, out = self.run_script('glossary.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertEqual(out.count('- **MVStore 引擎**'), 1)
        self.assertIn('（第1章）', out)

    def test_consecutive_terms_share_one_letter_heading(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 起草\n\n'
                   '**Alpha 引擎** 与 **Aurora 模块** 都在存储层。\n')
        code, out = self.run_script('glossary.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertEqual(out.count('## A'), 1)

    def test_a_chapter_without_a_heading_contributes_no_chapter_number(self):
        self.write('data/manuscript/ch1-test.md',
                   '**Solo 模块** 出现在一个没有标题的文件里。\n')
        code, out = self.run_script('glossary.py')
        self.assertEqual(code, 0, out[-300:])
        entry = next(line for line in out.splitlines()
                     if line.startswith('- **Solo 模块**'))
        self.assertNotIn('（第', entry)

if __name__ == '__main__':
    unittest.main()
