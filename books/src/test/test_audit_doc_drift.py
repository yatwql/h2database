#!/usr/bin/env python3
"""Doc drift: paths, script names, chapter names, config keys and levels."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

class DocDriftTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.drift = _fixture.load_module(self.root, 'doc_drift')
        self.real_root = BOOK_ROOT

    def doc(self, text: str) -> str:
        path = os.path.join(self.tmp.name, 'doc.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    def management_doc(self, text: str, name: str = 'testplan.md') -> str:
        directory = os.path.join(self.tmp.name, 'docs', 'managements')
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, name)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    # -- paths ------------------------------------------------------------
    def test_missing_path_is_reported(self):
        path = self.doc('见 `books/no-such-file.md` 一节。\n')
        findings = self.drift.check_paths([path])
        self.assertTrue(findings)
        self.assertEqual(findings[0]['kind'], 'PATH')

    def test_existing_path_is_accepted(self):
        path = self.doc('见 `books/README.md`。\n')
        self.assertEqual(self.drift.check_paths([path], os.path.dirname(BOOK_ROOT)), [])

    def test_illustrative_paths_are_skipped(self):
        path = self.doc('例如 `books/…/x.md` 或 `<name>`。\n')
        self.assertEqual(self.drift.check_paths([path]), [])

    def test_glob_paths_are_checked_by_expansion(self):
        path = self.doc('见 `books/src/python/*.py`。\n')
        self.assertEqual(self.drift.check_paths([path], os.path.dirname(BOOK_ROOT)), [])

    # -- scripts ----------------------------------------------------------
    def test_unknown_script_is_reported(self):
        path = self.doc('运行 `no_such_script.py`。\n')
        findings = self.drift.check_scripts([path])
        self.assertEqual(findings[0]['kind'], 'SCRIPT')

    def test_known_script_is_accepted(self):
        path = self.doc('运行 `make.py`。\n')
        self.assertEqual(self.drift.check_scripts([path], BOOK_ROOT), [])

    # -- chapters ---------------------------------------------------------
    def test_unknown_chapter_reference_is_reported(self):
        path = self.doc('见 `ch99-missing.md`。\n')
        findings = self.drift.check_chapters([path])
        self.assertEqual(findings[0]['kind'], 'CHAPTER')

    def test_unconfigured_chapter_is_reported(self):
        self.drift._config.MANUSCRIPT_DIR = os.path.join(self.root, 'data', 'manuscript')
        path = self.doc('见 `ch99-missing.md`。\n')
        self.assertTrue(self.drift.check_chapters([path]))

    def test_a_chapter_name_outside_back_ticks_is_reported(self):
        # a directory tree names files the same way prose does
        path = self.doc('```text\n  ch99-missing.md\n```\n')
        findings = self.drift.check_chapters([path])
        self.assertEqual([f['kind'] for f in findings], ['CHAPTER'])

    # -- config -----------------------------------------------------------
    def test_chapter_table_key_outside_the_chapter_list_is_reported(self):
        with mock.patch.object(self.drift._config, 'chapter_names',
                               return_value=['ch1-test.md']), \
             mock.patch.object(self.drift._config, 'chapter_table',
                               side_effect=lambda name: {'ch9-gone.md': [1]} if name == 'packages' else {}):
            findings = self.drift.check_config()
        self.assertEqual([f['kind'] for f in findings], ['CONFIG'])
        self.assertIn('ch9-gone.md', findings[0]['detail'])

    def test_chapter_tables_matching_the_chapter_list_pass(self):
        with mock.patch.object(self.drift._config, 'chapter_names',
                               return_value=['ch1-test.md']), \
             mock.patch.object(self.drift._config, 'chapter_table',
                               side_effect=lambda name: {'ch1-test.md': [1]}):
            self.assertEqual(self.drift.check_config(), [])

    # -- levels -----------------------------------------------------------
    def test_level_inside_the_owning_table_passes(self):
        path = self.management_doc('### 2.2 各检查项及其级别\n\n'
                                   '| 类别 | 说明 | 级别 |\n| --- | --- | --- |\n'
                                   '| 章节结构 | 齐全 | P0 |\n')
        self.assertEqual(self.drift.check_levels([path]), [])

    def test_level_table_outside_the_owning_sections_is_reported(self):
        path = self.management_doc('### 2.2 各检查项及其级别\n\n'
                                   '| 类别 | 级别 |\n| --- | --- |\n'
                                   '| 章节结构 | P0 |\n\n'
                                   '## 7. 门禁等级\n\n'
                                   '| 级别 | 检查项 |\n| --- | --- |\n'
                                   '| P0 | 章节结构。 |\n')
        findings = self.drift.check_levels([path])
        self.assertEqual([f['kind'] for f in findings], ['LEVEL'])

    def test_another_document_never_declares_a_level(self):
        path = self.management_doc('| P0 | 章节结构 |\n', name='plan.md')
        self.assertEqual([f['kind'] for f in self.drift.check_levels([path])], ['LEVEL'])

    # -- management registries ---------------------------------------
    def management_dir(self, **bodies: str) -> str:
        directory = os.path.join(self.tmp.name, 'managements')
        os.makedirs(directory, exist_ok=True)
        for name, body in bodies.items():
            path = os.path.join(directory, name.replace('_', '.') + '.md')
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(body)
        return directory

    def test_a_document_missing_from_both_registries_is_reported(self):
        directory = self.management_dir(
            README='| `README.md` | 索引 |\n',
            folder='  README.md   # 索引\n',
            changelog='# 变更日志\n')
        details = [f['detail'] for f in self.drift.check_managements(directory)]
        self.assertTrue(any('changelog.md' in d for d in details))

    def test_a_row_registered_twice_is_reported(self):
        directory = self.management_dir(
            README='| `README.md` | 索引 |\n| `README.md` | 又一遍 |\n',
            folder='  README.md   # 索引\n')
        kinds = [f['kind'] for f in self.drift.check_managements(directory)]
        self.assertIn('INDEX', kinds)

    def test_a_registry_naming_a_missing_document_is_reported(self):
        directory = self.management_dir(
            README='| `README.md` | 索引 |\n| `gone.md` | 已删 |\n',
            folder='  README.md   # 索引\n')
        details = [f['detail'] for f in self.drift.check_managements(directory)]
        self.assertTrue(any('gone.md' in d for d in details))

    # -- numbering ----------------------------------------------------
    def test_a_stale_next_number_is_reported(self):
        path = self.doc('plan-5 已用。\n\n**编号源**：`plan-next = 5`\n')
        findings = self.drift.check_numbering([path])
        self.assertEqual([f['kind'] for f in findings], ['NUMBERING'])
        self.assertIn('expected 6', findings[0]['detail'])

    def test_a_matching_next_number_passes(self):
        path = self.doc('plan-3 已用。\n\n**编号源**：`plan-next = 4`\n')
        other = self.doc('rf-7 已修。\n\n**编号源**：`rf-next = 8`\n')
        self.assertEqual(self.drift.check_numbering([path, other]), [])

    # -- quoted pipelines and prefix lists ----------------------------
    def test_a_shorter_delivery_pipeline_is_reported(self):
        steps = ['to_pdf', 'pdf_toc_links', 'verify_pdf', 'to_epub', 'verify_epub']
        path = self.doc('| `deliver` | `to_pdf` + `verify_pdf` + `verify_epub` |\n')
        findings = self.drift.check_deliver([path], steps)
        self.assertEqual([f['kind'] for f in findings], ['DELIVER'])
        self.assertIn('pdf_toc_links', findings[0]['detail'])

    def test_the_declared_delivery_pipeline_passes(self):
        steps = ['to_pdf', 'verify_pdf', 'to_epub']
        path = self.doc('| `deliver` | `to_pdf` + `verify_pdf` + `to_epub` |\n')
        self.assertEqual(self.drift.check_deliver([path], steps), [])

    def test_a_subset_prefix_list_is_reported(self):
        path = self.doc('只允许 `check`、`eval` 两类前缀。\n')
        findings = self.drift.check_prefixes([path], ['check', 'eval', 'new', 'release'])
        self.assertEqual([f['kind'] for f in findings], ['PREFIX'])
        self.assertIn('new', findings[0]['detail'])

    def test_the_full_prefix_list_passes(self):
        path = self.doc('只允许 `check`、`eval` 两类前缀。\n')
        self.assertEqual(self.drift.check_prefixes([path], ['check', 'eval']), [])

    def test_the_orchestrator_is_the_source_of_both_lists(self):
        real = _fixture.load_module(BOOK_ROOT, 'doc_drift')
        self.assertIn('to_pdf', real.deliver_steps())
        self.assertIn('bookctl', real.script_prefixes())

    # -- locus ------------------------------------------------------------
    def test_a_document_without_a_locus_line_is_reported(self):
        directory = self.management_dir(README='# 索引\n', folder='# 目录\n')
        kinds = [f['kind'] for f in self.drift.check_locus(directory)]
        self.assertEqual(kinds, ['LOCUS', 'LOCUS'])

    def test_a_locus_line_in_the_header_passes(self):
        directory = self.management_dir(README='# 索引\n\n> 定位：登记职责\n')
        self.assertEqual(self.drift.check_locus(directory), [])

    def test_a_locus_line_far_down_the_file_does_not_count(self):
        directory = self.management_dir(
            README='# 索引\n' + '\n' * 20 + '> 定位：登记职责\n')
        self.assertEqual([f['kind'] for f in self.drift.check_locus(directory)],
                         ['LOCUS'])

    # -- CLI --------------------------------------------------------------
    def test_json_output_reports_the_count(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.drift.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertIn('count', payload)

    def test_human_output_states_the_verdict(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.drift.main([])
        self.assertIn(code, (0, 1))
        self.assertTrue(buffer.getvalue())

if __name__ == '__main__':
    unittest.main()
