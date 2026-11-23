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
from _cases import Base, ScriptTestBase

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

class GlossaryCandidateRulesTest(unittest.TestCase):
    """One row per rule in `is_glossary_candidate`, so a rule cannot rot alone."""

    REJECTED = (
        ('ab', 'too short'),
        ('页面与索引', 'structural function word'),
        ('存储层', 'layer reference'),
        ('第三章设计', 'phase marker'),
        ('索引详解', 'heading word'),
        ('CommandContainer.run()', 'method call'),
        ('读 → 写', 'arrow operator'),
        ('A -> B', 'code operator'),
        ('核心设计：', 'trailing colon'),
        ('数据一致性与隔离级别', 'descriptive heading'),
        ('mvstore/Chunk', 'file path'),
        ('MVStore.java', 'source file name'),
        ('`MVStore`', 'code reference'),
        ('DML（数据操作语言）', 'parenthesised gloss'),
        ('a' * 36, 'too long for one term'),
        ('v1.4.197', 'version string'),
        ('Snapshot', 'short pure-English word'),
        ('每次 put() 导致页面超出容量', 'descriptive phrase'),
    )
    # `MVStore` on its own is *not* a candidate: the rule skips single English
    # words shorter than eight letters, and it is one. It is in the glossary, so
    # nothing is missed today; a bold 7-letter class name outside the glossary
    # would be. Recorded here so the trade-off is visible rather than surprising.
    ACCEPTED = ('Write Amplification', '写放大', 'B-Tree', 'PageSplit', 'MVStore 文件')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(_fixture.build_book(self.tmp.name), 'terms')

    def test_every_rejection_rule_has_a_case(self):
        for term, why in self.REJECTED:
            with self.subTest(term=term, why=why):
                self.assertFalse(self.mod.is_glossary_candidate(term), f'{why}: {term!r}')

    def test_real_terms_are_candidates(self):
        for term in self.ACCEPTED:
            with self.subTest(term=term):
                self.assertTrue(self.mod.is_glossary_candidate(term))


class TestAnnotateTermsBranches(FixtureCase):
    def test_annotates_then_is_idempotent(self):
        code, out = self.run_script('terms.py')
        self.assertEqual(code, 0, out[-300:])
        code2, out2 = self.run_script('terms.py')
        self.assertEqual(code2, 0, out2[-300:])
        self.assertIn('Already annotated', out2)

    def test_missing_glossary_exits_cleanly(self):
        os.unlink(os.path.join(self.root, 'data', 'manuscript', 'back', 'glossary.md'))
        code, out = self.run_script('terms.py', '--check-related')
        self.assertEqual(code, 1, out[-200:])
        self.assertIn('cannot read', out)
        self.assertNotIn('Traceback', out)

if __name__ == '__main__':
    unittest.main()

class TestAnnotateTermsGuideBranches(Base):
    def test_chapter_without_guide_block(self):
        self.write('data/manuscript/ch2-test.md', '# 第2章 测试章节\n\n仅正文。\n')
        code, out = self.run_script('terms.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('No guide block found', out)

class TestAnnotateTermsReports(Base):
    def test_report_missing_on_rich_chapter(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n> **本章导读**: 导读。\n\n'
                   '**Write Amplification** 与 **MVStore** 混排。\n')
        code, out = self.run_script('terms.py', '--report-missing')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('MISSING', out)

    def test_check_related_reports_dangling(self):
        self.write('data/manuscript/back/glossary.md',
                   '# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n  **章节**：第1章 §1.1\n'
                   '  **相关**：[[不存在的术语]]\n')
        code, out = self.run_script('terms.py', '--check-related')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('DANGLING', out)

class TestAnnotateTermsModes(ScriptTestBase):
    def test_default_mode_annotates_chapters(self):
        code, out = self.run_script('terms.py')
        self.assertEqual(code, 0, out)
        self.assertIn('Updated', out)

    def test_check_related_mode(self):
        code, out = self.run_script('terms.py', '--check-related')
        self.assertEqual(code, 0, out)
        self.assertIn('Dangling see-also references: 0', out)

    def test_report_missing_mode(self):
        code, out = self.run_script('terms.py', '--report-missing')
        self.assertEqual(code, 0, out)

    def test_check_mode(self):
        code, out = self.run_script('terms.py', '--check')
        self.assertEqual(code, 0, out)
        self.assertIn('No missing terms found', out)
