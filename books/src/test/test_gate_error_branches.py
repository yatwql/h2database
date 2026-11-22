#!/usr/bin/env python3
"""Error and edge branches of the volume, settings and version gates.

Happy paths live with their own suites; this file drives the branches a healthy
book never reaches — a shrunk manuscript, a dirty working tree, an unknown
provider, a cover that disagrees with the config.
"""

from __future__ import annotations

import importlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:infra', 'tier:fast')

_fixture.ensure_tools_path()


class VolumeGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.gate = _fixture.load_module(self.root, 'content_volume')

    def test_a_removed_file_and_a_shrunk_file_both_report(self):
        baseline = {'thresholds': {'floor_ratio': 0.95},
                    'manuscript': {'files': {
                        'gone.md': {'bytes': 100, 'lines': 10},
                        'ch1-test.md': {'bytes': 10_000, 'lines': 500}},
                        'total': {'bytes': 10_100, 'lines': 510}},
                    'delivered': {}}
        current = {'manuscript': {'files': {'ch1-test.md': {'bytes': 100, 'lines': 5}},
                                  'total': {'bytes': 100, 'lines': 5}},
                   'delivered': {}}
        problems = self.gate.compare(baseline, current)
        self.assertTrue(any('gone from the manuscript' in item for item in problems))
        self.assertTrue(any('ch1-test.md: lines' in item for item in problems))
        self.assertTrue(any('manuscript total' in item for item in problems))

    def test_delivered_artifacts_have_their_own_floors(self):
        baseline = {'thresholds': {'floor_ratio': 0.95},
                    'manuscript': {'files': {}, 'total': {}},
                    'delivered': {'pdf_pages': 100, 'epub_bytes': 10_000}}
        current = {'manuscript': {'files': {}, 'total': {}},
                   'delivered': {'pdf_pages': 10, 'epub_bytes': 100}}
        problems = self.gate.compare(baseline, current)
        self.assertTrue(any('delivered PDF' in item for item in problems))
        self.assertTrue(any('delivered EPUB' in item for item in problems))

    def test_shrink_detection_names_every_metric(self):
        baseline = {'manuscript': {'files': {'a.md': {'bytes': 10, 'lines': 10},
                                             'gone.md': {'bytes': 1, 'lines': 1}},
                                   'total': {'bytes': 11, 'lines': 11}}}
        current = {'manuscript': {'files': {'a.md': {'bytes': 5, 'lines': 5}},
                                  'total': {'bytes': 5, 'lines': 5}}}
        drops = self.gate.shrunk(baseline, current)
        self.assertTrue(any('gone' in item for item in drops))
        self.assertTrue(any('total: lines' in item for item in drops))

    def test_update_refuses_a_dirty_working_tree(self):
        with mock.patch.object(self.gate, 'provenance',
                               return_value={'dirty': 'M ch1.md', 'author': 'me'}):
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(self.gate.update_baseline({}), 1)
        self.assertIn('拒绝记账', err.getvalue())

    def test_update_refuses_without_a_reviewer(self):
        with mock.patch.object(self.gate, 'provenance',
                               return_value={'dirty': '', 'author': ''}):
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(self.gate.update_baseline({}), 1)
        self.assertIn('没有评审人', err.getvalue())

    def test_update_refuses_a_shrink_unless_accepted(self):
        current = {'manuscript': {'files': {}, 'total': {}}, 'delivered': {}}
        with mock.patch.object(self.gate, 'provenance',
                               return_value={'dirty': '', 'author': 'me'}), \
                mock.patch.object(self.gate, 'load_baseline',
                                  return_value={'manuscript': {'files': {},
                                                               'total': {'lines': 999}}}), \
                mock.patch.object(self.gate, 'shrunk', return_value=['total: lines']):
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(self.gate.update_baseline(current), 1)
        self.assertIn('拒绝降低基线', err.getvalue())

    def test_snapshot_lookup_rejects_an_ambiguous_label(self):
        folder = os.path.join(self.root, 'data', 'baselines')
        os.makedirs(folder, exist_ok=True)
        for name in ('snapshot-1-june.json', 'snapshot-2-june.json'):
            with open(os.path.join(folder, name), 'w', encoding='utf-8') as fh:
                json.dump({'files': {}}, fh)
        self.assertIsNone(self.gate.from_snapshot('june'))

    def test_snapshot_lookup_builds_a_baseline(self):
        folder = os.path.join(self.root, 'data', 'baselines')
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, 'snapshot-x.json'), 'w', encoding='utf-8') as fh:
            json.dump({'files': {'a.md': {'bytes': 10, 'lines': 2}}}, fh)
        payload = self.gate.from_snapshot('x')
        self.assertEqual(payload['manuscript']['total'], {'bytes': 10, 'lines': 2})
        self.assertEqual(payload['source']['snapshot'], 'x')

    def test_the_cli_explains_a_missing_baseline(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.gate.main([])
        self.assertEqual(code, 0)
        self.assertIn('尚未建立', buffer.getvalue())


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.settings = _fixture.load_module(self.root, 'settings')

    def test_a_missing_key_is_appended_rather_than_fatal(self):
        path = os.path.join(self.tmp.name, 'conf.toml')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('[book]\ntitle = "x"\n')
        self.settings._write_toml_literal(path, 'llm', 'ingest_prose', 'true')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        self.assertIn('[llm]', text)
        self.assertIn('ingest_prose = true', text)

    def test_an_unknown_section_is_a_key_error(self):
        path = os.path.join(self.tmp.name, 'conf.toml')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('[book]\ntitle = "x"\n')
        with self.assertRaises(KeyError):
            self.settings._write_toml_value(path, 'nope', 'x', 'y')

    def test_a_malformed_priority_reads_as_the_default(self):
        self.assertEqual(self.settings._priority({'priority': 'x'}), 100)
        self.assertEqual(self.settings._priority(None), 100)

    def test_moving_an_unknown_provider_is_refused(self):
        payload = {'providers': {'a': {'priority': 10}}}
        path = os.path.join(self.root, 'data', 'config', 'llm_provider.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)
        with mock.patch.object(self.settings, 'provider_json', lambda: path):
            with self.assertRaises(KeyError):
                self.settings.move_provider('zzz', 1)
            with self.assertRaises(ValueError):
                self.settings.move_provider('a', 2)

    def test_moving_a_provider_renumbers_the_order(self):
        path = os.path.join(self.root, 'data', 'config', 'llm_provider.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump({'providers': {'a': {'priority': 10}, 'b': {'priority': 20}}}, fh)
        with mock.patch.object(self.settings, 'provider_json', lambda: path), \
                mock.patch.object(self.settings, '_reload'):
            self.assertEqual(self.settings.move_provider('b', -1), 'b, a')
            with open(path, encoding='utf-8') as fh:
                stored = json.load(fh)
        self.assertEqual(stored['providers']['b']['priority'], 10)
        self.assertEqual(stored['providers']['a']['priority'], 20)

    def test_the_header_shows_a_dash_without_llm_config(self):
        llm = importlib.import_module('lib._llm')
        with mock.patch.object(llm, 'today_cost', side_effect=llm.LLMError('no config')):
            self.assertEqual(self.settings.spend_summary(), '—')


class VersionGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.gate = _fixture.load_module(self.root, 'version_consistency')

    def test_an_empty_title_is_reported(self):
        with mock.patch.object(self.gate._config, 'TITLE', ''):
            self.assertIn('title is empty', self.gate.title_problems()[0])

    def test_a_tool_document_naming_the_book_is_reported(self):
        title = self.gate._config.TITLE
        path = os.path.join(self.root, 'docs', 'managements', 'leak.md')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(f'# {title}\n')
        problems = self.gate.title_problems()
        self.assertTrue(any('book-agnostic' in item for item in problems))

    def test_the_cover_version_must_match_the_config(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'cover.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('# 书\n\n版本 v0.0\n')
        problems = self.gate.cover_problems()
        self.assertTrue(any('config says' in item for item in problems))

    def test_a_cover_without_a_version_line_is_reported(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'cover.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('# 书\n\n版本 待定\n')
        problems = self.gate.cover_problems()
        self.assertTrue(any('no "版本 vX" line' in item for item in problems))

    def test_an_unreadable_archive_yields_no_text(self):
        path = os.path.join(self.tmp.name, 'broken.epub')
        with open(path, 'wb') as fh:
            fh.write(b'not a zip')
        self.assertIsNone(self.gate.artifact_text(path))

    def test_a_cover_carrying_the_software_name_is_reported(self):
        APP_NAME = importlib.import_module('lib._version').APP_NAME
        path = os.path.join(self.root, 'data', 'manuscript', 'cover.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(f'# 书\n\n{APP_NAME}\n')
        self.assertTrue(self.gate.book_name_problems())

    def test_a_readable_zip_is_extracted(self):
        path = os.path.join(self.tmp.name, 'book.epub')
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('toc.xhtml', '<html>目录</html>')
        self.assertIn('目录', self.gate.artifact_text(path) or '')


if __name__ == '__main__':
    unittest.main()
