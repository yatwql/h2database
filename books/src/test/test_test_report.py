#!/usr/bin/env python3
"""Test reports: what a run writes, what pruning keeps, what `last` pulls out."""

from __future__ import annotations

import datetime
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:infra", "tier:fast")

_fixture.ensure_tools_path()

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="3" failures="1" errors="0" skipped="1">
  <testcase classname="src.test.test_alpha.AlphaTest" name="test_ok" time="0.01" />
  <testcase classname="src.test.test_alpha.AlphaTest" name="test_bad" time="0.02">
    <failure message="AssertionError: boom">traceback</failure>
  </testcase>
  <testcase classname="src.test.test_beta.BetaTest" name="test_skip" time="0.0">
    <skipped message="not here" />
  </testcase>
</testsuite></testsuites>
"""


class DispatchTableTest(unittest.TestCase):
    """Every subcommand the parser offers has a handler in the table."""

    def setUp(self):
        self.mod = _fixture.load_module(_fixture.build_book(tempfile.mkdtemp()), "test_report")

    def test_the_dispatch_table_covers_every_subcommand(self):
        parser = self.mod._parser()
        actions = [action for action in parser._actions if action.dest == "command"]
        self.assertTrue(actions)
        offered = set(actions[0].choices)
        self.assertEqual(offered, set(self.mod.COMMANDS))

    def test_each_handler_answers_with_an_exit_code(self):
        self.assertEqual(self.mod._cmd_list(), 0)


class ReportToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.tool = _fixture.load_module(self.root, "test_report")
        self.addCleanup(setattr, self.tool, "TESTS_DIR", self.tool.TESTS_DIR)

    # -- policy and layout ------------------------------------------------
    def test_settings_fall_back_to_the_defaults(self):
        settings = self.tool.settings()
        self.assertEqual(settings["dir"], "test-reports")
        self.assertGreaterEqual(settings["retention_days"], 1)

    def test_settings_ignore_a_bad_retention(self):
        with mock.patch.dict(self.tool._config.POLICY, {"reports": {"retention_days": "x"}}):
            self.assertEqual(self.tool.settings()["retention_days"], 30)

    def test_reports_root_sits_under_the_book(self):
        self.assertTrue(self.tool.reports_root().startswith(self.root))

    def test_no_reports_means_no_pointer(self):
        self.assertEqual(self.tool.report_dirs(), [])
        self.assertIsNone(self.tool.newest_report())

    def test_the_pointer_wins_over_disk_order(self):
        os.makedirs(os.path.join(self.tool.reports_root(), "20260101-000000"))
        os.makedirs(os.path.join(self.tool.reports_root(), "20260102-000000"))
        with open(self.tool.latest_pointer(), "w", encoding="utf-8") as fh:
            json.dump({"dir": "20260101-000000"}, fh)
        self.assertTrue(self.tool.newest_report().endswith("20260101-000000"))

    def test_a_broken_pointer_falls_back_to_the_newest_directory(self):
        os.makedirs(os.path.join(self.tool.reports_root(), "20260102-000000"))
        with open(self.tool.latest_pointer(), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertTrue(self.tool.newest_report().endswith("20260102-000000"))

    # -- parsing ----------------------------------------------------------
    def junit(self) -> str:
        path = os.path.join(self.root, "junit.xml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(JUNIT)
        return path

    def test_cases_come_with_outcomes_and_messages(self):
        cases, totals = self.tool._cases(self.junit())
        self.assertEqual([case["outcome"] for case in cases], ["pass", "fail", "skip"])
        self.assertEqual(cases[1]["message"], "AssertionError: boom")
        self.assertEqual(totals, {"tests": 3, "failures": 1, "errors": 0, "skipped": 1})

    def test_a_missing_junit_is_not_fatal(self):
        self.assertEqual(self.tool._cases(os.path.join(self.root, "nope.xml")), ([], {}))

    def test_a_case_carrying_only_a_log_child_is_a_pass(self):
        path = os.path.join(self.root, "logged.xml")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(
                "<testsuites><testsuite>"
                '<testcase classname="src.test.test_x.X" name="t" time="0.5">'
                "<system-out>print output</system-out>"
                "</testcase></testsuite></testsuites>"
            )
        cases, totals = self.tool._cases(path)
        self.assertEqual([case["outcome"] for case in cases], ["pass"])
        self.assertEqual(cases[0]["message"], "")
        self.assertEqual(totals["tests"], 1)

    def test_the_module_of_a_case_is_its_test_file(self):
        self.assertEqual(
            self.tool._module_of("src.test.test_alpha.AlphaTest::test_ok"), "test_alpha"
        )

    def test_median_handles_odd_and_even_lists(self):
        self.assertEqual(self.tool._median([1.0, 3.0, 2.0]), 2.0)
        self.assertEqual(self.tool._median([1.0, 4.0]), 2.5)

    def test_html_is_escaped(self):
        self.assertEqual(self.tool._escape("<a>&"), "&lt;a&gt;&amp;")

    # -- writing ----------------------------------------------------------
    def test_the_three_report_files_are_written(self):
        target = os.path.join(self.root, "report")
        summary = {
            "stamp": "20260101-000000",
            "marker": "tier_fast",
            "code": 1,
            "seconds": 1.5,
            "totals": {"tests": 1, "failures": 1},
            "machine": "test",
            "log": os.path.join(target, "pytest.log"),
        }
        cases = [{"id": "a::b", "outcome": "fail", "seconds": 0.1, "message": "AssertionError"}]
        self.tool._write_reports(target, summary, cases)
        for name in ("report.json", "report.md", "report.html"):
            self.assertTrue(os.path.isfile(os.path.join(target, name)), name)
        with open(os.path.join(target, "report.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["cases"], cases)
        with open(os.path.join(target, "report.html"), encoding="utf-8") as fh:
            self.assertIn("失败", fh.read())

    def test_a_green_report_says_so(self):
        target = os.path.join(self.root, "green")
        summary = {
            "stamp": "stamp",
            "marker": "m",
            "code": 0,
            "seconds": 0.1,
            "totals": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0},
            "machine": "test",
            "log": "x",
        }
        self.tool._write_reports(
            target, summary, [{"id": "a", "outcome": "pass", "seconds": 0.0, "message": ""}]
        )
        with open(os.path.join(target, "report.md"), encoding="utf-8") as fh:
            self.assertIn("无。", fh.read())

    # -- run --------------------------------------------------------------
    def fake_pytest(self, code: int = 0, junit_text: str = JUNIT):
        def runner(command, **_kwargs):
            for argument in command:
                if argument.startswith("--junitxml="):
                    with open(argument.split("=", 1)[1], "w", encoding="utf-8") as fh:
                        fh.write(junit_text)
            return subprocess.CompletedProcess(command, code, "", "")

        return runner

    def test_a_run_writes_the_report_and_the_pointer(self):
        with mock.patch.object(self.tool.subprocess, "run", side_effect=self.fake_pytest()):
            summary = self.tool.run("tier_fast")
        self.assertEqual(summary["code"], 0)
        self.assertTrue(os.path.isfile(os.path.join(summary["dir"], "report.json")))
        self.assertTrue(os.path.isfile(self.tool.latest_pointer()))

    def test_a_run_without_a_marker_adds_no_marker_option(self):
        seen: list[list[str]] = []

        def runner(command, **_kwargs):
            seen.append(list(command))
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(self.tool.subprocess, "run", side_effect=runner):
            self.tool.run("")
        # `python -m pytest` already carries one `-m`; a marker adds the second
        self.assertEqual([arg for arg in seen[0] if arg == "-m"], ["-m"])
        self.assertNotIn("tier_fast", seen[0])

    def test_a_timed_out_run_is_recorded_as_124(self):
        expired = subprocess.TimeoutExpired(["x"], 1)
        with mock.patch.object(self.tool.subprocess, "run", side_effect=expired):
            summary = self.tool.run("tier_fast", timeout=1)
        self.assertEqual(summary["code"], 124)

    # -- last -------------------------------------------------------------
    def test_last_reports_only_failures_and_a_rerun_command(self):
        target = os.path.join(self.tool.reports_root(), "20260101-000000")
        os.makedirs(target)
        payload = {
            "cases": [
                {
                    "id": "src.test.test_alpha.AlphaTest::test_bad",
                    "outcome": "fail",
                    "message": "x",
                },
                {"id": "src.test.test_beta.BetaTest::test_skip", "outcome": "skip", "message": ""},
            ]
        }
        with open(os.path.join(target, "report.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        found = self.tool.last_failures(target)
        self.assertEqual(len(found["failures"]), 1)
        self.assertIn("test_alpha.py", found["rerun"])

    def test_last_without_reports_is_empty(self):
        self.assertEqual(self.tool.last_failures()["failures"], [])

    # -- prune ------------------------------------------------------------
    def test_prune_drops_old_directories_only(self):
        root = self.tool.reports_root()
        for name in ("20200101-000000", datetime.datetime.now().strftime("%Y%m%d-%H%M%S")):
            os.makedirs(os.path.join(root, name), exist_ok=True)
        removed = self.tool.prune()
        self.assertIn("20200101-000000", removed)
        self.assertFalse(os.path.isdir(os.path.join(root, "20200101-000000")))

    def test_prune_ignores_a_dated_name_that_is_not_a_stamp(self):
        root = self.tool.reports_root()
        odd = os.path.join(root, "20200101-notastamp")
        os.makedirs(odd, exist_ok=True)
        self.assertEqual(self.tool.prune(), [])
        self.assertTrue(os.path.isdir(odd))

    def test_a_dry_run_prune_keeps_everything(self):
        root = self.tool.reports_root()
        os.makedirs(os.path.join(root, "20200101-000000"), exist_ok=True)
        self.assertIn("20200101-000000", self.tool.prune(dry_run=True))
        self.assertTrue(os.path.isdir(os.path.join(root, "20200101-000000")))

    # -- collect ----------------------------------------------------------
    def test_collect_counts_cases_from_the_declarations(self):
        tests = os.path.join(self.root, "src", "test")
        os.makedirs(tests, exist_ok=True)
        with open(os.path.join(tests, "test_fast_sample.py"), "w", encoding="utf-8") as fh:
            fh.write(
                "TAGS = ('layer:infra', 'tier:fast')\n"
                "import unittest\n"
                "class FastTest(unittest.TestCase):\n"
                "    def test_a(self): pass\n"
                "    def test_b(self): pass\n"
            )
        with open(os.path.join(tests, "test_slow_sample.py"), "w", encoding="utf-8") as fh:
            fh.write(
                "TAGS = ('layer:render', 'tier:slow')\n"
                "import unittest\n"
                "class SlowTest(unittest.TestCase):\n"
                "    def test_c(self): pass\n"
            )
        with mock.patch.object(self.tool, "TESTS_DIR", tests):
            payload = self.tool.collect()
        self.assertEqual(payload["counts"]["fast"], 2)
        self.assertEqual(payload["counts"]["slow"], 1)
        self.assertTrue(os.path.isfile(payload["path"]))

    # -- perf -------------------------------------------------------------
    def history(self, runs: list[dict]) -> str:
        path = os.path.join(self.root, "logs", "perf-history.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            for run in runs:
                fh.write(json.dumps(run) + "\n")
        return path

    def test_perf_compares_the_latest_run_with_the_median(self):
        self.history(
            [
                {"seconds": 10.0, "steps": [{"step": "gates", "seconds": 4.0}]},
                {"seconds": 12.0, "steps": [{"step": "gates", "seconds": 6.0}]},
                {"seconds": 60.0, "steps": [{"step": "gates", "seconds": 40.0}]},
            ]
        )
        payload = self.tool.perf_window(20)
        self.assertEqual(payload["runs"], 3)
        row = payload["steps"][0]
        self.assertEqual(row["median"], 5.0)
        self.assertTrue(row["regressed"])

    def test_perf_needs_two_runs(self):
        self.history([{"seconds": 3.0, "steps": [{"step": "gates", "seconds": 3.0}]}])
        self.assertEqual(self.tool.perf_window(20)["steps"], [])

    def test_perf_without_a_history_file_has_nothing_to_compare(self):
        payload = self.tool.perf_window(20)
        self.assertEqual(payload["runs"], 0)
        self.assertEqual(payload["steps"], [])

    def test_perf_ignores_a_run_it_cannot_parse(self):
        path = self.history(
            [
                {"seconds": 1.0, "steps": [{"step": "gates", "seconds": 1.0}]},
                {"seconds": 2.0, "steps": [{"step": "gates", "seconds": 2.0}]},
            ]
        )
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("{not json\n")
        self.assertEqual(self.tool.perf_window(20)["runs"], 2)

    def test_a_blank_history_line_never_reaches_the_json_parser(self):
        path = self.history(
            [
                {"seconds": 1.0, "steps": [{"step": "gates", "seconds": 1.0}]},
                {"seconds": 2.0, "steps": [{"step": "gates", "seconds": 2.0}]},
            ]
        )
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n   \n")
        with mock.patch.object(self.tool.json, "loads", wraps=json.loads) as loads:
            payload = self.tool.perf_window(20)
        self.assertEqual(payload["runs"], 2)
        # the blank line is dropped before parsing, so it never reaches json.loads
        parsed = [call.args[0] for call in loads.call_args_list]
        self.assertEqual([text for text in parsed if not text.strip()], [])

    # -- CLI --------------------------------------------------------------
    def cli(self, *args: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.tool.main(list(args))
        return code, buffer.getvalue()

    def test_cli_list_and_prune(self):
        os.makedirs(os.path.join(self.tool.reports_root(), "20260101-000000"), exist_ok=True)
        code, out = self.cli("list")
        self.assertEqual(code, 0)
        self.assertIn("20260101-000000", out)
        code, out = self.cli("prune", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("过期报告", out)

    def test_cli_last_without_reports_explains_itself(self):
        code, out = self.cli("last")
        self.assertEqual(code, 2)
        self.assertIn("test_report.py run", out)

    def test_cli_last_json_and_failure_exit(self):
        target = os.path.join(self.tool.reports_root(), "20260101-000000")
        os.makedirs(target)
        with open(os.path.join(target, "report.json"), "w", encoding="utf-8") as fh:
            json.dump(
                {"cases": [{"id": "src.test.test_x.X::t", "outcome": "fail", "message": "boom"}]},
                fh,
            )
        with open(self.tool.latest_pointer(), "w", encoding="utf-8") as fh:
            json.dump({"dir": "20260101-000000"}, fh)
        code, out = self.cli("last", "--json")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["failures"][0]["message"], "boom")

    def test_cli_collect_and_perf(self):
        with mock.patch.object(
            self.tool, "collect", return_value={"counts": {"fast": 1}, "path": "p"}
        ):
            code, out = self.cli("collect")
        self.assertEqual(code, 0)
        self.assertIn("fast", out)
        with mock.patch.object(
            self.tool,
            "perf_window",
            return_value={
                "runs": 2,
                "total": 1.0,
                "steps": [{"step": "gates", "seconds": 2.0, "median": 1.0, "regressed": True}],
            },
        ):
            code, out = self.cli("perf")
        self.assertEqual(code, 0)
        self.assertIn("回退", out)

    def test_a_coverage_snapshot_records_every_file(self):
        payload = json.dumps(
            {
                "files": {
                    "books/src/python/thin.py": {
                        "summary": {"num_statements": 20, "percent_covered": 61.5}
                    },
                    "books/src/python/tiny.py": {
                        "summary": {"num_statements": 2, "percent_covered": 0.0}
                    },
                }
            }
        )

        def fake_run(command, **_kwargs):
            return subprocess.CompletedProcess(command, 0, payload, "")

        with mock.patch.object(self.tool.subprocess, "run", side_effect=fake_run):
            snapshot = self.tool.coverage_snapshot(timeout=5)
        values = {key: value for key, value in snapshot["files"].items() if key.endswith("thin.py")}
        self.assertEqual(list(values.values()), [61.5])  # the small file is filtered out
        self.assertTrue(os.path.isfile(snapshot["path"]))

    def test_a_slow_fast_case_is_flagged(self):
        target = os.path.join(self.root, "slow")
        summary = {
            "stamp": "stamp",
            "marker": "tier_fast",
            "code": 0,
            "seconds": 1.0,
            "totals": {"tests": 1, "failures": 0, "errors": 0, "skipped": 0},
            "machine": "m",
            "log": "x",
        }
        cases = [
            {"id": "src.test.test_x.X::slow", "outcome": "pass", "seconds": 2.5, "message": ""}
        ]
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.tool._write_reports(target, summary, cases)
        self.assertIn("超过", buffer.getvalue())

    def test_cli_run_forwards_and_reports_the_exit_code(self):
        summary = {"code": 1, "dir": os.path.join(self.root, "r"), "totals": {}, "seconds": 1.0}
        with mock.patch.object(self.tool, "run", return_value=summary):
            code, out = self.cli("run")
        self.assertEqual(code, 1)
        self.assertIn("report ->", out)


class ReportEdgePathTest(unittest.TestCase):
    """The reporter's own failure paths: bad XML, broken modules, failed deletes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "test_report")

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.tmp.name, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_a_case_listed_twice_is_counted_once(self):
        junit = self.write(
            "first.xml",
            JUNIT.replace(
                "</testsuite>",
                '<testcase classname="src.test.test_alpha.AlphaTest" name="test_ok" /></testsuite>',
            ),
        )
        cases, totals = self.mod._cases(junit)
        self.assertEqual(totals["tests"], 3)
        self.assertEqual(len({case["id"] for case in cases}), 3)

    def test_a_coverage_snapshot_that_cannot_run_is_empty(self):
        with mock.patch.object(self.mod.subprocess, "run", side_effect=OSError("nope")):
            snapshot = self.mod.coverage_snapshot(5)
        self.assertEqual(snapshot["files"], {})
        self.assertEqual(snapshot["path"], "")

    def test_collect_skips_a_module_it_cannot_parse_and_counts_classes(self):
        tests = os.path.join(self.tmp.name, "tests")
        self.write("tests/test_broken.py", "def (:\n")
        self.write(
            "tests/test_untagged.py",
            'TAGS = ("tier:fast",) + EXTRA\n\ndef test_a(): pass\ndef test_b(): pass\n',
        )
        self.write(
            "tests/test_classy.py",
            'TAGS = ("tier:slow",)\n\nclass TestThing:\n    def test_a(self): pass\n',
        )
        with mock.patch.object(self.mod, "TESTS_DIR", tests):
            payload = self.mod.collect()
        self.assertEqual(sorted(payload["files"]), ["test_classy.py", "test_untagged.py"])
        self.assertEqual(payload["files"]["test_untagged.py"]["tests"], 2)
        # a method inside a Test class is one case, not two
        self.assertEqual(payload["files"]["test_classy.py"]["tests"], 1)
        self.assertEqual(payload["counts"]["untiered"], 2)

    def test_prune_ignores_names_that_are_not_stamps_and_warns_on_delete(self):
        reports = os.path.join(self.tmp.name, "reports")
        old = "20000101-000000"
        os.makedirs(os.path.join(reports, old))
        os.makedirs(os.path.join(reports, "not-a-stamp"))
        with (
            mock.patch.object(self.mod, "reports_root", lambda: reports),
            mock.patch.object(self.mod.shutil, "rmtree", side_effect=OSError("busy")),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            removed = self.mod.prune()
        self.assertEqual(removed, [old])

    def test_a_case_id_without_a_module_falls_back_to_its_class(self):
        self.assertEqual(self.mod._module_of("pkg.AlphaTest::test_ok"), "AlphaTest")
        self.assertEqual(self.mod._module_of(""), "")

    def test_cli_run_reports_the_coverage_snapshot_it_wrote(self):
        summary = {
            "dir": self.tmp.name,
            "seconds": 1.0,
            "code": 0,
            "totals": {"tests": 1, "failures": 0},
        }
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "run", return_value=summary),
            mock.patch.object(
                self.mod,
                "coverage_snapshot",
                return_value={
                    "path": os.path.join(self.tmp.name, "c.json"),
                    "files": {},
                    "stamp": "x",
                },
            ),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main(["run", "--coverage", "--marker", "tier_fast"]), 0)
        self.assertIn("coverage ->", buffer.getvalue())

    def test_cli_collect_and_perf_speak_json(self):
        buffer = io.StringIO()
        with (
            mock.patch.object(
                self.mod, "collect", return_value={"counts": {"fast": 1}, "path": self.tmp.name}
            ),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main(["collect", "--json"]), 0)
        with (
            mock.patch.object(self.mod, "perf_window", return_value={"steps": []}),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main(["perf"]), 0)
        with (
            mock.patch.object(
                self.mod, "perf_window", return_value={"steps": [], "runs": 0, "total": 0.0}
            ),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main(["perf", "--json"]), 0)
        self.assertIn("没有足够的历史数据", buffer.getvalue())

    def test_cli_last_prints_the_failures_and_the_rerun_command(self):
        payload = {
            "report": "r1",
            "failures": [{"id": "test_a", "reason": "boom"}],
            "rerun": "pytest books/src/test/test_a.py",
        }
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "last_failures", return_value=payload),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main(["last"]), 1)
        text = buffer.getvalue()
        self.assertIn("test_a", text)
        self.assertIn("只重跑这些模块", text)

    def test_a_coverage_run_that_wrote_no_snapshot_stays_quiet(self):
        buffer = io.StringIO()
        with (
            mock.patch.object(
                self.mod,
                "run",
                return_value={"dir": self.tmp.name, "seconds": 1.0, "code": 0, "totals": {}},
            ),
            mock.patch.object(
                self.mod, "coverage_snapshot", return_value={"path": "", "files": {}, "stamp": "x"}
            ),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main(["run", "--coverage"]), 0)
        self.assertNotIn("coverage ->", buffer.getvalue())

    def test_cli_perf_prints_no_delta_for_a_step_without_a_median(self):
        payload = {
            "runs": 2,
            "total": 2.0,
            "steps": [{"step": "gates", "seconds": 2.0, "median": None, "regressed": False}],
        }
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "perf_window", return_value=payload),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main(["perf"]), 0)
        self.assertIn(f"  {'gates':<18}{2.0:>7.1f}s  \n", buffer.getvalue())

    def test_cli_last_on_a_clean_report_exits_zero(self):
        payload = {"report": "r1", "failures": [], "rerun": ""}
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "last_failures", return_value=payload),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main(["last"]), 0)
        self.assertIn("没有失败用例。", buffer.getvalue())

    def test_cli_last_omits_the_rerun_command_when_no_module_is_named(self):
        payload = {"report": "r1", "failures": [{"id": "test_a", "reason": "boom"}], "rerun": ""}
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "last_failures", return_value=payload),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main(["last"]), 1)
        self.assertIn("test_a", buffer.getvalue())
        self.assertNotIn("只重跑这些模块", buffer.getvalue())

    def test_the_tool_runs_as_a_script(self):
        code, out = _fixture.run_inproc(self.root, "test_report.py", "collect")
        self.assertEqual(code, 0)
        self.assertTrue(out.strip())


if __name__ == "__main__":
    unittest.main()
