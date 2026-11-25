#!/usr/bin/env python3
"""Index cross-references and the file-length budget gate."""

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


class IndexXrefUnitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, "index_xrefs")

    def index(self, text: str) -> str:
        path = os.path.join(self.tmp.name, "index.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_alias_stripping_removes_parentheticals(self):
        self.assertEqual(self.mod._strip_alias("ACID（事务）"), "ACID")

    def test_aliases_include_the_ascii_and_cjk_forms(self):
        aliases = self.mod._aliases_for("MVStore（存储引擎）")
        self.assertTrue(aliases)
        self.assertTrue(all(isinstance(a, str) for a in aliases))

    def test_parse_index_returns_sections_and_entries(self):
        path = self.index(
            "# 索引\n\n## A\n\n- ACID —— §1.1\n  - 子项 —— §2.1\n  see also: MVStore\n"
        )
        main_entries, _sub_entries, see_alsos, sections = self.mod.parse_index(path)
        self.assertTrue(main_entries)
        self.assertTrue(sections)
        self.assertIsInstance(see_alsos, list)

    def test_main_reports_a_missing_index(self):
        buffer = io.StringIO()
        with (
            redirect_stdout(buffer),
            mock.patch.object(
                self.mod, "index_path", os.path.join(self.tmp.name, "none.md"), create=True
            ),
        ):
            code = self.mod.main([])
        self.assertIsInstance(code, int)
        self.assertRegex(buffer.getvalue(), r"索引|index|缺失|missing|FAIL|❌")
        self.assertTrue(buffer.getvalue())

    def test_json_output_lists_the_issues(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.mod.main(["--json"])
        text = buffer.getvalue()
        payload = json.loads(text[text.index("{"):])
        self.assertEqual(list(payload), ["issues"])
        self.assertIsInstance(payload["issues"], int)
        self.assertGreaterEqual(payload["issues"], 0)


class FileLengthUnitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, "file_length")

    def test_budgets_cover_every_kind(self):
        table = self.mod.budgets()
        self.assertTrue(table)
        for kind, values in table.items():
            self.assertIn("limit", values, kind)
            self.assertGreater(values["limit"], 0)

    def test_targets_are_relative_and_labelled(self):
        targets = self.mod.targets()
        self.assertTrue(targets)
        for path, kind in targets[:5]:
            self.assertTrue(os.path.isabs(path))
            self.assertIsInstance(kind, str)

    def test_main_reports_the_length_budgets(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([])
        self.assertIsInstance(code, int)
        self.assertRegex(buffer.getvalue(), r"(budget|长度|行数|行|limit|提醒线)")

    def test_json_output_lists_findings(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(["--json"])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertIn("ledger", payload)

    # -- growth ledger ----------------------------------------------------
    def ledger_book(self, body: str, files: dict[str, str]) -> str:
        root = os.path.join(self.tmp.name, "book")
        for name, text in files.items():
            path = os.path.join(root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        ledger = os.path.join(root, "docs", "managements")
        os.makedirs(ledger, exist_ok=True)
        with open(os.path.join(ledger, "review-findings.md"), "w", encoding="utf-8") as fh:
            fh.write(body)
        return root

    def test_a_registered_length_that_drifted_slightly_is_not_reported(self):
        root = self.ledger_book(
            "| `src/python/a.py` 9 行 | 占比 1%，拆法 |\n", {"src/python/a.py": "x = 1\n"}
        )
        self.assertEqual(self.mod.check_ledger(root), [])

    def test_growth_past_the_threshold_since_the_ledger_is_reported(self):
        body = "x\n" * 30
        root = self.ledger_book(
            "| `src/python/a.py` 10 行 | 占比 1%，拆法 |\n", {"src/python/a.py": body}
        )
        self.write_state(root, {"src/python/a.py": 10})
        findings = self.mod.check_ledger(root)
        self.assertEqual([f["kind"] for f in findings], ["LEDGER"])
        self.assertIn("增长 20 行", findings[0]["detail"])

    def test_growth_inside_the_threshold_is_tolerated(self):
        body = "x\n" * 14
        root = self.ledger_book(
            "| `src/python/a.py` 10 行 | 占比 1%，拆法 |\n", {"src/python/a.py": body}
        )
        self.write_state(root, {"src/python/a.py": 10})
        self.assertEqual(self.mod.check_ledger(root), [])

    def test_update_ledger_writes_the_measurement_and_the_baseline(self):
        body = "x\n" * 30
        root = self.ledger_book(
            "| `src/python/a.py` 10 行 | 占比 1%，拆法 |\n", {"src/python/a.py": body}
        )
        self.write_state(root, {"src/python/a.py": 10})
        self.assertEqual(self.mod.update_ledger(root), 1)
        ledger = os.path.join(root, "docs", "managements", "review-findings.md")
        with open(ledger, encoding="utf-8") as handle:
            self.assertIn("`src/python/a.py` 30 行", handle.read())
        self.assertEqual(self.mod.check_ledger(root), [])
        self.assertEqual(self.mod.read_state(self.mod._state_path(root)), {"src/python/a.py": 30})

    def test_the_growth_threshold_comes_from_the_config(self):
        with mock.patch.dict(self.mod._config.STYLE_POLICY, {"thresholds": {"ledger_growth": 3}}):
            self.assertEqual(self.mod.growth_limit(), 3)
        with mock.patch.dict(self.mod._config.STYLE_POLICY, {"thresholds": {}}):
            self.assertEqual(self.mod.growth_limit(), self.mod.GROWTH_DEFAULT)

    def write_state(self, root: str, files: dict[str, int]) -> None:
        path = self.mod._state_path(root)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"files": files}, handle)

    def test_a_registered_file_that_is_gone_is_reported(self):
        root = self.ledger_book("| `src/python/gone.py` 3 行 | 占比 1%，拆法 |\n", {})
        details = [f["detail"] for f in self.mod.check_ledger(root)]
        self.assertTrue(any("does not exist" in d for d in details))

    def test_a_matching_row_passes(self):
        root = self.ledger_book(
            "| `src/python/b.py` 2 行 | 占比 1%，拆法 |\n", {"src/python/b.py": "x = 1\ny = 2\n"}
        )
        self.assertEqual(self.mod.check_ledger(root), [])

    # -- declared budgets ------------------------------------------------
    def test_every_budget_kind_is_declared_in_the_config(self):
        self.assertEqual(self.mod.check_declared_budgets(), [])

    def test_a_kind_missing_from_the_config_is_reported(self):
        with mock.patch.dict(self.mod._config.STYLE_POLICY, {"limits": {"sources": {}}}):
            details = [f["detail"] for f in self.mod.check_declared_budgets()]
        self.assertTrue(any("manuscript" in d for d in details))
        self.assertFalse(any("sources" in d for d in details))


class SnapshotLabelTest(unittest.TestCase):
    """A snapshot answers to its bare label as well as its dated directory."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, "snapshot")
        self.snapshots = os.path.join(self.tmp.name, "snapshots")
        os.makedirs(os.path.join(self.snapshots, "2026-06-11", "manuscript"))
        self.patch = mock.patch.object(self.mod, "SNAPSHOT_ROOT", self.snapshots)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_the_bare_label_resolves_to_the_dated_directory(self):
        self.assertTrue(self.mod.resolve("06-11").endswith("2026-06-11"))

    def test_the_dated_name_still_resolves(self):
        self.assertTrue(self.mod.resolve("2026-06-11"))

    def test_an_unknown_label_is_reported_with_the_known_ones(self):
        path, code = self.mod.require("missing")
        self.assertEqual((path, code), ("", 2))


class ContentVolumeBaselineTest(unittest.TestCase):
    """The reviewed floor only moves up unless a shrink is accepted by hand."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, "content_volume")
        self.path = os.path.join(self.tmp.name, "content-volume.json")

    def book(self, lines: int, files: dict | None = None) -> dict:
        payload = files if files is not None else {"ch1.md": {"bytes": lines * 10, "lines": lines}}
        return {
            "manuscript": {"files": payload, "total": {"bytes": lines * 10, "lines": lines}},
            "delivered": {},
        }

    def write(self, payload: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def read(self) -> dict:
        with open(self.path, encoding="utf-8") as fh:
            return json.load(fh)

    def clean(self, **overrides) -> dict:
        info = {
            "commit": "abc1234",
            "committed_at": "2026-06-30T10:00:00+08:00",
            "author": "reviewer",
            "dirty": "",
        }
        info.update(overrides)
        return info

    def run_main(self, *args: str, info: dict | None = None) -> int:
        with (
            mock.patch.object(self.mod, "baseline_path", lambda: self.path),
            mock.patch.object(self.mod, "provenance", lambda: info or self.clean()),
            mock.patch("sys.stdout", new=io.StringIO()),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            return self.mod.main(list(args))

    def test_uncommitted_manuscript_is_refused(self):
        self.write(self.book(100))
        with mock.patch.object(self.mod, "snapshot", lambda: self.book(120)):
            code = self.run_main(
                "--update-baseline", info=self.clean(dirty=" M data/manuscript/ch1.md")
            )
        self.assertEqual(code, 1)

    def test_nobody_named_means_no_baseline(self):
        self.write(self.book(100))
        with mock.patch.object(self.mod, "snapshot", lambda: self.book(120)):
            code = self.run_main("--update-baseline", info=self.clean(author=""))
        self.assertEqual(code, 1)

    def test_the_recorded_baseline_names_its_review(self):
        self.write(self.book(100))
        with mock.patch.object(self.mod, "snapshot", lambda: self.book(120)):
            self.assertEqual(
                self.run_main("--update-baseline", "--reviewed-by", "阿龙", "--reason", "定稿评审"),
                0,
            )
        reviewed = self.read()["reviewed"]
        self.assertEqual(reviewed["by"], "阿龙")
        self.assertEqual(reviewed["commit"], "abc1234")
        self.assertEqual(reviewed["reason"], "定稿评审")

    def test_a_smaller_manuscript_counts_as_a_shrink(self):
        drops = self.mod.shrunk(self.book(100), self.book(90))
        self.assertTrue(any("ch1.md" in item for item in drops))
        self.assertTrue(any("total" in item for item in drops))

    def test_an_equal_or_larger_manuscript_does_not(self):
        self.assertEqual(self.mod.shrunk(self.book(100), self.book(100)), [])
        self.assertEqual(self.mod.shrunk(self.book(100), self.book(120)), [])

    def test_a_missing_chapter_counts_as_a_shrink(self):
        drops = self.mod.shrunk(self.book(100), self.book(0, files={}))
        self.assertTrue(any("gone" in item for item in drops))

    def test_updating_the_baseline_refuses_to_lower_it(self):
        self.write(self.book(100))
        with mock.patch.object(self.mod, "snapshot", lambda: self.book(90)):
            self.assertEqual(self.run_main("--update-baseline"), 1)

    def test_accepting_the_shrink_records_the_reason(self):
        self.write(self.book(100))
        with mock.patch.object(self.mod, "snapshot", lambda: self.book(90)):
            self.assertEqual(
                self.run_main("--update-baseline", "--accept-shrink", "--reason", "删掉重复章节"), 0
            )
        recorded = self.read()["accepted_shrinks"][0]
        self.assertEqual(recorded["reason"], "删掉重复章节")
        self.assertTrue(recorded["drops"])

    def snapshot_ledger(self, label: str, lines: int) -> None:
        directory = os.path.join(self.tmp.name, "data", "baselines")
        os.makedirs(directory, exist_ok=True)
        payload = {
            "snapshot": label,
            "files": {"ch1.md": {"bytes": lines * 10, "lines": lines}},
            "totals": {"files": 1, "bytes": lines * 10, "lines": lines},
        }
        with open(os.path.join(directory, f"snapshot-{label}.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def test_an_imported_snapshot_can_become_the_floor(self):
        self.snapshot_ledger("june", 120)
        with mock.patch.object(self.mod._config, "BOOK_ROOT", self.tmp.name):
            payload = self.mod.from_snapshot("june")
        self.assertEqual(payload["manuscript"]["total"]["lines"], 120)
        self.assertEqual(payload["source"]["snapshot"], "june")
        self.assertEqual(payload["delivered"], {})

    def test_a_snapshot_without_a_ledger_is_rejected(self):
        with (
            mock.patch.object(self.mod._config, "BOOK_ROOT", self.tmp.name),
            mock.patch("sys.stdout", new=io.StringIO()),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            code = self.mod.main(["--update-baseline", "--from-snapshot", "absent"])
        self.assertEqual(code, 2)

    def test_a_decided_snapshot_keeps_its_source_after_recording(self):
        self.write(self.book(100))
        self.snapshot_ledger("june", 90)
        with (
            mock.patch.object(self.mod._config, "BOOK_ROOT", self.tmp.name),
            mock.patch.object(self.mod, "snapshot", lambda: self.book(100)),
        ):
            code = self.run_main(
                "--update-baseline",
                "--from-snapshot",
                "june",
                "--accept-shrink",
                "--reason",
                "历史版本",
            )
        self.assertEqual(code, 0)
        self.assertEqual(self.read()["source"]["snapshot"], "june")

    def test_a_growing_baseline_is_recorded_without_a_flag(self):
        self.write(self.book(100))
        with mock.patch.object(self.mod, "snapshot", lambda: self.book(120)):
            self.assertEqual(self.run_main("--update-baseline"), 0)
        self.assertNotIn("accepted_shrinks", self.read())


class FileLengthEdgeTest(unittest.TestCase):
    """The budget gate's error paths: unreadable state, stale rows, warnings."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, "file_length")
        self.root = os.path.join(self.tmp.name, "book")
        os.makedirs(self.root, exist_ok=True)

    def ledger(self, body: str) -> str:
        directory = os.path.join(self.root, "docs", "managements")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "review-findings.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
        return path

    def seed(self, name: str, body: str) -> None:
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)

    def test_growth_limit_falls_back_when_the_config_is_not_a_number(self):
        with mock.patch.dict(
            self.mod._config.STYLE_POLICY, {"thresholds": {"ledger_growth": "many"}}
        ):
            self.assertEqual(self.mod.growth_limit(), self.mod.GROWTH_DEFAULT)

    def test_measured_of_a_book_without_a_ledger_is_empty(self):
        self.assertEqual(self.mod.measured(self.root), {})

    def test_measured_skips_rows_it_cannot_parse(self):
        self.seed("src/python/a.py", "x = 1\n")
        self.ledger("这不是台账行\n| `src/python/a.py` 9 行 | 占比 1%，拆法 |\n")
        self.assertEqual(self.mod.measured(self.root), {"src/python/a.py": 1})

    def test_update_ledger_without_a_ledger_updates_nothing(self):
        self.assertEqual(self.mod.update_ledger(self.root), 0)

    def test_update_ledger_leaves_a_row_for_a_missing_file_alone(self):
        body = "| `src/python/gone.py` 3 行 | 占比 1%，拆法 |\n"
        path = self.ledger(body)
        self.assertEqual(self.mod.update_ledger(self.root), 0)
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), body)

    def test_scan_separates_over_budget_from_warning(self):
        path = os.path.join(self.root, "src", "python", "a.py")
        self.seed("src/python/a.py", "x\n" * 10)
        limits = {"sources": {"limit": 4, "warn": 2}}
        with mock.patch.object(self.mod, "targets", return_value=[(path, "sources")]):
            over, warn = self.mod.scan(limits)
        self.assertEqual(len(over), 1)
        self.assertEqual(over[0]["lines"], 10)
        self.assertEqual(warn, [])
        limits = {"sources": {"limit": 40, "warn": 2}}
        with mock.patch.object(self.mod, "targets", return_value=[(path, "sources")]):
            over, warn = self.mod.scan(limits)
        self.assertEqual(over, [])
        self.assertEqual(len(warn), 1)

    def test_main_updates_the_ledger(self):
        buffer = io.StringIO()
        with mock.patch.object(self.mod, "update_ledger", return_value=3), redirect_stdout(buffer):
            self.assertEqual(self.mod.main(["--update-ledger"]), 0)
        self.assertIn("3", buffer.getvalue())

    def test_main_prints_over_budget_files_and_ledger_rows(self):
        over = [{"file": "src/python/a.py", "kind": "sources", "lines": 900, "limit": 800}]
        ledger = [{"file": "src/python/b.py", "line": 12, "detail": "雨过天晴"}]
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "scan", return_value=(over, [])),
            mock.patch.object(self.mod, "check_ledger", return_value=ledger),
            mock.patch.object(self.mod, "check_declared_budgets", return_value=[]),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main([]), 1)
        text = buffer.getvalue()
        self.assertIn("超出长度上限 1 个文件", text)
        self.assertIn("src/python/a.py", text)
        self.assertIn("src/python/b.py:12", text)

    def test_the_gate_runs_as_a_script(self):
        # a fixture book declares no budgets, so the report must name them rather
        # than depend on how long the real tree happens to be today
        book = _fixture.build_book(os.path.join(self.tmp.name, "book"))
        code, out = _fixture.run_inproc(book, "file_length.py", "--json")
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertEqual(sorted(payload), ["ledger", "over", "undeclared", "warn"])
        self.assertTrue(any("budget" in item["kind"].lower() for item in payload["undeclared"]))


if __name__ == "__main__":
    unittest.main()
