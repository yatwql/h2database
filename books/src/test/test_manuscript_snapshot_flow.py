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

TAGS = ("layer:manuscript", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))


class SnapshotFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, "snapshot")
        self.snapshots = os.path.join(self.tmp.name, "snapshots")
        self.baselines = os.path.join(self.tmp.name, "data", "baselines")
        os.makedirs(self.snapshots)
        os.makedirs(self.baselines)
        # every path the module derives comes from BOOK_ROOT; point it at the
        # temp tree so a test can never write into the checked-out book
        self.root_patch = mock.patch.object(self.mod._config, "BOOK_ROOT", self.tmp.name)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        snap_patch = mock.patch.object(self.mod, "SNAPSHOT_ROOT", self.snapshots)
        snap_patch.start()
        self.addCleanup(snap_patch.stop)

    def archive(self, files: dict[str, str]) -> str:
        path = os.path.join(self.tmp.name, "draft.zip")
        with zipfile.ZipFile(path, "w") as bundle:
            for name, body in files.items():
                bundle.writestr(name, body)
        return path

    def test_import_extracts_manuscript_and_records_a_manifest(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n\n正文。\n"})
        with redirect_stdout(io.StringIO()):
            code = self.mod.import_snapshot(source, "june", "2026-06-11")
        self.assertEqual(code, 0)
        root = os.path.join(self.snapshots, "2026-06-11-june")
        self.assertTrue(os.path.isfile(os.path.join(root, "manuscript", "ch1.md")))
        with open(os.path.join(root, "manifest.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertIn("source_archive", manifest)
        self.assertIn("files", manifest)

    def test_verify_passes_for_an_untouched_snapshot(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n"})
        with redirect_stdout(io.StringIO()):
            self.mod.import_snapshot(source, "june", "2026-06-11")
            code = self.mod.verify("2026-06-11-june")
        self.assertEqual(code, 0)

    def test_verify_reports_a_tampered_file(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n"})
        with redirect_stdout(io.StringIO()):
            self.mod.import_snapshot(source, "june", "2026-06-11")
        target = os.path.join(self.snapshots, "2026-06-11-june", "manuscript", "ch1.md")
        with open(target, "w", encoding="utf-8") as fh:
            fh.write("# 改过了\n")
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", new=io.StringIO()):
            code = self.mod.verify("2026-06-11-june")
        self.assertEqual(code, 1)

    def test_baseline_writes_the_volume_ledger(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n正文。\n"})
        with redirect_stdout(io.StringIO()):
            self.mod.import_snapshot(source, "june", "2026-06-11")
            code = self.mod.baseline("june")
        self.assertEqual(code, 0)
        with open(os.path.join(self.baselines, "snapshot-june.json"), encoding="utf-8") as fh:
            ledger = json.load(fh)
        self.assertEqual(ledger["totals"]["files"], 1)
        self.assertGreater(ledger["totals"]["lines"], 0)

    def test_list_reports_the_imported_snapshots(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n"})
        with redirect_stdout(io.StringIO()):
            self.mod.import_snapshot(source, "june", "2026-06-11")
            code = self.mod.list_snapshots()
        self.assertEqual(code, 0)

    # -- error branches ---------------------------------------------------
    def test_a_missing_archive_is_refused(self):
        err = io.StringIO()
        with redirect_stdout(err):
            code = self.mod.import_snapshot(
                os.path.join(self.tmp.name, "no.zip"), "june", "2026-06-11"
            )
        self.assertEqual(code, 2)

    def test_an_existing_snapshot_is_not_overwritten(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n"})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.import_snapshot(source, "june", "2026-06-11"), 0)
            self.assertEqual(self.mod.import_snapshot(source, "june", "2026-06-11"), 2)

    def test_an_archive_without_manuscript_members_is_refused(self):
        source = self.archive({"readme.txt": "x"})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.import_snapshot(source, "june", "2026-06-11"), 2)

    def test_resolve_reports_an_ambiguous_label(self):
        for name in ("2026-06-11-a-june", "2026-06-12-b-june"):
            os.makedirs(os.path.join(self.snapshots, name))
        self.assertIsNone(self.mod.resolve("june"))
        self.assertEqual(self.mod.require("june")[1], 2)

    def test_resolve_accepts_the_exact_directory_name(self):
        name = "2026-06-11-june"
        os.makedirs(os.path.join(self.snapshots, name))
        self.assertEqual(self.mod.resolve(name), os.path.join(self.snapshots, name))

    def test_verify_reports_a_missing_manifest(self):
        name = "2026-06-11-empty"
        os.makedirs(os.path.join(self.snapshots, name, "manuscript"))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.verify(name), 2)

    def test_a_directory_can_be_promoted_to_a_snapshot(self):
        # an archived copy is already the right shape: promoting it must not need a zip
        source = os.path.join(self.tmp.name, "archive", "book", "2026-11-22", "manuscript")
        os.makedirs(os.path.join(source, "back"), exist_ok=True)
        with open(os.path.join(source, "ch1.md"), "w", encoding="utf-8") as fh:
            fh.write("# 第1章\n\n正文。\n")
        with open(os.path.join(source, "back", "glossary.md"), "w", encoding="utf-8") as fh:
            fh.write("# 术语表\n")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.import_snapshot(source, "from-archive", "2026-11-22"), 0)
        target = os.path.join(self.snapshots, "2026-11-22-from-archive")
        with open(os.path.join(target, "manifest.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest["totals"]["files"], 2)
        self.assertIn("back/glossary.md", manifest["files"])
        self.assertTrue(manifest["archive_sha256"])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.verify("2026-11-22-from-archive"), 0)

    def test_list_on_an_empty_root_says_so(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(self.mod.list_snapshots(), 0)
        self.assertIn("no snapshots", buffer.getvalue())

    def test_an_unreadable_file_hashes_to_empty(self):
        self.assertEqual(self.mod.sha256_file(os.path.join(self.tmp.name, "nope")), "")

    def test_the_cli_prints_help_without_a_command(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.main([]), 2)

    def test_the_cli_verify_and_baseline_run_by_label(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n\n正文。\n"})
        with redirect_stdout(io.StringIO()):
            self.mod.import_snapshot(source, "june", "2026-06-11")
            self.assertEqual(self.mod.main(["verify", "2026-06-11-june"]), 0)
            self.assertEqual(self.mod.main(["baseline", "june"]), 0)

    def test_the_cli_json_summary_names_the_command(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(["--json", "list"])
        self.assertEqual(code, 0)
        self.assertIn('"command": "list"', buffer.getvalue())

    def test_the_cli_refuses_an_unknown_label(self):
        with redirect_stdout(io.StringIO()):
            self.assertNotEqual(self.mod.main(["verify", "nope"]), 0)

    def test_baseline_refuses_a_label_that_resolves_to_nothing(self):
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(self.mod.baseline("nope"), 2)

    def test_baseline_ignores_files_that_are_not_markdown(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n正文。\n"})
        with redirect_stdout(io.StringIO()):
            self.mod.import_snapshot(source, "june", "2026-06-11")
            extra = os.path.join(self.snapshots, "2026-06-11-june", "manuscript", "notes.txt")
            with open(extra, "w", encoding="utf-8") as fh:
                fh.write("scratch\n")
            self.assertEqual(self.mod.baseline("june"), 0)
        with open(os.path.join(self.baselines, "snapshot-june.json"), encoding="utf-8") as fh:
            self.assertEqual(list(json.load(fh)["files"]), ["ch1.md"])


class SnapshotEdgeTest(unittest.TestCase):
    """The error paths: unwritable targets, foreign members, missing manifests."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, "snapshot")
        self.snapshots = os.path.join(self.tmp.name, "snapshots")
        os.makedirs(self.snapshots)
        for patcher in (
            mock.patch.object(self.mod._config, "BOOK_ROOT", self.tmp.name),
            mock.patch.object(self.mod, "SNAPSHOT_ROOT", self.snapshots),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def archive(self, files: dict[str, str], name: str = "draft.zip") -> str:
        path = os.path.join(self.tmp.name, name)
        with zipfile.ZipFile(path, "w") as bundle:
            for member, body in files.items():
                bundle.writestr(member, body)
        return path

    def test_an_unwritable_target_is_a_tool_error(self):
        with (
            mock.patch.object(self.mod.os, "makedirs", side_effect=OSError("denied")),
            mock.patch("sys.stderr", new=io.StringIO()),
            self.assertRaises(SystemExit) as raised,
        ):
            self.mod.make_dir(os.path.join(self.tmp.name, "x"))
        self.assertEqual(raised.exception.code, 2)

    def test_a_zip_member_that_is_not_markdown_is_ignored(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n", "manuscript/notes.txt": "notes\n"})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.import_snapshot(source, "june", "2026-06-11"), 0)
        root = os.path.join(self.snapshots, "2026-06-11-june", "manuscript")
        self.assertEqual(sorted(os.listdir(root)), ["ch1.md"])

    def test_a_zip_member_that_is_markdown_but_not_manuscript_is_ignored(self):
        source = self.archive(
            {"manuscript/ch1.md": "# 第1章\n", "manuscript/notes.md": "# 随手记\n"}
        )
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.import_snapshot(source, "june", "2026-06-11"), 0)
        root = os.path.join(self.snapshots, "2026-06-11-june", "manuscript")
        self.assertEqual(sorted(os.listdir(root)), ["ch1.md"])

    def test_a_directory_without_markdown_is_refused(self):
        source = os.path.join(self.tmp.name, "draft")
        os.makedirs(source)
        with open(os.path.join(source, "notes.txt"), "w", encoding="utf-8") as handle:
            handle.write("notes\n")
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(self.mod.import_snapshot(source, "june", "2026-06-11"), 2)

    def test_a_markdown_file_outside_the_manuscript_tree_is_ignored(self):
        source = os.path.join(self.tmp.name, "draft3")
        os.makedirs(source)
        with open(os.path.join(source, "ch1.md"), "w", encoding="utf-8") as handle:
            handle.write("# 第1章\n")
        with open(os.path.join(source, "README.md"), "w", encoding="utf-8") as handle:
            handle.write("# 不是正文\n")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.import_snapshot(source, "june", "2026-06-11"), 0)
        root = os.path.join(self.snapshots, "2026-06-11-june", "manuscript")
        self.assertEqual(sorted(os.listdir(root)), ["ch1.md"])

    def test_a_directory_file_that_cannot_be_copied_is_refused(self):
        source = os.path.join(self.tmp.name, "draft2")
        os.makedirs(source)
        with open(os.path.join(source, "ch1.md"), "w", encoding="utf-8") as handle:
            handle.write("# 第1章\n")
        with (
            mock.patch.object(self.mod.shutil, "copyfile", side_effect=OSError("denied")),
            redirect_stdout(io.StringIO()),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            self.assertEqual(self.mod.import_snapshot(source, "july", "2026-07-01"), 2)

    def test_a_zip_member_in_the_back_matter_keeps_its_directory(self):
        source = self.archive({"manuscript/back/index.md": "# 索引\n"})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.import_snapshot(source, "june", "2026-06-11"), 0)
        self.assertTrue(
            os.path.isfile(
                os.path.join(self.snapshots, "2026-06-11-june", "manuscript", "back", "index.md")
            )
        )

    def test_a_zip_member_that_cannot_be_extracted_is_refused(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n"})
        with (
            mock.patch.object(self.mod.shutil, "copyfileobj", side_effect=OSError("denied")),
            redirect_stdout(io.StringIO()),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            self.assertEqual(self.mod.import_snapshot(source, "june", "2026-06-11"), 2)

    def test_an_unreadable_artifact_directory_is_refused(self):
        source = os.path.join(self.tmp.name, "dist")
        os.makedirs(source)
        with (
            mock.patch.object(self.mod.os, "listdir", side_effect=OSError("denied")),
            redirect_stdout(io.StringIO()),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            self.assertEqual(self.mod.import_artifacts(source, "edition", "2026-06-11"), 2)

    def test_an_absent_snapshot_root_lists_nothing(self):
        with mock.patch.object(self.mod, "SNAPSHOT_ROOT", os.path.join(self.tmp.name, "missing")):
            self.assertEqual(self.mod.snapshots(), [])

    def test_an_unlistable_snapshot_root_lists_nothing(self):
        with (
            mock.patch.object(self.mod.os, "listdir", side_effect=OSError("denied")),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            self.assertEqual(self.mod.snapshots(), [])

    def test_a_snapshot_without_a_manifest_is_named_in_the_listing(self):
        os.makedirs(os.path.join(self.snapshots, "2026-06-11-june"))
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(self.mod.list_snapshots(), 0)
        self.assertIn("manifest missing", buffer.getvalue())

    def test_verify_reports_a_missing_snapshot_file(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n"})
        with redirect_stdout(io.StringIO()):
            self.mod.import_snapshot(source, "june", "2026-06-11")
        os.remove(os.path.join(self.snapshots, "2026-06-11-june", "manuscript", "ch1.md"))
        buffer = io.StringIO()
        with redirect_stdout(buffer), mock.patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(self.mod.verify("2026-06-11-june"), 1)
        self.assertIn("missing", buffer.getvalue())

    def test_a_baseline_needs_a_snapshot_manuscript(self):
        os.makedirs(os.path.join(self.snapshots, "2026-06-11-june"))
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(self.mod.baseline("june"), 2)

    def test_a_baseline_counts_only_markdown(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n", "manuscript/notes.txt": "notes\n"})
        os.makedirs(os.path.join(self.tmp.name, "data", "baselines"), exist_ok=True)
        with redirect_stdout(io.StringIO()):
            self.mod.import_snapshot(source, "june", "2026-06-11")
            self.assertEqual(self.mod.baseline("june"), 0)
        path = os.path.join(self.tmp.name, "data", "baselines", "snapshot-june.json")
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        self.assertEqual(list(payload["files"]), ["ch1.md"])

    def test_the_cli_imports_a_manuscript_and_artifacts(self):
        source = self.archive({"manuscript/ch1.md": "# 第1章\n"})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.main(["import", source, "june", "--date", "2026-06-11"]), 0)
        artifacts = os.path.join(self.tmp.name, "dist")
        os.makedirs(artifacts, exist_ok=True)
        with open(os.path.join(artifacts, "test-book.html"), "w", encoding="utf-8") as handle:
            handle.write("<p>正文</p>")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(
                self.mod.main(["import-artifacts", artifacts, "edition", "--date", "2026-06-12"]), 0
            )

    def test_the_tool_runs_as_a_script(self):
        code, out = _fixture.run_inproc(BOOK_ROOT, "snapshot.py", "list")
        self.assertEqual(code, 0)
        self.assertTrue(out.strip())


if __name__ == "__main__":
    unittest.main()
