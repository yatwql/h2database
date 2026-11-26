#!/usr/bin/env python3
"""Small gates: log setup, health readings, plan parsing, content depth, versions."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class LogSetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        # refresh_config points the process at this book; put it back afterwards
        previous_env = os.environ.get('BOOK_ROOT')
        previous_cfg = __import__('lib._config', fromlist=['current']).current()
        self.addCleanup(lambda: __import__('lib._config', fromlist=['reset']).reset(previous_cfg))
        if previous_env is None:
            self.addCleanup(os.environ.pop, 'BOOK_ROOT', None)
        else:
            self.addCleanup(os.environ.__setitem__, 'BOOK_ROOT', previous_env)
        _fixture.refresh_config(self.root)
        self.mod = _fixture.load_module(self.root, '_log')

    def test_the_log_directory_follows_the_configured_name(self):
        path = self.mod.log_dir()
        self.assertTrue(path.startswith(os.path.abspath(self.root)), path)
        self.assertTrue(os.path.isdir(path))

    def test_an_uncreatable_log_directory_warns_and_falls_back(self):
        with mock.patch.object(self.mod.os, 'makedirs', side_effect=OSError('denied')), \
                redirect_stderr(io.StringIO()) as err:
            path = self.mod.log_dir()
        self.assertIn('cannot create log directory', err.getvalue())
        self.assertFalse(path.endswith('logs'))


class TestHealthReadingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'test_health')

    def test_a_baseline_that_cannot_be_read_reads_as_empty(self):
        baseline = os.path.join(self.root, 'data', 'baselines', 'coverage.json')
        os.makedirs(os.path.dirname(baseline), exist_ok=True)
        with open(baseline, 'w', encoding='utf-8') as fh:
            fh.write('{broken')
        self.assertEqual(self.mod.below_baseline({'files': []}), [])

    def test_coverage_data_without_files_yields_empty_lists(self):
        with mock.patch.object(self.mod, '_run', return_value=(0, '{}')):
            snapshot = self.mod.coverage_snapshot()
        self.assertEqual(snapshot['thinnest'], [])
        self.assertEqual(snapshot['branch_heavy'], [])

    def test_an_unparsable_module_is_skipped_when_measuring_length(self):
        broken = os.path.join(self.tmp.name, 'broken.py')
        with open(broken, 'w', encoding='utf-8') as fh:
            fh.write('def x(:\n')
        with mock.patch.object(self.mod, 'PY_ROOT', self.tmp.name):
            self.assertEqual(self.mod.long_functions(1), [])

    def test_an_unreadable_source_is_skipped_too(self):
        with mock.patch.object(self.mod._fsutil, 'read_text', side_effect=OSError('denied')), \
                mock.patch.object(self.mod, 'PY_ROOT', self.tmp.name):
            self.assertEqual(self.mod.long_functions(1), [])


class PlanParsingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'plan_coverage')

    def test_a_malformed_number_counts_as_zero(self):
        self.assertEqual(self.mod.as_int('nope'), 0)
        self.assertEqual(self.mod.as_int('7'), 7)

    def test_a_missing_section_reads_as_empty(self):
        self.assertEqual(self.mod.own_section('# 标题\n\n## 别的\n', '## 在办'), '')

    def test_iteration_directories_come_from_the_docs_tree(self):
        folder = os.path.join(self.root, 'docs', 'plan')
        os.makedirs(os.path.join(folder, 'alpha'), exist_ok=True)
        with open(os.path.join(folder, 'not-a-dir.md'), 'w', encoding='utf-8') as fh:
            fh.write('')
        self.assertEqual(self.mod.design_dirs(folder), ['alpha'])

    def test_an_unlistable_plan_folder_yields_nothing(self):
        with mock.patch.object(self.mod.os, 'listdir', side_effect=OSError('denied')):
            self.assertEqual(self.mod.design_dirs(os.path.join(self.root, 'docs', 'plan')), [])


class ContentDepthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'content_depth')

    def test_the_gate_runs_and_reports(self):
        code, out = _fixture.run_inproc(self.root, 'content_depth.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('内容深度', out)
        self.assertNotIn('Traceback', out)


class VersionConsistencyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'version_consistency')

    def test_a_missing_doc_header_is_reported(self):
        docs = os.path.join(self.root, 'docs', 'managements')
        os.makedirs(docs, exist_ok=True)
        with open(os.path.join(docs, 'plan.md'), 'w', encoding='utf-8') as fh:
            fh.write('# 计划\n\n没有版本头。\n')
        code, out = _fixture.run_inproc(self.root, 'version_consistency.py')
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('plan.md', out)


if __name__ == '__main__':
    unittest.main()
