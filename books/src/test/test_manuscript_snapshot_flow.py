#!/usr/bin/env python3
"""Snapshot flow: import an archive, verify it, and record its volume ledger."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from unittest import mock

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

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

class SnapshotFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, 'snapshot')
        self.snapshots = os.path.join(self.tmp.name, 'snapshots')
        self.baselines = os.path.join(self.tmp.name, 'data', 'baselines')
        os.makedirs(self.snapshots)
        os.makedirs(self.baselines)
        # every path the module derives comes from BOOK_ROOT; point it at the
        # temp tree so a test can never write into the checked-out book
        self.root_patch = mock.patch.object(self.mod._config, 'BOOK_ROOT', self.tmp.name)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        snap_patch = mock.patch.object(self.mod, 'SNAPSHOT_ROOT', self.snapshots)
        snap_patch.start()
        self.addCleanup(snap_patch.stop)

    def archive(self, files: dict[str, str]) -> str:
        path = os.path.join(self.tmp.name, 'draft.zip')
        with zipfile.ZipFile(path, 'w') as bundle:
            for name, body in files.items():
                bundle.writestr(name, body)
        return path

    def test_import_extracts_manuscript_and_records_a_manifest(self):
        source = self.archive({'manuscript/ch1.md': '# 第1章\n\n正文。\n'})
        with redirect_stdout(io.StringIO()):
            code = self.mod.import_snapshot(source, 'june', '2026-06-11')
        self.assertEqual(code, 0)
        root = os.path.join(self.snapshots, '2026-06-11-june')
        self.assertTrue(os.path.isfile(os.path.join(root, 'manuscript', 'ch1.md')))
        with open(os.path.join(root, 'manifest.json'), encoding='utf-8') as fh:
            manifest = json.load(fh)
        self.assertIn('source_archive', manifest)
        self.assertIn('files', manifest)

    def test_verify_passes_for_an_untouched_snapshot(self):
        source = self.archive({'manuscript/ch1.md': '# 第1章\n'})
        with redirect_stdout(io.StringIO()):
            self.mod.import_snapshot(source, 'june', '2026-06-11')
            code = self.mod.verify('2026-06-11-june')
        self.assertEqual(code, 0)

    def test_verify_reports_a_tampered_file(self):
        source = self.archive({'manuscript/ch1.md': '# 第1章\n'})
        with redirect_stdout(io.StringIO()):
            self.mod.import_snapshot(source, 'june', '2026-06-11')
        target = os.path.join(self.snapshots, '2026-06-11-june', 'manuscript', 'ch1.md')
        with open(target, 'w', encoding='utf-8') as fh:
            fh.write('# 改过了\n')
        with redirect_stdout(io.StringIO()), mock.patch('sys.stderr', new=io.StringIO()):
            code = self.mod.verify('2026-06-11-june')
        self.assertEqual(code, 1)

    def test_baseline_writes_the_volume_ledger(self):
        source = self.archive({'manuscript/ch1.md': '# 第1章\n正文。\n'})
        with redirect_stdout(io.StringIO()):
            self.mod.import_snapshot(source, 'june', '2026-06-11')
            code = self.mod.baseline('june')
        self.assertEqual(code, 0)
        with open(os.path.join(self.baselines, 'snapshot-june.json'),
                  encoding='utf-8') as fh:
            ledger = json.load(fh)
        self.assertEqual(ledger['totals']['files'], 1)
        self.assertGreater(ledger['totals']['lines'], 0)

    def test_list_reports_the_imported_snapshots(self):
        source = self.archive({'manuscript/ch1.md': '# 第1章\n'})
        with redirect_stdout(io.StringIO()):
            self.mod.import_snapshot(source, 'june', '2026-06-11')
            code = self.mod.list_snapshots()
        self.assertEqual(code, 0)


    # -- error branches ---------------------------------------------------
    def test_a_missing_archive_is_refused(self):
        err = io.StringIO()
        with redirect_stdout(err):
            code = self.mod.import_snapshot(os.path.join(self.tmp.name, 'no.zip'),
                                            'june', '2026-06-11')
        self.assertEqual(code, 2)

    def test_an_existing_snapshot_is_not_overwritten(self):
        source = self.archive({'manuscript/ch1.md': '# 第1章\n'})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.import_snapshot(source, 'june', '2026-06-11'), 0)
            self.assertEqual(self.mod.import_snapshot(source, 'june', '2026-06-11'), 2)

    def test_an_archive_without_manuscript_members_is_refused(self):
        source = self.archive({'readme.txt': 'x'})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.import_snapshot(source, 'june', '2026-06-11'), 2)

    def test_resolve_reports_an_ambiguous_label(self):
        for name in ('2026-06-11-a-june', '2026-06-12-b-june'):
            os.makedirs(os.path.join(self.snapshots, name))
        self.assertIsNone(self.mod.resolve('june'))
        self.assertEqual(self.mod.require('june')[1], 2)

    def test_resolve_accepts_the_exact_directory_name(self):
        name = '2026-06-11-june'
        os.makedirs(os.path.join(self.snapshots, name))
        self.assertEqual(self.mod.resolve(name), os.path.join(self.snapshots, name))

    def test_verify_reports_a_missing_manifest(self):
        name = '2026-06-11-empty'
        os.makedirs(os.path.join(self.snapshots, name, 'manuscript'))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.verify(name), 2)

    def test_a_directory_can_be_promoted_to_a_snapshot(self):
        # an archived copy is already the right shape: promoting it must not need a zip
        source = os.path.join(self.tmp.name, 'archive', 'book', '2026-11-22', 'manuscript')
        os.makedirs(os.path.join(source, 'back'), exist_ok=True)
        with open(os.path.join(source, 'ch1.md'), 'w', encoding='utf-8') as fh:
            fh.write('# 第1章\n\n正文。\n')
        with open(os.path.join(source, 'back', 'glossary.md'), 'w', encoding='utf-8') as fh:
            fh.write('# 术语表\n')
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.import_snapshot(source, 'from-archive', '2026-11-22'), 0)
        target = os.path.join(self.snapshots, '2026-11-22-from-archive')
        with open(os.path.join(target, 'manifest.json'), encoding='utf-8') as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest['totals']['files'], 2)
        self.assertIn('back/glossary.md', manifest['files'])
        self.assertTrue(manifest['archive_sha256'])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.verify('2026-11-22-from-archive'), 0)

    def test_list_on_an_empty_root_says_so(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(self.mod.list_snapshots(), 0)
        self.assertIn('no snapshots', buffer.getvalue())

    def test_an_unreadable_file_hashes_to_empty(self):
        self.assertEqual(self.mod.sha256_file(os.path.join(self.tmp.name, 'nope')), '')


if __name__ == '__main__':
    unittest.main()
