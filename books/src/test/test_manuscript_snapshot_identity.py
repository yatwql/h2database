#!/usr/bin/env python3
"""Snapshot identity: which book and which source tree a snapshot belongs to.

A snapshot is compared against a later build, so it has to say what it is a snapshot
*of*. These cases pin the three things that make that answerable: the identity block in
the manifest, a directory named after the book, and a diff that refuses to compare two
different subjects unless it is told to.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:manuscript", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))


class SnapshotIdentityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "snapshot")
        self.snapshots = os.path.join(self.root, "data", "snapshots")
        os.makedirs(self.snapshots, exist_ok=True)
        for patcher in (
            mock.patch.object(self.mod, "SNAPSHOT_ROOT", self.snapshots),
            mock.patch.object(self.mod._config, "BOOK_ROOT", self.root),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _import(self, label, date, body="# 第1章\n\n正文。\n"):
        source = os.path.join(self.tmp.name, f"src-{label}", "manuscript")
        os.makedirs(source, exist_ok=True)
        with open(os.path.join(source, "ch1.md"), "w", encoding="utf-8") as fh:
            fh.write(body)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.import_snapshot(source, label, date), 0)
        return self.mod.snapshot_dir(date, label)

    def test_the_manifest_records_book_source_and_tool(self):
        target = self._import("june", "2026-06-11")
        with open(os.path.join(target, "manifest.json"), encoding="utf-8") as fh:
            identity = json.load(fh)["identity"]
        self.assertEqual(identity["book"]["slug"], self.mod._config.current().merged_name)
        self.assertTrue(identity["book"]["version"])
        self.assertTrue(identity["source"]["roots"])
        self.assertTrue(identity["source"]["version"])
        self.assertTrue(identity["tool"]["version"])
        self.assertEqual(len(identity["tool"]["config"]), 12)
        self.assertTrue(identity["language"])

    def test_a_snapshot_lives_under_its_book_not_next_to_other_books(self):
        target = self._import("june", "2026-06-11")
        slug = self.mod._config.current().merged_name
        self.assertEqual(os.path.basename(os.path.dirname(target)), slug)
        self.assertEqual(os.path.basename(target), "2026-06-11-june")

    def test_list_names_the_book_and_the_source_version(self):
        self._import("june", "2026-06-11")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(self.mod.list_snapshots(), 0)
        out = buffer.getvalue()
        self.assertIn(self.mod._config.current().merged_name, out)
        self.assertIn(self.mod._config.current().versions()["source"], out)

    def _write_manifest(self, name, identity):
        path = os.path.join(self.snapshots, name)
        os.makedirs(os.path.join(path, "manuscript"), exist_ok=True)
        with open(os.path.join(path, "manuscript", "ch1.md"), "w", encoding="utf-8") as fh:
            fh.write("# 第1章\n")
        with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "label": name,
                    "files": {"ch1.md": {"bytes": 6, "lines": 1, "sha256": "a"}},
                    "totals": {"files": 1, "bytes": 6, "lines": 1},
                    "identity": identity,
                },
                fh,
            )

    def test_diff_refuses_two_different_books(self):
        self._write_manifest("a", {"book": {"slug": "book-a"}, "source": {"version": "1"}})
        self._write_manifest("b", {"book": {"slug": "book-b"}, "source": {"version": "1"}})
        errors = io.StringIO()
        with redirect_stderr(errors):
            self.assertEqual(self.mod.diff("a", "b"), 2)
        self.assertIn("different book or source tree", errors.getvalue())
        self.assertIn("--cross", errors.getvalue())

    def test_cross_allows_the_comparison_but_says_it_is_not_a_regression(self):
        self._write_manifest("a", {"book": {"slug": "book-a"}, "source": {"version": "1"}})
        self._write_manifest("b", {"book": {"slug": "book-b"}, "source": {"version": "1"}})
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(self.mod.diff("a", "b", cross=True), 0)
        self.assertIn("not a regression", buffer.getvalue())

    def test_a_snapshot_without_identity_is_not_silently_compared(self):
        self._write_manifest("a", {})
        self._write_manifest("b", {"book": {"slug": "book-b"}, "source": {"version": "1"}})
        errors = io.StringIO()
        with redirect_stderr(errors):
            self.assertEqual(self.mod.diff("a", "b"), 2)
        self.assertIn("identity block", errors.getvalue())

    def test_diff_of_the_same_subject_reports_per_file_changes(self):
        identity = {"book": {"slug": "same"}, "source": {"version": "1"}}
        self._write_manifest("a", identity)
        self._write_manifest("b", identity)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(self.mod.diff("a", "b"), 0)
        self.assertIn("added 0, removed 0, changed 0", buffer.getvalue())

    def test_listing_skips_files_and_nested_non_directories(self):
        with open(os.path.join(self.snapshots, "stray.txt"), "w", encoding="utf-8") as fh:
            fh.write("not a snapshot")
        book = os.path.join(self.snapshots, "book-a")
        os.makedirs(book)
        with open(os.path.join(book, "notes.txt"), "w", encoding="utf-8") as fh:
            fh.write("nor this")
        self._write_manifest("book-b/2026-01-01-x", {})
        found = self.mod.snapshot_paths()
        self.assertNotIn("stray.txt", found)
        self.assertNotIn("book-a/notes.txt", found)
        self.assertIn("book-b/2026-01-01-x", found)

    def test_diff_reports_added_removed_and_changed_files(self):
        identity = {"book": {"slug": "same"}, "source": {"version": "1"}}
        self._write_manifest("a", identity)
        self._write_manifest("b", identity)
        path_b = os.path.join(self.snapshots, "b", "manifest.json")
        with open(path_b, encoding="utf-8") as fh:
            manifest = json.load(fh)
        manifest["files"] = {
            "ch1.md": {"bytes": 9, "lines": 2, "sha256": "b"},
            "ch2.md": {"bytes": 3, "lines": 1, "sha256": "c"},
        }
        with open(path_b, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(self.mod.diff("a", "b"), 0)
        out = buffer.getvalue()
        self.assertIn("~ ch1.md", out)
        self.assertIn("+ ch2.md", out)

        manifest["files"] = {"ch1.md": {"bytes": 6, "lines": 1, "sha256": "a"}}
        with open(path_b, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        path_a = os.path.join(self.snapshots, "a", "manifest.json")
        with open(path_a, encoding="utf-8") as fh:
            first = json.load(fh)
        first["files"]["extra.md"] = {"bytes": 1, "lines": 1, "sha256": "d"}
        with open(path_a, "w", encoding="utf-8") as fh:
            json.dump(first, fh)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(self.mod.diff("a", "b"), 0)
        self.assertIn("- extra.md", buffer.getvalue())

    def test_diff_returns_usage_error_when_a_label_does_not_resolve(self):
        self._write_manifest("a", {"book": {"slug": "same"}, "source": {"version": "1"}})
        with redirect_stderr(io.StringIO()):
            self.assertEqual(self.mod.diff("a", "missing-label"), 2)

    def test_the_cli_dispatches_diff(self):
        identity = {"book": {"slug": "same"}, "source": {"version": "1"}}
        self._write_manifest("a", identity)
        self._write_manifest("b", identity)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.main(["diff", "a", "b"]), 0)

    def test_a_book_directory_that_cannot_be_read_is_skipped_not_fatal(self):
        os.makedirs(os.path.join(self.snapshots, "unreadable"))
        inner_listdir = os.listdir

        def block(path):
            if os.path.basename(path) == "unreadable":
                raise OSError("permission denied")
            return inner_listdir(path)

        with mock.patch("os.listdir", side_effect=block):
            found = self.mod.snapshot_paths()
        self.assertEqual(found, {})

    def _legacy(self, name, manifest=None):
        path = os.path.join(self.snapshots, name)
        os.makedirs(os.path.join(path, "manuscript"), exist_ok=True)
        with open(os.path.join(path, "manuscript", "ch1.md"), "w", encoding="utf-8") as fh:
            fh.write("# 第1章\n")
        if manifest is not None:
            with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8") as fh:
                json.dump(manifest, fh)
        return path

    def test_adopt_gives_a_legacy_snapshot_an_identity_and_moves_it_home(self):
        path = self._legacy("2026-06-11", {})
        chapter = os.path.join(path, "manuscript", "ch1.md")
        with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "files": {
                        "ch1.md": {"bytes": 6, "lines": 1, "sha256": self.mod.sha256_file(chapter)}
                    }
                },
                fh,
            )
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.adopt("2026-06-11"), 0)
        slug = self.mod._config.current().merged_name
        target = os.path.join(self.snapshots, slug, "2026-06-11")
        self.assertTrue(os.path.isdir(target))
        self.assertFalse(os.path.exists(os.path.join(self.snapshots, "2026-06-11")))
        with open(os.path.join(target, "manifest.json"), encoding="utf-8") as fh:
            identity = json.load(fh)["identity"]
        self.assertEqual(identity["book"]["slug"], slug)
        self.assertEqual(identity["adopted_from"], "2026-06-11")
        self.assertEqual(identity["adopted_as"], slug)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.verify("2026-06-11"), 0)

    def test_adopt_leaves_an_identified_snapshot_alone(self):
        self._legacy("2026-06-12", {"files": {}, "identity": {"book": {"slug": "x"}}})
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(self.mod.adopt("2026-06-12"), 0)
        self.assertIn("already carries an identity", buffer.getvalue())

    def test_adopt_refuses_a_snapshot_without_a_manifest(self):
        self._legacy("2026-06-13", None)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(self.mod.adopt("2026-06-13"), 2)

    def test_adopt_refuses_when_the_target_directory_is_taken(self):
        self._legacy("2026-06-14", {"files": {}})
        slug = self.mod._config.current().merged_name
        os.makedirs(os.path.join(self.snapshots, slug, "2026-06-14"))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(self.mod.adopt("2026-06-14"), 2)

    def test_adopt_reports_a_move_that_fails(self):
        self._legacy("2026-06-15", {"files": {}})
        with mock.patch.object(self.mod.shutil, "move", side_effect=OSError("denied")):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(self.mod.adopt("2026-06-15"), 2)

    def test_the_cli_dispatches_adopt(self):
        self._legacy("2026-06-16", {"files": {}})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.main(["adopt", "2026-06-16"]), 0)

    def test_adopt_refuses_a_label_that_resolves_to_nothing(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(self.mod.adopt("no-such-snapshot"), 2)

    def test_adopt_stays_put_when_the_snapshot_is_already_under_the_book(self):
        slug = self.mod._config.current().merged_name
        path = os.path.join(self.snapshots, slug, "2026-06-17")
        os.makedirs(os.path.join(path, "manuscript"), exist_ok=True)
        with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"files": {}}, fh)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.adopt(f"{slug}/2026-06-17"), 0)
        self.assertTrue(os.path.isdir(path))


if __name__ == "__main__":
    unittest.main()
