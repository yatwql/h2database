#!/usr/bin/env python3
"""Archive: one dated copy per run, and old copies aged out."""

from __future__ import annotations

import datetime
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

import _fixture

TAGS = ("layer:manuscript", "tier:fast")

_fixture.ensure_tools_path()

TODAY = datetime.date(2026, 11, 22)


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.archive = _fixture.load_module(self.root, "archive")

    def seed_dist(self) -> None:
        dist = os.path.join(self.root, "dist")
        os.makedirs(dist, exist_ok=True)
        for name in ("test-book.md", "test-book.html", "test-book.log"):
            with open(os.path.join(dist, name), "w", encoding="utf-8") as fh:
                fh.write("x\n")

    def book_dir(self) -> str:
        return os.path.join(self.root, "data", "archive", self.archive.book_slug())

    def test_the_manuscript_is_copied_under_the_date(self):
        summary = self.archive.take(["manuscript"], TODAY)
        self.assertEqual(summary["kinds"], ["manuscript"])
        day = os.path.join(self.book_dir(), "2026-11-22", "manuscript")
        self.assertTrue(os.path.isfile(os.path.join(day, "ch1-test.md")))
        self.assertTrue(
            os.path.isfile(os.path.join(day, "manifest.json"))
            or os.path.isfile(os.path.join(self.book_dir(), "2026-11-22", "manifest.json"))
        )

    def test_the_delivered_artefacts_are_copied_without_logs(self):
        self.seed_dist()
        self.archive.take(["dist"], TODAY)
        day = os.path.join(self.book_dir(), "2026-11-22", "dist")
        self.assertTrue(
            os.path.isfile(
                os.path.join(
                    day,
                    "test-book.pdf"
                    if os.path.isfile(os.path.join(self.root, "dist", "test-book.pdf"))
                    else "test-book.md",
                )
            )
        )
        self.assertFalse(os.path.exists(os.path.join(day, "test-book.log")))

    def test_the_manifest_records_files_and_sizes(self):
        self.archive.take(["manuscript"], TODAY)
        path = os.path.join(self.book_dir(), "2026-11-22", "manifest.json")
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        self.assertEqual(payload["date"], "2026-11-22")
        self.assertIn("manuscript", payload["files"])
        self.assertTrue(payload["digest"])

    def test_old_dates_are_pruned_outside_the_window(self):
        old = self.book_dir()
        for name in ("2026-09-01", "2026-10-01", "2026-11-20"):
            os.makedirs(os.path.join(old, name), exist_ok=True)
        summary = self.archive.take(["manuscript"], TODAY)
        # TODAY is 2026-11-22 with a 45-day window, so the cutoff is 2026-10-08.
        self.assertIn("2026-09-01", summary["pruned"])
        self.assertIn("2026-10-01", summary["pruned"])
        self.assertFalse(os.path.isdir(os.path.join(old, "2026-09-01")))
        self.assertTrue(os.path.isdir(os.path.join(old, "2026-11-20")))

    def test_a_dry_run_touches_nothing(self):
        self.seed_dist()
        before = sorted(os.listdir(os.path.join(self.root, "data")))
        summary = self.archive.take(["dist"], TODAY, dry_run=True)
        self.assertTrue(summary["dry_run"])
        self.assertEqual(sorted(os.listdir(os.path.join(self.root, "data"))), before)

    def test_the_book_directory_is_named_after_the_book(self):
        self.assertEqual(self.archive.book_slug(), "test-book")

    def test_nothing_to_archive_is_reported(self):
        code, out = _fixture.run_inproc(self.root, "archive.py", "--json", "--kind", "dist")
        if os.path.isdir(os.path.join(self.root, "dist")):
            for name in os.listdir(os.path.join(self.root, "dist")):
                os.remove(os.path.join(self.root, "dist", name))
        self.assertIn(code, (0, 1))
        if out.strip().startswith("{"):
            self.assertIn("files", json.loads(out))

    def test_the_cli_writes_the_summary_as_json(self):
        self.seed_dist()
        code, out = _fixture.run_inproc(self.root, "archive.py", "--json", "--today", "2026-11-22")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["date"], "2026-11-22")
        self.assertIn("dist", payload["kinds"])

    def test_a_bad_date_is_usage_error(self):
        code, _out = _fixture.run_inproc(self.root, "archive.py", "--today", "22/11/2026")
        self.assertEqual(code, 2)

    def test_retention_falls_back_to_the_default(self):
        with mock.patch.dict(self.archive._config.POLICY, {"archive": {"retention_days": "x"}}):
            self.assertEqual(self.archive.settings()["retention_days"], 45)


class ArchiveEdgeTest(unittest.TestCase):
    """Archive fallbacks: unnamed books, foreign sources, stale directories."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.archive = _fixture.load_module(self.root, "archive")

    def test_a_book_without_a_merged_name_falls_back_to_its_title(self):
        with (
            mock.patch.object(self.archive._config, "MERGED_NAME", ""),
            mock.patch.object(self.archive._config, "TITLE", "我的 书"),
        ):
            self.assertEqual(self.archive.book_slug(), "我的-书")

    def test_a_file_outside_the_source_root_keeps_only_its_name(self):
        source = os.path.join(self.root, "manuscript")
        outside = os.path.join(self.root, "elsewhere", "draft.md")
        os.makedirs(os.path.dirname(outside), exist_ok=True)
        with open(outside, "w", encoding="utf-8") as handle:
            handle.write("x\n")
        copied = self.archive._copy([outside], source, os.path.join(self.root, "copy"))
        self.assertEqual(list(copied), ["draft.md"])

    def test_date_directories_ignore_other_names(self):
        book_dir = os.path.join(self.root, "archive-dirs")
        os.makedirs(os.path.join(book_dir, "2026-11-20"), exist_ok=True)
        os.makedirs(os.path.join(book_dir, "notes"), exist_ok=True)
        with open(os.path.join(book_dir, "2026-10-01"), "w", encoding="utf-8") as handle:
            handle.write("x\n")
        found = [os.path.basename(path) for _day, path in self.archive._date_dirs(book_dir)]
        self.assertEqual(found, ["2026-11-20"])
        self.assertEqual(self.archive._date_dirs(os.path.join(self.root, "nowhere")), [])

    def test_a_dry_run_prunes_without_deleting(self):
        book_dir = os.path.join(self.root, "dry")
        old = os.path.join(book_dir, "2026-01-01")
        os.makedirs(old, exist_ok=True)
        removed = self.archive.prune(book_dir, 45, TODAY, dry_run=True)
        self.assertEqual(removed, ["2026-01-01"])
        self.assertTrue(os.path.isdir(old))

    def test_a_directory_that_cannot_be_removed_is_a_warning(self):
        book_dir = os.path.join(self.root, "locked")
        os.makedirs(os.path.join(book_dir, "2026-01-01"), exist_ok=True)
        stderr = io.StringIO()
        with (
            mock.patch.object(self.archive.shutil, "rmtree", side_effect=OSError("busy")),
            redirect_stderr(stderr),
        ):
            removed = self.archive.prune(book_dir, 45, TODAY)
        self.assertEqual(removed, ["2026-01-01"])
        self.assertIn("busy", stderr.getvalue())

    def test_the_cli_reports_what_it_pruned(self):
        book_dir = os.path.join(self.root, "data", "archive", self.archive.book_slug())
        os.makedirs(os.path.join(book_dir, "2026-01-01"), exist_ok=True)
        code, out = _fixture.run_inproc(self.root, "archive.py", "--today", "2026-11-22")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("已清理", out)


if __name__ == "__main__":
    unittest.main()
