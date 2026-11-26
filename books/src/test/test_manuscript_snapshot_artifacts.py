"""An artifact snapshot freezes built files, which are mostly binary."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

import _fixture

TAGS = ("layer:manuscript", "tier:fast")

_fixture.ensure_tools_path()

_snapshot = __import__("manuscript.snapshot", fromlist=["import_artifacts", "verify"])
import_artifacts = _snapshot.import_artifacts
verify = _snapshot.verify


class ArtifactSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "book")
        os.makedirs(os.path.join(self.root, "data", "snapshots"))
        os.makedirs(os.path.join(self.root, "data", "config"))
        self.source = os.path.join(self.tmp.name, "edition")
        os.makedirs(self.source)
        # a binary file, because that is what a PDF or an EPUB is
        with open(os.path.join(self.source, "book.pdf"), "wb") as handle:
            handle.write(b"%PDF-1.4\n\xa0\xb1\xb2 binary payload\n")
        with open(os.path.join(self.source, "book.md"), "w", encoding="utf-8") as handle:
            handle.write("# 一\n\n正文\n")
        self._env = os.environ.get("BOOK_ROOT")
        os.environ["BOOK_ROOT"] = self.root
        _snapshot.SNAPSHOT_ROOT = os.path.join(self.root, "data", "snapshots")

    def tearDown(self):
        if self._env is None:
            os.environ.pop("BOOK_ROOT", None)
        else:
            os.environ["BOOK_ROOT"] = self._env

    def test_artifacts_are_frozen_and_verified_by_hash(self):
        self.assertEqual(import_artifacts(self.source, "ref", "2026-06-15"), 0)
        manifest_path = os.path.join(_snapshot.SNAPSHOT_ROOT, "2026-06-15-ref", "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        self.assertEqual(manifest["kind"], "artifacts")
        self.assertEqual(sorted(manifest["files"]), ["book.md", "book.pdf"])
        self.assertEqual(verify("2026-06-15-ref"), 0)

    def test_a_changed_artifact_fails_verification(self):
        self.assertEqual(import_artifacts(self.source, "ref2", "2026-06-15"), 0)
        path = os.path.join(_snapshot.SNAPSHOT_ROOT, "2026-06-15-ref2", "artifacts", "book.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# 改过\n")
        self.assertEqual(verify("2026-06-15-ref2"), 1)

    def test_an_existing_artifact_snapshot_is_not_overwritten(self):
        self.assertEqual(import_artifacts(self.source, "ref3", "2026-06-15"), 0)
        self.assertEqual(import_artifacts(self.source, "ref3", "2026-06-15"), 2)

    def test_a_missing_source_is_refused(self):
        self.assertEqual(
            import_artifacts(os.path.join(self.tmp.name, "nope"), "ref4", "2026-06-15"), 2
        )

    def test_a_subdirectory_in_the_source_is_not_frozen(self):
        os.makedirs(os.path.join(self.source, "images"))
        self.assertEqual(import_artifacts(self.source, "ref5", "2026-06-15"), 0)
        with open(
            os.path.join(_snapshot.SNAPSHOT_ROOT, "2026-06-15-ref5", "manifest.json"),
            encoding="utf-8",
        ) as handle:
            manifest = json.load(handle)
        self.assertEqual(sorted(manifest["files"]), ["book.md", "book.pdf"])


if __name__ == "__main__":
    unittest.main()
