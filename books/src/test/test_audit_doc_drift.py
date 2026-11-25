#!/usr/bin/env python3
"""Doc drift: paths, script names, chapter names, config keys and levels."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))


class DocDriftTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.drift = _fixture.load_module(self.root, "doc_drift")
        self.real_root = BOOK_ROOT

    def doc(self, text: str) -> str:
        path = os.path.join(self.tmp.name, "doc.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def management_doc(self, text: str, name: str = "testplan.md") -> str:
        directory = os.path.join(self.tmp.name, "docs", "managements")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    # -- paths ------------------------------------------------------------
    def test_missing_path_is_reported(self):
        path = self.doc("见 `books/no-such-file.md` 一节。\n")
        findings = self.drift.check_paths([path])
        self.assertTrue(findings)
        self.assertEqual(findings[0]["kind"], "PATH")

    def test_existing_path_is_accepted(self):
        path = self.doc("见 `books/README.md`。\n")
        self.assertEqual(self.drift.check_paths([path], os.path.dirname(BOOK_ROOT)), [])

    def test_a_gitignored_path_counts_as_present(self):
        path = self.doc("日志在 `books/logs/` 下。\n")
        with mock.patch.object(self.drift, "_git_ignored", lambda rel: True):
            self.assertEqual(self.drift.check_paths([path]), [])

    def test_illustrative_paths_are_skipped(self):
        path = self.doc("例如 `books/…/x.md` 或 `<name>`。\n")
        self.assertEqual(self.drift.check_paths([path]), [])

    def test_glob_paths_are_checked_by_expansion(self):
        path = self.doc("见 `books/src/python/*.py`。\n")
        self.assertEqual(self.drift.check_paths([path], os.path.dirname(BOOK_ROOT)), [])

    # -- scripts ----------------------------------------------------------
    def test_unknown_script_is_reported(self):
        path = self.doc("运行 `no_such_script.py`。\n")
        findings = self.drift.check_scripts([path])
        self.assertEqual(findings[0]["kind"], "SCRIPT")

    def test_known_script_is_accepted(self):
        path = self.doc("运行 `make.py`。\n")
        self.assertEqual(self.drift.check_scripts([path], BOOK_ROOT), [])

    # -- chapters ---------------------------------------------------------
    def test_unknown_chapter_reference_is_reported(self):
        path = self.doc("见 `ch99-missing.md`。\n")
        findings = self.drift.check_chapters([path])
        self.assertEqual(findings[0]["kind"], "CHAPTER")

    def test_unconfigured_chapter_is_reported(self):
        self.drift._config.MANUSCRIPT_DIR = os.path.join(self.root, "data", "manuscript")
        path = self.doc("见 `ch99-missing.md`。\n")
        self.assertTrue(self.drift.check_chapters([path]))

    def test_a_chapter_name_outside_back_ticks_is_reported(self):
        # a directory tree names files the same way prose does
        path = self.doc("```text\n  ch99-missing.md\n```\n")
        findings = self.drift.check_chapters([path])
        self.assertEqual([f["kind"] for f in findings], ["CHAPTER"])

    # -- config -----------------------------------------------------------
    def test_chapter_table_key_outside_the_chapter_list_is_reported(self):
        with (
            mock.patch.object(self.drift._config, "chapter_names", return_value=["ch1-test.md"]),
            mock.patch.object(
                self.drift._config,
                "chapter_table",
                side_effect=lambda name: {"ch9-gone.md": [1]} if name == "packages" else {},
            ),
        ):
            findings = self.drift.check_config()
        self.assertEqual([f["kind"] for f in findings], ["CONFIG"])
        self.assertIn("ch9-gone.md", findings[0]["detail"])

    def test_chapter_tables_matching_the_chapter_list_pass(self):
        with (
            mock.patch.object(self.drift._config, "chapter_names", return_value=["ch1-test.md"]),
            mock.patch.object(
                self.drift._config, "chapter_table", side_effect=lambda name: {"ch1-test.md": [1]}
            ),
        ):
            self.assertEqual(self.drift.check_config(), [])

    # -- levels -----------------------------------------------------------
    def test_level_inside_the_owning_table_passes(self):
        path = self.management_doc(
            "### 2.2 各检查项及其级别\n\n"
            "| 类别 | 说明 | 级别 |\n| --- | --- | --- |\n"
            "| 章节结构 | 齐全 | P0 |\n"
        )
        self.assertEqual(self.drift.check_levels([path]), [])

    def test_level_table_outside_the_owning_sections_is_reported(self):
        path = self.management_doc(
            "### 2.2 各检查项及其级别\n\n"
            "| 类别 | 级别 |\n| --- | --- |\n"
            "| 章节结构 | P0 |\n\n"
            "## 7. 门禁等级\n\n"
            "| 级别 | 检查项 |\n| --- | --- |\n"
            "| P0 | 章节结构。 |\n"
        )
        findings = self.drift.check_levels([path])
        self.assertEqual([f["kind"] for f in findings], ["LEVEL"])

    def test_another_document_never_declares_a_level(self):
        path = self.management_doc("| P0 | 章节结构 |\n", name="plan.md")
        self.assertEqual([f["kind"] for f in self.drift.check_levels([path])], ["LEVEL"])

    # -- management registries ---------------------------------------
    def management_dir(self, **bodies: str) -> str:
        directory = os.path.join(self.tmp.name, "managements")
        os.makedirs(directory, exist_ok=True)
        for name, body in bodies.items():
            path = os.path.join(directory, name.replace("_", ".") + ".md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
        return directory

    def test_a_document_missing_from_the_tree_is_reported(self):
        directory = self.management_dir(folder="  folder.py   # 树\n", changelog="# 变更日志\n")
        details = [f["detail"] for f in self.drift.check_managements(directory)]
        self.assertTrue(any("changelog.md" in d for d in details))

    def test_a_tree_row_registered_twice_is_reported(self):
        directory = self.management_dir(folder="  folder.md   # 树\n  folder.md   # 又一遍\n")
        kinds = [f["kind"] for f in self.drift.check_managements(directory)]
        self.assertIn("INDEX", kinds)

    def test_a_tree_naming_a_missing_document_is_reported(self):
        directory = self.management_dir(folder="  folder.md   # 树\n  gone.md     # 已删\n")
        details = [f["detail"] for f in self.drift.check_managements(directory)]
        self.assertTrue(any("gone.md" in d for d in details))

    # -- numbering ----------------------------------------------------
    def test_a_stale_next_number_is_reported(self):
        path = self.doc("plan-5 已用。\n\n**编号源**：`plan-next = 5`\n")
        findings = self.drift.check_numbering([path])
        self.assertEqual([f["kind"] for f in findings], ["NUMBERING"])
        self.assertIn("expected 6", findings[0]["detail"])

    def test_a_matching_next_number_passes(self):
        path = self.doc("plan-3 已用。\n\n**编号源**：`plan-next = 4`\n")
        other = self.doc("rf-7 已修。\n\n**编号源**：`rf-next = 8`\n")
        self.assertEqual(self.drift.check_numbering([path, other]), [])

    # -- quoted pipelines and prefix lists ----------------------------
    def test_a_shorter_delivery_pipeline_is_reported(self):
        steps = ["to_pdf", "pdf_toc_links", "verify_pdf", "to_epub", "verify_epub"]
        path = self.doc("| `deliver` | `to_pdf` + `verify_pdf` + `verify_epub` |\n")
        findings = self.drift.check_deliver([path], steps)
        self.assertEqual([f["kind"] for f in findings], ["DELIVER"])
        self.assertIn("pdf_toc_links", findings[0]["detail"])

    def test_the_declared_delivery_pipeline_passes(self):
        steps = ["to_pdf", "verify_pdf", "to_epub"]
        path = self.doc("| `deliver` | `to_pdf` + `verify_pdf` + `to_epub` |\n")
        self.assertEqual(self.drift.check_deliver([path], steps), [])

    def test_a_subset_prefix_list_is_reported(self):
        path = self.doc("只允许 `check`、`eval` 两类前缀。\n")
        findings = self.drift.check_prefixes([path], ["check", "eval", "new", "release"])
        self.assertEqual([f["kind"] for f in findings], ["PREFIX"])
        self.assertIn("new", findings[0]["detail"])

    def test_the_full_prefix_list_passes(self):
        path = self.doc("只允许 `check`、`eval` 两类前缀。\n")
        self.assertEqual(self.drift.check_prefixes([path], ["check", "eval"]), [])

    def test_wrapper_prefixes_are_read_in_either_quote_style(self):
        real = _fixture.load_module(BOOK_ROOT, "doc_drift")
        source = (
            '"""d"""\n\ndef check_scripts():\n'
            '    allowed = (\n        "bookctl",\n        "check",\n    )\n'
        )
        self.assertEqual(real.script_prefixes(source), ["bookctl", "check"])

    def test_the_orchestrator_is_the_source_of_both_lists(self):
        real = _fixture.load_module(BOOK_ROOT, "doc_drift")
        self.assertIn("to_pdf", real.deliver_steps())
        self.assertIn("bookctl", real.script_prefixes())

    # -- locus ------------------------------------------------------------
    def test_a_document_without_a_locus_line_is_reported(self):
        directory = self.management_dir(README="# 索引\n", folder="# 目录\n")
        kinds = [f["kind"] for f in self.drift.check_locus(directory)]
        self.assertEqual(kinds, ["LOCUS", "LOCUS"])

    def test_a_locus_line_in_the_header_passes(self):
        directory = self.management_dir(README="# 索引\n\n> 定位：登记职责\n")
        self.assertEqual(self.drift.check_locus(directory), [])

    def test_a_locus_line_far_down_the_file_does_not_count(self):
        directory = self.management_dir(README="# 索引\n" + "\n" * 20 + "> 定位：登记职责\n")
        self.assertEqual([f["kind"] for f in self.drift.check_locus(directory)], ["LOCUS"])

    # -- portable content standard ------------------------------------
    def test_a_standard_naming_a_script_is_reported(self):
        path = self.doc("运行 `make.py` 判。\n")
        self.assertEqual([f["kind"] for f in self.drift.check_standard(path)], ["STANDARD"])

    def test_a_standard_naming_a_gate_table_is_reported(self):
        path = self.doc("判据见 testplan.md。\n")
        findings = self.drift.check_standard(path)
        self.assertIn("testplan", findings[0]["detail"])

    def test_a_standard_naming_a_config_file_is_reported(self):
        path = self.doc("阈值在 `style.json` 里。\n")
        self.assertEqual([f["kind"] for f in self.drift.check_standard(path)], ["STANDARD"])

    def test_a_standard_pointing_at_its_writing_twin_passes(self):
        path = self.doc("写法见 how-to-write.md §12。\n")
        self.assertEqual(self.drift.check_standard(path), [])

    # -- criteria cite properties ----------------------------------------
    def test_a_criteria_row_citing_a_config_key_is_reported(self):
        path = self.management_doc("| 索引完整性 | 每章条数不低于 `index_per_chapter_min` | P1 |\n")
        findings = self.drift.check_threshold_keys([path], {"index_per_chapter_min"})
        self.assertEqual([f["kind"] for f in findings], ["THRESHOLD"])

    def test_a_criteria_row_stating_the_property_passes(self):
        path = self.management_doc("| 索引完整性 | 每章条数不低于配置下限 | P1 |\n")
        self.assertEqual(self.drift.check_threshold_keys([path], {"index_per_chapter_min"}), [])

    def test_prose_outside_the_table_may_name_a_gate(self):
        path = self.management_doc("合并原则：`captions`/`figures` 都看图。\n")
        self.assertEqual(self.drift.check_threshold_keys([path], {"captions"}), [])

    def test_the_repository_cites_no_config_key_in_its_criteria(self):
        self.assertEqual(self.drift.check_threshold_keys([]), [])

    # -- CLI --------------------------------------------------------------
    def test_json_output_reports_the_count(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.drift.main(["--json"])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertIn("count", payload)

    def test_human_output_states_the_verdict(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.drift.main([])
        self.assertIsInstance(code, int)
        self.assertRegex(buffer.getvalue(), r"✅|❌|WARN|FAIL|OK|通过|失败")
        self.assertTrue(buffer.getvalue())


class PlanTreeNamingTest(unittest.TestCase):
    """Iteration designs live in docs/plan/<topic>/ and are named after the topic."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.drift = _fixture.load_module(self.root, "doc_drift")

    def topic(self, name, *files):
        folder = os.path.join(self.root, "docs", "plan", name)
        os.makedirs(folder, exist_ok=True)
        for entry in files or ("plan.md",):
            with open(os.path.join(folder, entry), "w", encoding="utf-8") as fh:
                fh.write("# title\n")

    def details(self):
        return [item["detail"] for item in self.drift.check_plan_tree(self.root)]

    def test_a_semantic_topic_directory_passes(self):
        self.topic("diagram-upgrade", "design.md", "plan.md")
        self.assertEqual(self.details(), [])

    def test_absent_plan_root_is_not_an_error(self):
        self.assertEqual(self.details(), [])

    def test_a_numbered_directory_is_reported(self):
        self.topic("plan-6", "plan.md")
        self.assertTrue(any("语义名" in detail for detail in self.details()))

    def test_a_numbered_file_is_reported(self):
        self.topic("diagram-upgrade", "plan-6-plan.md", "plan.md")
        self.assertTrue(any("文件名" in detail for detail in self.details()))

    def test_a_topic_without_a_plan_is_reported(self):
        self.topic("diagram-upgrade", "design.md")
        self.assertTrue(any("缺少 plan.md" in detail for detail in self.details()))

    def test_a_stray_file_at_the_root_is_reported(self):
        os.makedirs(os.path.join(self.root, "docs", "plan"), exist_ok=True)
        with open(os.path.join(self.root, "docs", "plan", "notes.md"), "w", encoding="utf-8") as fh:
            fh.write("# x\n")
        self.assertTrue(any("只放主题目录" in detail for detail in self.details()))

    def test_an_unexpected_document_name_is_reported(self):
        self.topic("diagram-upgrade", "misc.md", "plan.md")
        self.assertTrue(any("只允许" in detail for detail in self.details()))


class ProjectNameTest(unittest.TestCase):
    """The docs describe the tool, not the project it happens to analyse."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.drift = _fixture.load_module(self.root, "doc_drift")

    def doc(self, name: str, text: str) -> str:
        path = os.path.join(self.root, "docs", "managements", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_the_package_prefix_in_a_management_doc_is_reported(self):
        path = self.doc("requirements.md", "包前缀 `org.h2` 不得出现在管理文档里。\n")
        with mock.patch.dict(self.drift._config.SOURCES, {"package_prefix": "org.h2"}):
            findings = self.drift.check_project_names([path])
        self.assertEqual([f["kind"] for f in findings], ["PROJECT"])
        self.assertIn("org.h2", findings[0]["detail"])

    def test_the_ledgers_and_the_worked_example_may_name_the_project(self):
        files = [
            self.doc(name, "org.h2 是本次分析的对象。\n")
            for name in ("changelog.md", "review-findings.md", "how-to-new-book.md")
        ]
        with mock.patch.dict(self.drift._config.SOURCES, {"package_prefix": "org.h2"}):
            self.assertEqual(self.drift.check_project_names(files), [])

    def test_a_manual_page_without_the_name_is_clean(self):
        path = os.path.join(self.root, "docs", "manuals", "how-to-use.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("运行 `make.py check`，产物在 `dist/<book>.pdf`。\n")
        with mock.patch.dict(self.drift._config.SOURCES, {"package_prefix": "org.h2"}):
            self.assertEqual(self.drift.check_project_names([path]), [])


class ManualScopeTest(unittest.TestCase):
    """Manuals declare one dimension each, and never quote the design documents."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.drift = _fixture.load_module(self.root, "doc_drift")
        self.directory = os.path.join(self.tmp.name, "manuals")
        os.makedirs(self.directory, exist_ok=True)

    def manual(self, name: str, body: str) -> str:
        path = os.path.join(self.directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
        return path

    def test_a_manual_without_a_dimension_is_reported(self):
        self.manual("a.md", "# 无维度\n正文。\n")
        details = [f["detail"] for f in self.drift.check_manual_scope(self.directory)]
        self.assertTrue(any("维度" in detail for detail in details))

    def test_two_manuals_sharing_a_dimension_are_reported(self):
        self.manual("a.md", "# A\n\n> 维度：配置\n")
        self.manual("b.md", "# B\n\n> 维度：配置\n")
        details = [f["detail"] for f in self.drift.check_manual_scope(self.directory)]
        self.assertTrue(any("duplicates" in detail for detail in details))

    def test_a_manual_quoting_a_management_document_is_reported(self):
        self.manual("a.md", "# A\n\n> 维度：配置\n\n见 ../managements/testplan.md\n")
        details = [f["detail"] for f in self.drift.check_manual_scope(self.directory)]
        self.assertTrue(any("design docs" in detail for detail in details))

    def test_a_clean_manual_passes(self):
        self.manual("a.md", "# A\n\n> 维度：配置\n\n只看本文。\n")
        self.assertEqual(self.drift.check_manual_scope(self.directory), [])


if __name__ == "__main__":
    unittest.main()


class DriftConfigurationAndExitTest(unittest.TestCase):
    """The style-key check, and the two verdict exits of the gate."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.drift = _fixture.load_module(BOOK_ROOT, "doc_drift")

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_a_style_key_nobody_explains_is_reported(self):
        self.write(
            "data/config/style.json",
            json.dumps({"limits": {"sources": {"limit": 800}}}, ensure_ascii=False),
        )
        self.write("docs/manuals/how-to-config.md", "# 配置\n\n## limits\n")
        details = [item["detail"] for item in self.drift.check_style_keys(self.root)]
        self.assertTrue(any("'sources'" in detail for detail in details), details)

    def test_private_sections_and_keys_are_ignored(self):
        self.write(
            "data/config/style.json",
            json.dumps({"_note": "x", "limits": {"_draft": 1}}, ensure_ascii=False),
        )
        self.write("docs/manuals/how-to-config.md", "# 配置\n\n## limits\n")
        self.assertEqual(self.drift.check_style_keys(self.root), [])

    def test_an_unreadable_style_file_is_skipped(self):
        self.write("data/config/style.json", "{not json")
        self.write("docs/manuals/how-to-config.md", "# 配置\n")
        self.assertEqual(self.drift.check_style_keys(self.root), [])

    def test_main_prints_the_drift_and_exits_one(self):
        buffer = io.StringIO()
        finding = {"kind": "PATH", "file": "docs/x.md", "line": 3, "detail": "src/nowhere.py"}
        with (
            mock.patch.object(self.drift, "doc_files", return_value=[]),
            mock.patch.object(self.drift, "check_paths", return_value=[finding]),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.drift.main([]), 1)
        self.assertIn("src/nowhere.py", buffer.getvalue())
