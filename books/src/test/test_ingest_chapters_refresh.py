#!/usr/bin/env python3
"""Fact-block refresh: only the marked blocks move, prose stays byte-identical."""

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


def package(lines: int, classes: int = 2) -> dict:
    """One package entry shaped like the source inventory."""
    return {
        "lines": lines,
        "files": 3,
        "summary": "示例包",
        "depends_on": {"org.example.core": 4},
        "key_classes": [
            {
                "name": f"Widget{index}",
                "lines": max(1, lines // (index + 2)),
                "public_methods": index + 1,
                "summary": "示例类型",
                "rel": f"org/example/Widget{index}.java",
                "api": ["run"],
                "api_lines": {"run": 10 + index},
            }
            for index in range(classes)
        ],
    }


class RefreshBlocksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, "chapters")
        self.factblocks = _fixture.load_module(self.root, "factblocks")

    def chapter(self, lines: int) -> dict:
        return {
            "file": "ch1-test.md",
            "source_lines": lines,
            "packages": {"org.example": package(lines)},
        }

    def test_the_renderer_marks_every_recomputable_block(self):
        text = self.chapters.render_chapter(self.chapter(120))
        self.assertIn("<!-- generated:packages -->", text)
        self.assertIn("<!-- generated:api -->", text)
        self.assertIn("<!-- /generated -->", text)

    def test_refresh_swaps_only_the_marked_blocks(self):
        old = self.chapters.render_chapter(self.chapter(120))
        new = self.chapters.render_chapter(self.chapter(480))
        result = self.factblocks.refresh_blocks(old, new)
        self.assertIsNotNone(result)
        refreshed, removed, added = result
        self.assertGreater(removed + added, 0)

        self.assertTrue(self.factblocks.generated_blocks(old))
        old_lines = old.split("\n")
        spans = []
        name = None
        start = 0
        for index, line in enumerate(old_lines):
            opening = self.factblocks.GENERATED_OPEN_RE.match(line.strip())
            if opening and name is None:
                name, start = opening.group(1), index
                continue
            if self.factblocks.GENERATED_CLOSE_RE.match(line.strip()) and name is not None:
                spans.append((start, index))
                name = None
        refreshed_lines = refreshed.split("\n")
        changed = [
            index for index, before in enumerate(old_lines) if before != refreshed_lines[index]
        ]
        for index in changed:
            self.assertTrue(
                any(start <= index <= end for start, end in spans),
                f"line {index} changed outside a marked block: {old_lines[index]}",
            )

    def test_prose_outside_the_markers_survives_verbatim(self):
        old = self.chapters.render_chapter(self.chapter(120))
        prose = "这是作者自己写的一段正文，刷新事实块时一个字都不该动。"
        injected = old.replace("## 1.1 模块版图", prose + "\n\n## 1.1 模块版图", 1)
        refreshed, _removed, _added = self.factblocks.refresh_blocks(
            injected, self.chapters.render_chapter(self.chapter(480))
        )
        self.assertIn(prose, refreshed)

    def test_a_file_without_markers_reports_nothing_to_refresh(self):
        self.assertIsNone(
            self.factblocks.refresh_blocks("# 第1章 手写章节\n\n全是人写的正文。\n", "")
        )

    def test_unchanged_facts_produce_an_identical_file(self):
        text = self.chapters.render_chapter(self.chapter(120))
        refreshed, removed, added = self.factblocks.refresh_blocks(text, text)
        self.assertEqual((refreshed, removed, added), (text, 0, 0))

    def test_a_block_the_fresh_render_dropped_leaves_the_chapter(self):
        old = self.chapters.render_chapter(self.chapter(120))
        blocks = self.factblocks.generated_blocks(old)
        self.assertGreater(len(blocks), 1)
        kept = sorted(blocks)[0]
        fresh = f"<!-- generated:{kept} -->\n- 新的一行\n<!-- /generated -->\n"
        refreshed, removed, added = self.factblocks.refresh_blocks(old, fresh)
        after = self.factblocks.generated_blocks(refreshed)
        self.assertEqual(set(after), set(blocks))
        self.assertIn("- 新的一行", refreshed)
        untouched = sorted(set(blocks) - {kept})[0]
        self.assertEqual(after[untouched], blocks[untouched])
        self.assertGreater(removed, 0)

    def test_a_chapter_that_does_not_exist_yet_has_nothing_to_back_up(self):
        path = os.path.join(self.root, "data", "manuscript", "ch9-new.md")
        self.assertIsNone(self.factblocks.backup_existing(path, "20240101"))

    def test_a_failed_backup_warns_and_lets_the_overwrite_go_ahead(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        buffer = io.StringIO()
        with (
            mock.patch.object(
                self.factblocks._fsutil, "write_text", side_effect=OSError("disk full")
            ),
            contextlib.redirect_stderr(buffer),
        ):
            self.assertIsNone(self.factblocks.backup_existing(path, "20240101"))
        self.assertIn("备份失败", buffer.getvalue())


class ForceAndRefreshRunTest(unittest.TestCase):
    """The two write paths as the CLI drives them."""

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

    def path(self) -> str:
        return os.path.join(self.root, "data", "manuscript", "ch1-test.md")

    def test_force_backs_the_old_file_up_and_reports_the_cost(self):
        self.args.force = True
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = self.chapters._emit_chapter(self.chapter, self.args, "STAMP")
        self.assertEqual(status, "written")
        self.assertIn("-", buffer.getvalue())
        backup = os.path.join(self.root, "data", "tmp", "generated-backup", "STAMP", "ch1-test.md")
        self.assertTrue(os.path.isfile(backup))

    def test_refresh_leaves_an_unmarked_file_alone_and_says_why(self):
        self.args.refresh_facts = True
        before = "# 第1章 示例总览\n\n作者手写正文。\n"
        with open(self.path(), "w", encoding="utf-8") as fh:
            fh.write(before)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = self.chapters._emit_chapter(self.chapter, self.args, "STAMP")
        self.assertEqual(status, "skip")
        self.assertIn("无标记块", buffer.getvalue())
        with open(self.path(), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)

    def test_refresh_rewrites_a_marked_file_in_place(self):
        self.args.refresh_facts = True
        with open(self.path(), "w", encoding="utf-8") as fh:
            fh.write(self.chapters.render_chapter(self.chapter))
        self.chapter["source_lines"] = 900
        self.chapter["packages"] = {"org.example": package(900)}
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = self.chapters._emit_chapter(self.chapter, self.args, "STAMP")
        self.assertEqual(status, "refresh")
        with open(self.path(), encoding="utf-8") as fh:
            self.assertIn("| `org.example` | 3 | 900 |", fh.read())

    def test_the_run_summary_names_refreshed_and_skipped_chapters(self):
        state = os.path.join(self.root, "data", "state")
        os.makedirs(state, exist_ok=True)
        with open(os.path.join(state, "source-inventory.json"), "w", encoding="utf-8") as fh:
            json.dump({"packages": {}}, fh)
        with open(os.path.join(state, "outline.json"), "w", encoding="utf-8") as fh:
            json.dump({"chapters": [self.chapter]}, fh)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.chapters.main(["--refresh-facts"])
        self.assertEqual(code, 0)
        self.assertIn("刷新 0 章 / 跳过 1 章（无标记块）", buffer.getvalue())


class CliPathsTest(unittest.TestCase):
    """--dry-run, --force (with backup), appendices and unreadable state."""

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

    def write_state(self, outline: dict) -> None:
        state = os.path.join(self.root, "data", "state")
        os.makedirs(state, exist_ok=True)
        with open(os.path.join(state, "source-inventory.json"), "w", encoding="utf-8") as fh:
            json.dump({"packages": {}}, fh)
        with open(os.path.join(state, "outline.json"), "w", encoding="utf-8") as fh:
            json.dump(outline, fh)

    def test_dry_run_reports_the_size_and_writes_nothing(self):
        os.remove(self.path())  # nothing to preserve, so the renderer runs
        self.args.dry_run = True
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = self.chapters._emit_chapter(self.chapter, self.args, "STAMP")
        self.assertEqual(status, "written")
        self.assertIn("--- ch1-test.md (", buffer.getvalue())
        self.assertFalse(os.path.exists(self.path()))

    def test_force_overwrites_prose_after_backing_it_up(self):
        with open(self.path(), "w", encoding="utf-8") as fh:
            fh.write("作者写的一段正文。\n")
        self.args.force = True
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = self.chapters._emit_chapter(self.chapter, self.args, "STAMP")
        self.assertEqual(status, "written")
        with open(self.path(), encoding="utf-8") as fh:
            self.assertIn("本章导读", fh.read())
        backups = os.path.join(self.root, "data", "tmp")
        self.assertTrue(
            any("STAMP" in folder for _dir, _dirs, _files in os.walk(backups) for folder in [_dir]),
            list(os.walk(backups)),
        )

    def test_an_appendix_is_written_only_once(self):
        appendix = next(iter(self.chapters.APPENDIX_SPEC), None)
        if appendix is None:
            self.skipTest("this book declares no appendix")
        self.chapters.APPENDIX_SPEC[appendix] = (1, "测试附录")
        self.addCleanup(self.chapters.APPENDIX_SPEC.pop, appendix, None)
        chapter = {"file": appendix, "source_lines": 10, "packages": {"org.example": package(10)}}
        first = self.chapters._append_appendix(chapter, False)
        second = self.chapters._append_appendix(chapter, False)
        self.assertEqual((first, second), ("written", "skip"))

    def test_unreadable_state_files_are_refused(self):
        state = os.path.join(self.root, "data", "state")
        os.makedirs(state, exist_ok=True)
        with open(os.path.join(state, "outline.json"), "w", encoding="utf-8") as fh:
            fh.write("{broken")
        with open(os.path.join(state, "source-inventory.json"), "w", encoding="utf-8") as fh:
            json.dump({}, fh)
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = self.chapters.main([])
        self.assertEqual(code, 2)
        self.assertIn("not valid JSON", err.getvalue())

    def test_only_restricts_the_run_to_one_file(self):
        other = {
            "file": "ch2-test.md",
            "source_lines": 60,
            "packages": {"org.example": package(60)},
        }
        self.write_state({"chapters": [self.chapter, other]})
        with open(self.path("ch1-test.md"), encoding="utf-8") as fh:
            before = fh.read()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.chapters.main(["--only", "ch2-test.md"])
        self.assertEqual(code, 0, buffer.getvalue()[-300:])
        with open(self.path("ch1-test.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)  # untouched by an --only run


class DefaultModeTest(unittest.TestCase):
    """Without --force the renderer refreshes facts and keeps the prose."""

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

    def path(self) -> str:
        return os.path.join(self.root, "data", "manuscript", "ch1-test.md")

    def test_a_marked_file_is_refreshed_and_the_prose_survives(self):
        prose = "作者写的一段正文。"
        rendered = self.chapters.render_chapter(self.chapter)
        with open(self.path(), "w", encoding="utf-8") as fh:
            fh.write(rendered.replace("## 1.1 模块版图", prose + "\n\n## 1.1 模块版图", 1))
        self.chapter["source_lines"] = 900
        self.chapter["packages"] = {"org.example": package(900)}

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = self.chapters._emit_chapter(self.chapter, self.args, "STAMP")
        self.assertEqual(status, "refresh")
        self.assertIn("事实块 -", buffer.getvalue())
        with open(self.path(), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(prose, text)
        self.assertIn("| `org.example` | 3 | 900 |", text)

    def test_an_unchanged_file_reports_no_work(self):
        with open(self.path(), "w", encoding="utf-8") as fh:
            fh.write(self.chapters.render_chapter(self.chapter))
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = self.chapters._emit_chapter(self.chapter, self.args, "STAMP")
        self.assertEqual(status, "unchanged")
        self.assertIn("事实块与源码一致", buffer.getvalue())

    def test_an_unmarked_file_is_left_alone(self):
        before = "# 第1章 示例总览\n\n全是人写的正文。\n"
        with open(self.path(), "w", encoding="utf-8") as fh:
            fh.write(before)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = self.chapters._emit_chapter(self.chapter, self.args, "STAMP")
        self.assertEqual(status, "skip")
        self.assertIn("正文无标记块", buffer.getvalue())
        with open(self.path(), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)


class SourceChangeLineTest(unittest.TestCase):
    """The renderer says whether the source tree moved since the last ingest."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, "chapters")
        self.state = os.path.join(self.root, "data", "state")
        os.makedirs(self.state, exist_ok=True)

    def write(self, name: str, payload: dict) -> None:
        with open(os.path.join(self.state, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def test_first_ingest_has_nothing_to_compare(self):
        self.write("source-inventory.json", {"packages": {}})
        self.assertIn("首次 ingest", self.chapters._source_change_line())

    def test_an_identical_inventory_reads_as_unchanged(self):
        self.write("source-inventory.json", {"packages": {"a": 1}})
        self.write("source-inventory.prev.json", {"packages": {"a": 1}})
        self.assertIn("无变化", self.chapters._source_change_line())

    def test_a_moved_inventory_reads_as_changed(self):
        self.write("source-inventory.json", {"packages": {"a": 2}})
        self.write("source-inventory.prev.json", {"packages": {"a": 1}})
        self.assertIn("已变化", self.chapters._source_change_line())


if __name__ == "__main__":
    unittest.main()
