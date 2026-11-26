#!/usr/bin/env python3
"""The ingest run as the operator drives it: dry runs over marked files, the
counters the summary prints, the LLM plan, and the guards in front of `main`.

The write paths themselves are covered next door; these cases are about what the
run *says* and refuses before any file moves.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:ingest", "tier:fast")

_fixture.ensure_tools_path()


def package(lines: int) -> dict:
    return {
        "lines": lines,
        "files": 2,
        "summary": "示例包",
        "depends_on": {},
        "key_classes": [],
    }


class CliCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, "chapters")
        self.args = argparse.Namespace(
            only=None, dry_run=False, force=False, refresh_facts=False, llm=False
        )
        self.chapter = {
            "file": "ch1-test.md",
            "source_lines": 120,
            "packages": {"org.example": package(120)},
        }

    def path(self, name: str = "ch1-test.md") -> str:
        return os.path.join(self.root, "data", "manuscript", name)

    def write(self, text: str, name: str = "ch1-test.md") -> None:
        with open(self.path(name), "w", encoding="utf-8") as handle:
            handle.write(text)

    def run_emit(self, args) -> tuple[str, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = self.chapters._emit_chapter(self.chapter, args, "STAMP")
        return status, buffer.getvalue()


class DryRunOverMarkedFileTest(CliCase):
    def test_refresh_facts_with_dry_run_lists_the_block_delta(self):
        self.write(self.chapters.render_chapter(self.chapter))
        self.chapter["source_lines"] = 800
        self.chapter["packages"] = {"org.example": package(800)}
        self.args.refresh_facts = True
        self.args.dry_run = True
        status, printed = self.run_emit(self.args)
        self.assertEqual(status, "refresh")
        self.assertIn("--- ch1-test.md（事实块 -", printed)
        with open(self.path(), encoding="utf-8") as handle:
            self.assertIn("| `org.example` | 2 | 120 |", handle.read())

    def test_refresh_facts_reports_a_file_that_is_already_current(self):
        self.write(self.chapters.render_chapter(self.chapter))
        self.args.refresh_facts = True
        status, printed = self.run_emit(self.args)
        self.assertEqual(status, "unchanged")
        self.assertIn("事实块已是最新", printed)

    def test_a_plain_dry_run_over_a_marked_file_reports_the_delta_only(self):
        self.write(self.chapters.render_chapter(self.chapter))
        self.chapter["source_lines"] = 640
        self.chapter["packages"] = {"org.example": package(640)}
        self.args.dry_run = True
        status, printed = self.run_emit(self.args)
        self.assertEqual(status, "refresh")
        self.assertIn("（事实块 -", printed)

    def test_force_over_a_missing_file_writes_without_a_backup(self):
        os.remove(self.path())
        self.args.force = True
        status, printed = self.run_emit(self.args)
        self.assertEqual(status, "written")
        self.assertIn("wrote ch1-test.md", printed)
        self.assertNotIn("备份", printed)


class CountersReportTest(CliCase):
    def test_the_summary_names_refreshed_and_unchanged_chapters(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.chapters._report(
                {"written": 1, "skipped": 0, "refreshed": 2, "unchanged": 3, "unmarked": 0},
                self.args,
            )
        text = buffer.getvalue()
        self.assertIn("事实块已刷新: 2 章", text)
        self.assertIn("事实块无变化: 3 章", text)
        self.assertNotIn("LLM 未介入", text)

    def test_a_run_that_wrote_nothing_says_the_llm_had_nothing_to_polish(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer), mock.patch.object(self.chapters, "_USE_LLM", True):
            self.chapters._report(
                {"written": 0, "skipped": 1, "refreshed": 0, "unchanged": 0, "unmarked": 0},
                self.args,
            )
        text = buffer.getvalue()
        self.assertIn("LLM 未介入", text)
        self.assertIn("--force", text)

    def test_emit_all_counts_the_appendix_and_ignores_files_the_book_lacks(self):
        outline = {
            "chapters": [
                {"file": "appendix-z.md", "source_lines": 1, "packages": {}},
                {"file": "ch9-unknown.md", "source_lines": 1, "packages": {}},
            ]
        }
        with (
            mock.patch.dict(
                self.chapters.APPENDIX_SPEC, {"appendix-z.md": (9, "附录")}, clear=True
            ),
            mock.patch.dict(self.chapters.CHAPTER_SPEC, {}, clear=True),
            mock.patch.object(self.chapters, "_append_appendix", return_value="written"),
        ):
            counters = self.chapters._emit_all(outline, self.args, "STAMP")
        self.assertEqual(counters["written"], 1)
        self.assertEqual(counters["skipped"], 0)


class SourceChangeErrorTest(CliCase):
    def test_an_unreadable_previous_record_reads_as_changed(self):
        state = os.path.join(self.root, "data", "state")
        os.makedirs(state, exist_ok=True)
        with open(
            os.path.join(state, "source-inventory.prev.json"), "w", encoding="utf-8"
        ) as handle:
            handle.write("{}")
        # the read happens in _source_state, so that is the module to break
        read_text = mock.patch.object(
            self.chapters._source_state._fsutil, "read_text", side_effect=OSError("media error")
        )
        with read_text:
            self.assertIn("不可读", self.chapters._source_change_line())


class LlmPlanTest(CliCase):
    def plan(self, chapters: dict, appendix: dict, only=None) -> tuple[int, str]:
        buffer = io.StringIO()
        with (
            mock.patch.dict(self.chapters.CHAPTER_SPEC, chapters, clear=True),
            mock.patch.dict(self.chapters.APPENDIX_SPEC, appendix, clear=True),
            redirect_stdout(buffer),
        ):
            code = self.chapters._print_llm_plan(argparse.Namespace(only=only, force=False))
        return code, buffer.getvalue()

    def test_only_the_missing_chapters_count_as_work(self):
        code, text = self.plan({"ch1-test.md": [(1, "一")]}, {})
        self.assertEqual(code, 0)
        self.assertIn("计划：补缺 0 章", text)
        self.assertIn("结论：没有需要 LLM 起草的内容", text)

    def test_a_missing_chapter_is_planned_for_generation(self):
        code, text = self.plan({"ch9-new.md": [(9, "九")]}, {})
        self.assertEqual(code, 0)
        self.assertIn("计划：补缺 1 章", text)
        self.assertIn("共 2 次", text)
        self.assertIn("本轮跳过：0 章", text)

    def test_a_forced_plan_rewrites_every_chapter(self):
        buffer = io.StringIO()
        with (
            mock.patch.dict(self.chapters.CHAPTER_SPEC, {"ch1-test.md": [(1, "一")]}, clear=True),
            mock.patch.dict(self.chapters.APPENDIX_SPEC, {}, clear=True),
            redirect_stdout(buffer),
        ):
            self.chapters._print_llm_plan(argparse.Namespace(only=None, force=True))
        self.assertIn("整篇重写 1 章", buffer.getvalue())

    def test_an_explicit_chapter_is_planned_even_when_it_exists(self):
        code, text = self.plan({"ch1-test.md": [(1, "一")]}, {}, only="ch1-test.md")
        self.assertEqual(code, 0)
        self.assertIn("整篇重写 1 章", text)


class MainGuardTest(CliCase):
    def test_refresh_facts_and_force_together_are_refused(self):
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = self.chapters.main(["--refresh-facts", "--force"])
        self.assertEqual(code, 2)
        self.assertIn("不能同时使用", err.getvalue())

    def test_llm_with_plan_prints_the_estimate_and_writes_nothing(self):
        with (
            mock.patch.dict(self.chapters.CHAPTER_SPEC, {"ch9-new.md": [(9, "九")]}, clear=True),
            mock.patch.dict(self.chapters.APPENDIX_SPEC, {}, clear=True),
            redirect_stdout(io.StringIO()),
        ):
            code = self.chapters.main(["--llm", "--plan"])
        self.assertEqual(code, 0)

    def test_llm_announces_a_first_build_before_the_scan(self):
        os.remove(self.path())
        state = os.path.join(self.root, "data", "state")
        os.makedirs(state, exist_ok=True)
        with open(os.path.join(state, "source-inventory.json"), "w", encoding="utf-8") as fh:
            json.dump({"packages": {}}, fh)
        with open(os.path.join(state, "outline.json"), "w", encoding="utf-8") as fh:
            json.dump({"chapters": [self.chapter]}, fh)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.chapters.main(["--llm"])
        self.assertEqual(code, 0, buffer.getvalue()[-300:])
        self.assertIn("本轮将生成", buffer.getvalue())
        self.assertIn("导读/小结起草文字", buffer.getvalue())

    def test_llm_with_every_chapter_on_disk_declines_to_run(self):
        state = os.path.join(self.root, "data", "state")
        os.makedirs(state, exist_ok=True)
        with open(os.path.join(state, "source-inventory.json"), "w", encoding="utf-8") as fh:
            json.dump({"packages": {}}, fh)
        with open(os.path.join(state, "outline.json"), "w", encoding="utf-8") as fh:
            json.dump({"chapters": [self.chapter]}, fh)
        buffer = io.StringIO()
        with (
            mock.patch.dict(self.chapters.CHAPTER_SPEC, {"ch1-test.md": [(1, "一")]}, clear=True),
            mock.patch.dict(self.chapters.APPENDIX_SPEC, {}, clear=True),
            redirect_stdout(buffer),
        ):
            code = self.chapters.main(["--llm"])
        self.assertEqual(code, 0)
        self.assertIn("不会生成或重写任何章节", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
