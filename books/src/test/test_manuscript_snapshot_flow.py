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


if __name__ == '__main__':
    unittest.main()
