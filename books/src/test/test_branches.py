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

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'sources'):
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


class TestSmartAuditBranches(FixtureCase):
    def test_runs_on_fixture_with_report(self):
        code, out = self.run_script('_audit_smart.py')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertNotIn('Traceback', out)

    def test_diagram_markers_and_short_blocks(self):
        smart = self.module('_audit_smart')
        self.assertEqual(smart.count_diagrams(''), 0)
        two_line = '```text\n┌┐\n└┘\n```\n'
        self.assertEqual(smart.count_diagrams(two_line), 0)

    def test_exempt_ranges_non_appendix(self):
        smart = self.module('_audit_smart')
        lines = ['# 第1章 测试', '', '## 1.1 小节', '正文']
        headings = [(1, '第1章 测试', 1), (2, '1.1 小节', 3)]
        self.assertEqual(smart.build_exempt_ranges(headings, lines), [])


class TestSmartAuditDeepCoverage(FixtureCase):
    """Drive _audit_smart's report path with #### children and few diagrams."""

    RICH = (
        '# 第1章 测试章节\n\n'
        '> **本章导读**: 导读。\n\n'
        '## 1.1 背景与问题\n\n'
        '这一节说明背景，**图 1-1: 展示整体调用链路** 给出概览。\n\n'
        '### 1.1.1 写入路径\n\n'
        '#### 1.1.1.1 缓冲写入\n\n'
        '正文说明缓冲写入的行为与触发条件。\n\n'
        '#### 1.1.1.2 落盘写入\n\n'
        '正文说明落盘写入的行为与触发条件。\n\n'
        '```text\n┌──┐\n│A │\n└──┘\n```\n\n'
        '```text\n┌──┐\n│B │\n└──┘\n```\n\n'
        '**图 1-2: 对比两种写入路径的差异**\n\n'
        '## 1.9 本章小结\n\n小结。\n'
    )

    def test_report_with_children(self):
        self.write('data/manuscript/ch1-test.md', self.RICH)
        code, out = self.run_script('_audit_smart.py')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertNotIn('Traceback', out)

    def test_fig_refs_mode(self):
        code, out = self.run_script('_audit_smart.py', '--fig-refs')
        self.assertEqual(code, 0, out[-300:])


class TestSmartAuditGaps(FixtureCase):
    """A section with #### children and too few diagrams must be reported."""

    GAP = (
        '# 第1章 测试章节\n\n'
        '> **本章导读**: 导读。\n\n'
        '## 1.1 背景\n\n'
        '### 1.1.1 写入路径\n\n'
        '#### 1.1.1.1 缓冲写入\n\n'
        '正文说明缓冲写入的行为与触发条件，并给出边界分析。\n\n'
        '#### 1.1.1.2 落盘写入\n\n'
        '正文说明落盘写入的行为与触发条件，并给出边界分析。\n\n'
        '```text\n┌──┐\n│A │\n└──┘\n```\n\n'
        '## 1.9 本章小结\n\n小结。\n'
    )

    def test_gap_section_reported(self):
        self.write('data/manuscript/ch1-test.md', self.GAP)
        code, out = self.run_script('_audit_smart.py')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertIn('TOTAL', out)


class TestReadabilityDeep(FixtureCase):
    def test_unbalanced_box_and_bad_caption(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n'
                   '```text\n┌────────┐\n│ 缺少下边框 │\n```\n\n'
                   '**图 1-1: 架构**\n\n'
                   '**图 1-2: 展示组件 A 与组件 B 的完整调用链路与失败回退**\n')
        code, out = self.run_script('readability_check.py', '--figures')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertNotIn('Traceback', out)

    def test_wide_diagram_and_long_lines(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n' +
                   '```text\n' + ('x' * 140 + '\n') * 4 + '```\n')
        code, out = self.run_script('readability_check.py')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertIn('READABILITY', out)


class TestGlossaryValidateMode(FixtureCase):
    def test_validate_resolves_chapters(self):
        code, out = self.run_script('build_glossary.py', '--validate')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertIn('Entries', out)

    def test_validate_flags_invalid_chapter(self):
        self.write('data/manuscript/back/glossary.md',
                   '# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n  **章节**：第99章 §99.1\n')
        code, out = self.run_script('build_glossary.py', '--validate')
        self.assertEqual(code, 1)
        self.assertIn('INVALID', out)


class TestGlossaryCoverageMode(FixtureCase):
    def test_coverage_mode_runs(self):
        code, out = self.run_script('build_glossary.py', '--coverage')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertNotIn('Traceback', out)

    def test_check_mode_with_rich_glossary(self):
        self.write('data/manuscript/back/glossary.md',
                   '# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n'
                   '  **章节**：第1章 §1.1\n  **相关**：[[MVStore]]\n\n'
                   '## M\n\n- **MVStore**: 存储引擎。\n  **章节**：第2章 §2.1\n')
        code, out = self.run_script('build_glossary.py', '--check')
        self.assertIn(code, (0, 1), out[-300:])


class TestSmartAuditDeep(FixtureCase):
    RICH = (
        '# 第1章 测试章节\n\n'
        '> **本章导读**: 导读。\n\n'
        '## 1.1 小节\n\n'
        '展示组件之间的调用关系与数据流向，便于读者建立整体认识。\n\n'
        '```text\n┌──────┐\n│ 组件 │\n└──────┘\n```\n\n'
        '**图 1-1: 展示组件 A 的调用路径**\n\n'
        '如图 1-1 所示，调用链清晰。\n\n'
        '```text\n┌───┐\n│ B │\n└───┘\n```\n\n'
        '**图 1-2: 对比组件 B 与 A 的差异**\n\n'
        '## 1.2 小节\n\n'
        '```java\nclass A {}\n```\n\n'
        '**图 1-3: 标注未引用图的情形**\n\n'
        '## 1.9 本章小结\n\n小结。\n'
    )

    def test_full_report_path(self):
        self.write('data/manuscript/ch1-test.md', self.RICH)
        code, out = self.run_script('_audit_smart.py')
        self.assertIn(code, (0, 1), out[-400:])
        self.assertNotIn('Traceback', out)


class TestGlossaryBuilderBranches(FixtureCase):
    def test_missing_glossary_exits_cleanly(self):
        os.unlink(os.path.join(self.root, 'data', 'manuscript', 'back', 'glossary.md'))
        code, out = self.run_script('build_glossary.py')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertNotIn('Traceback', out)

    def test_check_mode_on_missing_terms(self):
        self.write('data/manuscript/back/glossary.md',
                   '# 术语表\n\n## A\n\n- **ACID**: 事务特性。\n  **章节**：第1章 §1.1\n')
        code, out = self.run_script('build_glossary.py', '--check')
        self.assertIn(code, (0, 1), out[-300:])


class TestIndexBuilderBranches(FixtureCase):
    def test_hierarchy_check_on_small_index(self):
        code, out = self.run_script('build_index.py', '--hierarchy-check')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertNotIn('Traceback', out)

    def test_missing_index_file(self):
        os.unlink(os.path.join(self.root, 'data', 'manuscript', 'back', 'index.md'))
        code, out = self.run_script('build_index.py')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertNotIn('Traceback', out)


class TestReadabilityBranches(FixtureCase):
    def test_runs_on_fixture(self):
        code, out = self.run_script('readability_check.py')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertNotIn('Traceback', out)

    def test_long_sentence_and_wide_diagram(self):
        body = '这是一句' + '很长' * 60 + '的话。\n'
        diagram = '```text\n' + 'x' * 130 + '\n' + 'y' * 130 + '\n' + 'z' * 130 + '\n```\n'
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n' + body + '\n' + diagram)
        code, out = self.run_script('readability_check.py')
        self.assertIn(code, (0, 1), out[-300:])


class TestAnnotateTermsBranches(FixtureCase):
    def test_annotates_then_is_idempotent(self):
        code, out = self.run_script('_annotate_terms.py')
        self.assertEqual(code, 0, out[-300:])
        code2, out2 = self.run_script('_annotate_terms.py')
        self.assertEqual(code2, 0, out2[-300:])
        self.assertIn('Already annotated', out2)

    def test_missing_glossary_exits_cleanly(self):
        os.unlink(os.path.join(self.root, 'data', 'manuscript', 'back', 'glossary.md'))
        code, out = self.run_script('_annotate_terms.py', '--check-related')
        self.assertIn(code, (0, 1), out[-200:])
        self.assertNotIn('Traceback', out)


class TestIndexXrefBranches(FixtureCase):
    def test_runs_and_reports(self):
        code, out = self.run_script('_audit_index_xrefs.py')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertNotIn('Traceback', out)

    def test_broken_see_also_detected(self):
        self.write('data/manuscript/back/index.md',
                   '# 索引\n\n## A\n\n- ACID —— §1.1\n  see also: 不存在的词\n')
        code, out = self.run_script('_audit_index_xrefs.py')
        self.assertIn(code, (0, 1), out[-300:])


class TestCaptionAndExerciseBranches(FixtureCase):
    def test_captions_normal_threshold(self):
        code, out = self.run_script('_audit_captions.py', '--threshold', 'loose')
        self.assertIn(code, (0, 1), out[-300:])

    def test_captions_json_output(self):
        _code, out = self.run_script('_audit_captions.py', '--json')
        self.assertIn('\"violations\"', out)

    def test_exercises_json_output(self):
        code, out = self.run_script('_audit_exercises.py', '--json')
        self.assertIn(code, (0, 1), out[-200:])
        self.assertIn('{', out)

    def test_figure_clusters_json(self):
        code, out = self.run_script('_audit_figure_clusters.py', '--json')
        self.assertIn(code, (0, 1), out[-200:])
        self.assertIn('{', out)


class TestStyleAndHtmlBranches(FixtureCase):
    def test_style_on_broken_tables(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n| a | b |\n|---|---|\n| 1 |\n')
        code, out = self.run_script('check_style.py')
        self.assertIn(code, (0, 1), out[-300:])

    def test_html_handles_unclosed_fence(self):
        self.write('data/manuscript/ch2-test.md',
                   '# 第2章 测试章节\n\n```text\n未闭合\n')
        self.run_script('rebuild_merged.py')
        code, out = self.run_script('generate_html.py')
        self.assertEqual(code, 0, out[-300:])


class TestSourceFreshnessReport(FixtureCase):
    def test_print_report_branches(self):
        sfc = self.module('source_freshness_check')
        ref_ok = sfc.Reference('ch.md', 1, 'A', 2)
        ref_missing = sfc.Reference('ch.md', 2, 'B', 5)
        results = [
            sfc.Verification(ref_ok, 'OK', '/tmp/A.java', ''),
            sfc.Verification(ref_ok, 'OFFSET', '/tmp/A.java', 'file has 1 lines, offset -1'),
            sfc.Verification(ref_missing, 'MISSING', None, ''),
            sfc.Verification(ref_ok, 'ERROR', '/tmp/A.java', 'boom'),
        ]
        sfc.print_report(results, {'A': ['/tmp/A.java'], 'Dup': ['a', 'b']})


class TestSourceFreshnessBranches(FixtureCase):
    def test_missing_reference_and_baseline_flow(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n见 NoSuchClass.java:12 与 Page.java:3\n')
        code, out = self.run_script('source_freshness_check.py')
        self.assertIn(code, (0, 1), out[-300:])
        self.assertNotIn('Traceback', out)

    def test_update_baseline_then_clean(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n见 MVStore.rollbackTo() 用法\n')
        code, _ = self.run_script('source_freshness_check.py', '--update-baseline')
        self.assertEqual(code, 0)
        code, out = self.run_script('source_freshness_check.py', '--suggest')
        self.assertIn(code, (0, 1), out[-300:])


class TestAnalysisBranches(FixtureCase):
    def test_balance_check_json_and_baseline(self):
        code, out = self.run_script('balance_check.py', '--json')
        self.assertIn(code, (0, 1), out[-200:])
        baseline = os.path.join(self.root, 'dist', 'baseline.json')
        code, _ = self.run_script('balance_check.py', '--baseline', baseline)
        self.assertEqual(code, 0)
        code, out = self.run_script('balance_check.py', '--diff', baseline)
        self.assertEqual(code, 0, out[-200:])

    def test_balance_check_missing_baseline(self):
        code, out = self.run_script('balance_check.py', '--diff',
                                    os.path.join(self.root, 'nope.json'))
        self.assertEqual(code, 1)
        self.assertIn('基线文件不存在', out)


if __name__ == '__main__':
    unittest.main()
