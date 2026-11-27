#!/usr/bin/env python3
"""The one reader for snapshots: layout, manifest and volume facts.

These cases exist because two records of the same facts drifted apart once already: the
snapshot manifest and a per-label copy under `data/baselines`. What is tested here is that
the manifest alone answers what the content-volume gate needs, for both layouts and for
both kinds of snapshot.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:lib", "tier:fast")


class SnapshotReaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "_snapshot")
        self.snapshots = os.path.join(self.tmp.name, "snapshots")
        os.makedirs(self.snapshots)
        patcher = mock.patch.object(self.mod, "root", return_value=self.snapshots)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write(self, name, body):
        path = os.path.join(self.snapshots, name)
        os.makedirs(os.path.join(path, "manuscript"), exist_ok=True)
        if body is not None:
            with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8") as fh:
                json.dump(body, fh)
        return path

    def test_a_manifest_is_read_and_a_missing_one_is_not_an_error(self):
        self._write("with", {"files": {"a.md": {"bytes": 4, "lines": 1}}})
        self._write("without", None)
        self.assertEqual(list(self.mod.manifest("with")["files"]), ["a.md"])
        self.assertIsNone(self.mod.manifest("without"))
        self.assertIsNone(self.mod.manifest("not-there"))

    def test_volume_counts_the_manifest_and_zeroes_artifact_lines(self):
        self._write(
            "ms", {"files": {"a.md": {"bytes": 40, "lines": 3}, "b.md": {"bytes": 10, "lines": 1}}}
        )
        facts = self.mod.volume("ms")
        self.assertEqual(facts["totals"], {"files": 2, "bytes": 50, "lines": 4})
        self._write("art", {"files": {"x.pdf": {"bytes": 900}}})
        self.assertEqual(self.mod.volume("art")["totals"]["lines"], 0)
        self.assertIsNone(self.mod.volume("not-there"))

    def test_a_slug_layout_snapshot_resolves_by_its_bare_name(self):
        path = self._write("book-a/2026-01-01-x", {"files": {}})
        self.assertEqual(self.mod.resolve("2026-01-01-x"), path)
        self.assertEqual(self.mod.resolve("book-a/2026-01-01-x"), path)

    def test_an_empty_root_reads_as_no_snapshots(self):
        os.rmdir(self.snapshots)
        self.assertEqual(self.mod.paths(), {})
        self.assertIsNone(self.mod.resolve("anything"))


if __name__ == "__main__":
    unittest.main()
