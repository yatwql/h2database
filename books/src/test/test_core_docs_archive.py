#!/usr/bin/env python3
"""Docs archive: mechanical moves into docs/archive."""

from __future__ import annotations

import importlib
import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:core", "tier:fast")

_fixture.ensure_tools_path()

CHANGELOG = """# 变更日志
> 版本：v0.1
---
## [0.1] - 开发中（未发布）
### 变更
- 第一件事
## 归档
"""

PLAN = """# 实施与维护计划
## 概述
在办 1 项。
"""

RF = """# 自我审查问题记录
## 当前待处理问题
| # | 问题 |
| --- | --- |
### 本版本已修复（0.1）
| # | 问题 | 修复 |
| --- | --- | --- |
| rf-1 | 某问题 | 某修复 |
## 归档
"""


def write_docs(root: str) -> None:
    """A miniature docs tree with the three live ledgers."""
    os.makedirs(os.path.join(root, "managements"), exist_ok=True)
    os.makedirs(os.path.join(root, "archive"), exist_ok=True)
    for name, text in (("changelog", CHANGELOG), ("plan", PLAN), ("review-findings", RF)):
        with open(os.path.join(root, "managements", f"{name}.md"), "w", encoding="utf-8") as fh:
            fh.write(text)


class ArchiveHelpersTest(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module("core.docs_archive")

    def test_a_patch_version_belongs_to_its_minor(self):
        self.assertEqual(self.mod.minor_of("0.1.3"), "0.1")
        self.assertEqual(self.mod.version_dir_name("v0.1"), "v0.1")
        self.assertEqual(self.mod.archive_names("0.1")["changelog"], "archived_changelog.0.1.md")

    def test_a_version_without_a_minor_is_rejected(self):
        with self.assertRaises(self.mod.ArchiveError):
            self.mod.minor_of("7")

    def test_the_header_is_written_once_and_then_rewritten(self):
        once = self.mod.apply_header("正文\n", "0.1", "2026-11-22")
        self.assertIn("> 涵盖版本：0.1", once)
        self.assertIn("> 归档时间：2026-11-22", once)
        twice = self.mod.apply_header(once, "0.2", "2026-12-01")
        self.assertEqual(twice.count("> 涵盖版本："), 1)
        self.assertIn("> 涵盖版本：0.2", twice)

    def test_the_release_section_leaves_the_live_changelog(self):
        rest, section = self.mod.split_version_section(CHANGELOG, "0.1")
        self.assertIn("第一件事", section)
        self.assertNotIn("第一件事", rest)
        self.assertIn("## 归档", rest)

    def test_a_missing_release_section_is_reported(self):
        with self.assertRaises(self.mod.ArchiveError):
            self.mod.split_version_section(CHANGELOG, "9.9")

    def test_the_fixed_issue_table_leaves_the_live_ledger(self):
        rest, block = self.mod.split_rf_block(RF, "0.1")
        self.assertIn("rf-1", block)
        self.assertNotIn("rf-1", rest)

    def test_the_index_is_added_once(self):
        line = self.mod.index_line("archived_changelog.0.1.md", "v0.1", "0.1")
        once = self.mod.ensure_index("# x\n", [line])
        twice = self.mod.ensure_index(once, [line])
        self.assertEqual(once, twice)
        self.assertEqual(once.count("## 归档"), 1)


class ArchiveFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        write_docs(self.tmp)
        self.mod = importlib.import_module("core.docs_archive")

    def read(self, *parts: str) -> str:
        with open(os.path.join(self.tmp, *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_dry_run_writes_nothing(self):
        plan = self.mod.build_plan("0.1", self.tmp, [], "2026-11-22")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "archive", "v0.1")))
        self.assertTrue(any("迁出变更日志" in step for step in plan.describe()))

    def test_apply_moves_every_ledger_and_keeps_the_live_files(self):
        plan = self.mod.build_plan("0.1", self.tmp, [], "2026-11-22")
        self.mod.apply_plan(plan, [])
        for name in ("changelog", "plan", "review-findings"):
            archived = self.read("archive", "v0.1", f"archived_{name}.0.1.md")
            self.assertIn("> 涵盖版本：0.1", archived)
        self.assertNotIn("第一件事", self.read("managements", "changelog.md"))
        self.assertNotIn("rf-1", self.read("managements", "review-findings.md"))
        for name in ("changelog", "plan", "review-findings"):
            self.assertIn("archived_", self.read("managements", f"{name}.md"))

    def test_running_twice_changes_nothing(self):
        self.mod.apply_plan(self.mod.build_plan("0.1", self.tmp, [], "2026-11-22"), [])
        snapshot = {
            name: self.read("managements", f"{name}.md")
            for name in ("changelog", "plan", "review-findings")
        }
        self.mod.apply_plan(self.mod.build_plan("0.1", self.tmp, [], "2026-11-22"), [])
        for name, before in snapshot.items():
            self.assertEqual(self.read("managements", f"{name}.md"), before)

    def test_a_finished_iteration_directory_moves_whole(self):
        topic = os.path.join(self.tmp, "plan", "diagram-upgrade")
        os.makedirs(topic)
        with open(os.path.join(topic, "design.md"), "w", encoding="utf-8") as fh:
            fh.write("# 设计\n")
        plan = self.mod.build_plan("0.1", self.tmp, ["diagram-upgrade"], "2026-11-22")
        self.mod.apply_plan(plan, ["diagram-upgrade"])
        self.assertTrue(
            os.path.isfile(
                os.path.join(self.tmp, "archive", "v0.1", "diagram-upgrade", "design.md")
            )
        )
        self.assertFalse(os.path.exists(topic))

    def test_an_unknown_iteration_directory_is_an_error(self):
        plan = self.mod.build_plan("0.1", self.tmp, ["no-such-topic"], "2026-11-22")
        self.assertTrue(plan.errors)

    def test_missing_live_ledgers_are_reported(self):
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty, True)
        plan = self.mod.build_plan("0.1", empty, [], "2026-11-22")
        self.assertEqual(len(plan.errors), 3)




class DocsArchiveFailurePathsTest(unittest.TestCase):
    """Move/refresh failures become ArchiveError; the CLI turns them into exit 2."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(_fixture.build_book(self.tmp.name), "docs_archive")

    def plan(self, **overrides) -> mock.Mock:
        plan = mock.Mock()
        plan.errors = overrides.get("errors", [])
        plan.docs = self.tmp.name
        plan.target = os.path.join(self.tmp.name, "archive", "v0.1")
        plan.version = "0.1"
        plan.names = {"changelog": "changelog-0.1.md"}
        plan.live = lambda name: os.path.join(self.tmp.name, "live", name)
        plan.path = lambda name: os.path.join(self.tmp.name, "snapshots", name)
        plan.describe = lambda: ["move changelog"]
        return plan

    def test_an_index_without_entries_is_left_untouched(self):
        self.assertEqual(self.mod.ensure_index("# 变更日志\n", []), "# 变更日志\n")

    def test_a_destination_that_already_exists_is_not_moved_again(self):
        plan = self.plan()
        topic = "topic-a"
        os.makedirs(os.path.join(plan.target, topic), exist_ok=True)
        os.makedirs(os.path.join(plan.docs, "plan", topic), exist_ok=True)
        self.mod._move_topics(plan, [topic])
        self.assertTrue(os.path.isdir(os.path.join(plan.docs, "plan", topic)))

    def test_a_move_that_fails_is_an_archive_error(self):
        plan = self.plan()
        os.makedirs(os.path.join(plan.docs, "plan", "topic-b"), exist_ok=True)
        with mock.patch.object(self.mod.shutil, "move", side_effect=OSError("busy")):
            with self.assertRaises(self.mod.ArchiveError) as raised:
                self.mod._move_topics(plan, ["topic-b"])
        self.assertIn("topic-b", str(raised.exception))

    def test_an_unreadable_archive_directory_is_an_archive_error(self):
        plan = self.plan()
        with mock.patch.object(self.mod.os, "listdir", side_effect=OSError("denied")):
            with self.assertRaises(self.mod.ArchiveError):
                self.mod._refresh_indexes(plan)

    def test_a_plan_with_errors_refuses_to_apply(self):
        plan = self.plan(errors=["目录名不合规"])
        with self.assertRaises(self.mod.ArchiveError):
            self.mod.apply_plan(plan, [])

    def test_the_cli_reports_a_bad_plan_and_a_failed_apply(self):
        plan = self.plan(errors=["目录名不合规"])
        buffer = io.StringIO()
        with mock.patch.object(self.mod, "build_plan", return_value=plan), redirect_stdout(buffer):
            self.assertEqual(self.mod.main(["--version", "0.1"]), 2)
        self.assertIn("目录名不合规", buffer.getvalue())

        clean = self.plan()
        with (
            mock.patch.object(self.mod, "build_plan", return_value=clean),
            mock.patch.object(
                self.mod, "apply_plan", side_effect=self.mod.ArchiveError("无法移动")
            ),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main(["--version", "0.1"]), 2)
        self.assertIn("无法移动", buffer.getvalue())

    def test_the_cli_reports_the_archived_version(self):
        clean = self.plan()
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "build_plan", return_value=clean),
            mock.patch.object(self.mod, "apply_plan"),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main(["--version", "0.1"]), 0)
        self.assertIn("已归档 0.1", buffer.getvalue())


class DocsArchiveEdgeCaseTest(unittest.TestCase):
    """The entries an archive tree accumulates that do not belong to a release."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "docs_archive")
        self.docs = os.path.join(self.tmp.name, "docs")
        write_docs(self.docs)

    def test_a_fixed_issue_block_for_another_version_is_skipped(self):
        ledger = (
            "# 问题记录\n"
            "### 本版本已修复（9.9）\n| rf-0 | 旧问题 |\n\n"
            "### 本版本已修复（0.1）\n| rf-1 | 新问题 |\n"
        )
        rest, block = self.mod.split_rf_block(ledger, "0.1")
        self.assertIn("rf-0", rest)
        self.assertIn("rf-1", block)
        self.assertNotIn("rf-1", rest)

    def test_an_iteration_directory_with_an_irregular_name_is_an_error(self):
        os.makedirs(os.path.join(self.docs, "plan", "2024 旧计划"))
        plan = self.mod.build_plan("0.1", self.docs, ["2024 旧计划"], "2026-01-01")
        self.assertTrue(any("不合规" in error for error in plan.errors), plan.errors)

    def test_a_stray_entry_in_the_archive_directory_gets_no_index_line(self):
        os.makedirs(os.path.join(self.docs, "archive", "v0.1"))
        with open(os.path.join(self.docs, "archive", "notes.md"), "w", encoding="utf-8") as fh:
            fh.write("随手笔记\n")
        plan = self.mod.build_plan("0.2", self.docs, [], "2026-01-01")
        self.mod._refresh_indexes(plan)
        with open(os.path.join(self.docs, "managements", "changelog.md"), encoding="utf-8") as fh:
            changelog = fh.read()
        self.assertIn("v0.1", changelog)
        self.assertNotIn("notes", changelog)

    def test_the_cli_reports_a_version_it_cannot_archive(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(["--version", "7", "--dry-run"])
        self.assertEqual(code, 2)
        self.assertIn("error:", buffer.getvalue())

    def test_the_script_entrypoint_reports_through_the_error_wrapper(self):
        code, out = _fixture.run_inproc(self.root, "docs_archive.py", "--version", "7")
        self.assertEqual(code, 2, out[-300:])
        self.assertIn("error:", out)


if __name__ == "__main__":
    unittest.main()
