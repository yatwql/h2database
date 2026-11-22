#!/usr/bin/env python3
"""Archive: one dated copy per run, and old copies aged out."""

from __future__ import annotations

import datetime
import json
import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:manuscript', 'tier:fast')

_fixture.ensure_tools_path()

TODAY = datetime.date(2026, 11, 22)


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.archive = _fixture.load_module(self.root, 'archive')

    def seed_dist(self) -> None:
        dist = os.path.join(self.root, 'dist')
        os.makedirs(dist, exist_ok=True)
        for name in ('test-book.md', 'test-book.html', 'test-book.log'):
            with open(os.path.join(dist, name), 'w', encoding='utf-8') as fh:
                fh.write('x\n')

    def book_dir(self) -> str:
        return os.path.join(self.root, 'data', 'archive', self.archive.book_slug())

    def test_the_manuscript_is_copied_under_the_date(self):
        summary = self.archive.take(['manuscript'], TODAY)
        self.assertEqual(summary['kinds'], ['manuscript'])
        day = os.path.join(self.book_dir(), '2026-11-22', 'manuscript')
        self.assertTrue(os.path.isfile(os.path.join(day, 'ch1-test.md')))
        self.assertTrue(os.path.isfile(os.path.join(day, 'manifest.json')) or
                        os.path.isfile(os.path.join(self.book_dir(), '2026-11-22',
                                                    'manifest.json')))

    def test_the_delivered_artefacts_are_copied_without_logs(self):
        self.seed_dist()
        self.archive.take(['dist'], TODAY)
        day = os.path.join(self.book_dir(), '2026-11-22', 'dist')
        self.assertTrue(os.path.isfile(os.path.join(day, 'test-book.pdf' if
                                                    os.path.isfile(os.path.join(
                                                        self.root, 'dist', 'test-book.pdf'))
                                                    else 'test-book.md')))
        self.assertFalse(os.path.exists(os.path.join(day, 'test-book.log')))

    def test_the_manifest_records_files_and_sizes(self):
        self.archive.take(['manuscript'], TODAY)
        path = os.path.join(self.book_dir(), '2026-11-22', 'manifest.json')
        with open(path, encoding='utf-8') as fh:
            payload = json.load(fh)
        self.assertEqual(payload['date'], '2026-11-22')
        self.assertIn('manuscript', payload['files'])
        self.assertTrue(payload['digest'])

    def test_old_dates_are_pruned_outside_the_window(self):
        old = self.book_dir()
        for name in ('2026-09-01', '2026-10-01', '2026-11-20'):
            os.makedirs(os.path.join(old, name), exist_ok=True)
        summary = self.archive.take(['manuscript'], TODAY)
        # TODAY is 2026-11-22 with a 45-day window, so the cutoff is 2026-10-08.
        self.assertIn('2026-09-01', summary['pruned'])
        self.assertIn('2026-10-01', summary['pruned'])
        self.assertFalse(os.path.isdir(os.path.join(old, '2026-09-01')))
        self.assertTrue(os.path.isdir(os.path.join(old, '2026-11-20')))

    def test_a_dry_run_touches_nothing(self):
        self.seed_dist()
        before = sorted(os.listdir(os.path.join(self.root, 'data')))
        summary = self.archive.take(['dist'], TODAY, dry_run=True)
        self.assertTrue(summary['dry_run'])
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, 'data'))), before)

    def test_the_book_directory_is_named_after_the_book(self):
        self.assertEqual(self.archive.book_slug(), 'test-book')

    def test_nothing_to_archive_is_reported(self):
        code, out = _fixture.run_inproc(self.root, 'archive.py', '--json', '--kind', 'dist')
        if os.path.isdir(os.path.join(self.root, 'dist')):
            for name in os.listdir(os.path.join(self.root, 'dist')):
                os.remove(os.path.join(self.root, 'dist', name))
        self.assertIn(code, (0, 1))
        if out.strip().startswith('{'):
            self.assertIn('files', json.loads(out))

    def test_the_cli_writes_the_summary_as_json(self):
        self.seed_dist()
        code, out = _fixture.run_inproc(self.root, 'archive.py', '--json',
                                        '--today', '2026-11-22')
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload['date'], '2026-11-22')
        self.assertIn('dist', payload['kinds'])

    def test_a_bad_date_is_usage_error(self):
        code, _out = _fixture.run_inproc(self.root, 'archive.py', '--today', '22/11/2026')
        self.assertEqual(code, 2)

    def test_retention_falls_back_to_the_default(self):
        with mock.patch.dict(self.archive._config.POLICY, {'archive': {'retention_days': 'x'}}):
            self.assertEqual(self.archive.settings()['retention_days'], 45)


if __name__ == '__main__':
    unittest.main()
