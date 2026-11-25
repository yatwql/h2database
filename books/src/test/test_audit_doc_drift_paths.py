#!/usr/bin/env python3
"""doc_drift.py: the paths a document is allowed to take and the ledgers it may name.

Each case gives one check the input that makes it skip rather than report: an
unreadable directory, a generated path, a ledger document quoting an old name, a
row that names something the configuration really has.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()


class DriftCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.drift = _fixture.load_module(self.root, "doc_drift")

    def doc(self, text: str, name: str = "doc.md", folder: str = "") -> str:
        path = (
            os.path.join(self.root, folder, name) if folder else os.path.join(self.tmp.name, name)
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path


class PlanTreeReadErrorTest(DriftCase):
    def test_a_topic_directory_that_cannot_be_listed_is_one_finding(self):
        topic = os.path.join(self.root, "docs", "plan", "unreadable")
        os.makedirs(topic)
        real = os.listdir

        def listdir(path):
            if os.path.abspath(str(path)) == os.path.abspath(topic):
                raise OSError("denied")
            return real(path)

        with mock.patch.object(self.drift.os, "listdir", side_effect=listdir):
            details = [item["detail"] for item in self.drift.check_plan_tree(self.root)]
        self.assertEqual(len(details), 1)
        self.assertIn("cannot read", details[0])

    def test_a_plan_root_that_cannot_be_listed_is_one_finding(self):
        root = os.path.join(self.root, "docs", "plan")
        os.makedirs(root)
        with mock.patch.object(self.drift.os, "listdir", side_effect=OSError("denied")):
            findings = self.drift.check_plan_tree(self.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("cannot read", findings[0]["detail"])


class GeneratedPathTest(DriftCase):
    def test_a_built_artifact_is_not_a_missing_file(self):
        built = self.drift._generated_prefixes()[0] + "test-book.html"
        self.assertTrue(self.drift._exists(built))

    def test_the_generated_directory_itself_counts_as_present(self):
        directory = self.drift._generated_prefixes()[0].rstrip("/")
        self.assertTrue(self.drift._exists(directory))

    def test_a_book_relative_path_is_asked_of_git_with_the_book_directory(self):
        asked = []

        def ignored(rel):
            asked.append(rel)
            return True

        with mock.patch.object(self.drift, "_git_ignored", side_effect=ignored):
            self.assertTrue(self.drift._exists("src/python/not-there.py"))
        self.assertEqual(asked, [f"{os.path.basename(self.root)}/src/python/not-there.py"])


class LedgerDocumentTest(DriftCase):
    def test_the_changelog_may_quote_a_shorter_delivery_pipeline(self):
        path = self.doc("`to_pdf` → `verify_pdf`\n", name="changelog.md")
        self.assertEqual(self.drift.check_deliver([path], ["to_pdf", "verify_pdf", "to_epub"]), [])

    def test_the_changelog_may_quote_an_old_prefix_list(self):
        path = self.doc(
            "只允许 `books/scripts/` 下的 `check-*` 前缀，历史如此。\n", name="changelog.md"
        )
        self.assertEqual(self.drift.check_prefixes([path], ["check", "eval"]), [])

    def test_an_old_chapter_name_in_the_ledger_is_left_alone(self):
        path = self.doc("`ch99-removed.md` 已删除。\n", name="review-findings.md")
        self.assertEqual(self.drift.check_chapters([path]), [])

    def test_a_configured_chapter_that_exists_is_not_reported(self):
        path = self.doc("见 `ch1-test.md` 与 `ch2-test.md`。\n")
        self.assertEqual(self.drift.check_chapters([path]), [])


class PrefixClaimTest(DriftCase):
    def test_a_sentence_that_is_not_about_prefixes_is_ignored(self):
        path = self.doc("只允许把这段文字放在手册里，不涉及脚本。\n")
        self.assertEqual(self.drift.check_prefixes([path], ["check", "eval"]), [])


class ThresholdKeyTest(DriftCase):
    def test_a_repository_without_config_keys_has_nothing_to_compare(self):
        self.assertEqual(self.drift.check_threshold_keys([], set()), [])

    def test_only_the_testplan_owns_the_criteria_table(self):
        path = self.doc("| 通过标准 | `coverage_fail_under` |\n", name="design.md")
        self.assertEqual(self.drift.check_threshold_keys([path], {"coverage_fail_under"}), [])

    def test_a_row_naming_a_key_is_reported_and_other_tokens_are_not(self):
        path = self.doc(
            "| 通过标准 | `coverage_fail_under` |\n| 判据 | `some_gate` |\n", name="testplan.md"
        )
        findings = self.drift.check_threshold_keys([path], {"coverage_fail_under"})
        self.assertEqual(len(findings), 1)
        self.assertIn("coverage_fail_under", findings[0]["detail"])

    def test_the_two_policy_files_supply_the_key_universe(self):
        keys = self.drift.config_keys()
        self.assertIn("coverage_fail_under", keys)


class ProjectNameScopeTest(DriftCase):
    def test_a_book_configuring_no_project_name_checks_nothing(self):
        with mock.patch.object(self.drift, "_project_names", return_value=[]):
            self.assertEqual(self.drift.check_project_names([self.doc("x\n")]), [])

    def test_a_document_outside_the_manuals_is_not_about_the_project(self):
        path = self.doc("org.h2 的入口在 Engine.java。\n")
        with mock.patch.object(self.drift, "_project_names", return_value=["org.h2"]):
            self.assertEqual(self.drift.check_project_names([path]), [])

    def test_a_sources_declaration_without_a_prefix_still_reads_the_title(self):
        with mock.patch.object(
            self.drift._config,
            "project",
            side_effect=lambda key, default: "测试之书" if key == "title" else default,
        ):
            self.assertIn("测试之书", self.drift._project_names())


class IllustrativePathTest(DriftCase):
    def test_a_path_written_with_three_dots_is_illustrative(self):
        path = self.doc("见 `books/.../x.md`。\n")
        self.assertEqual(self.drift.check_paths([path]), [])


class LevelScopeTest(DriftCase):
    def test_a_table_outside_the_managements_directory_is_not_a_level(self):
        path = self.doc("| 检查项 | P1 |\n", name="notes.md", folder="docs/plan/topic")
        self.assertEqual(self.drift.check_levels([path]), [])


class EntryPointTest(DriftCase):
    def test_the_gate_runs_as_a_script(self):
        code, out = _fixture.run_inproc(self.root, "doc_drift.py", "--json")
        payload = json.loads(out)
        self.assertEqual(code, 0 if payload["count"] == 0 else 1)
        self.assertIn("findings", payload)


if __name__ == "__main__":
    unittest.main()
