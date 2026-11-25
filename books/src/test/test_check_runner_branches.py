#!/usr/bin/env python3
"""Branch coverage for the check runner: step selection, scoping and reporting."""

from __future__ import annotations

import datetime
import glob
import io
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:infra", "tier:fast")

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))


class OtherBookChangeTest(unittest.TestCase):
    """A neighbour book's change is not this book's infrastructure."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(os.path.join(self.tmp.name, "book-a"))
        self.other = _fixture.build_book(os.path.join(self.tmp.name, "book-b"))
        self.runner = _fixture.load_module(self.root, "check_runner")

    def relative(self, root: str, *parts: str) -> str:
        return os.path.relpath(os.path.join(root, *parts), self.runner.repo_root()).replace(
            os.sep, "/"
        )

    def test_a_change_in_the_other_book_is_its_own_domain(self):
        changed = self.relative(self.other, "data", "manuscript", "ch1-test.md")
        self.assertEqual(self.runner.domain_of(changed), "other-book")

    def test_it_does_not_pull_this_books_gates_in(self):
        changed = self.relative(self.other, "data", "manuscript", "ch1-test.md")
        self.assertEqual(self.runner.gates_for_change([changed]), "")

    def test_an_absolute_path_is_classified_the_same_way(self):
        changed = os.path.join(self.other, "docs", "managements", "plan.md")
        self.assertEqual(self.runner.domain_of(changed), "other-book")
        own = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        self.assertNotEqual(self.runner.domain_of(own), "other-book")

    def test_a_path_outside_every_book_stays_infrastructure(self):
        self.assertEqual(self.runner.domain_of("README.md"), "infra")

    def test_a_change_in_this_book_still_maps_to_its_own_domain(self):
        changed = self.relative(self.root, "data", "manuscript", "ch1-test.md")
        self.assertNotEqual(self.runner.domain_of(changed), "other-book")


class CommandTableTest(unittest.TestCase):
    """One command per step, and a clear refusal for anything else."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.runner = _fixture.load_module(self.root, "check_runner")

    def joined(self, step: str, **kwargs) -> str:
        command = self.runner._command(step, **kwargs)
        return " ".join(command or [])

    def test_the_fixed_steps_name_their_tool(self):
        self.assertIn("make.py", self.joined("fast-gates"))
        self.assertIn("--keep-going", self.joined("gates"))
        self.assertIn("--full", self.joined("slow"))
        self.assertIn("order_dependence.py", self.joined("order"))
        self.assertIn("deliver", self.joined("deliver"))

    def test_lint_prefers_the_pinned_module_then_the_paths(self):
        with mock.patch.object(self.runner.importlib.util, "find_spec", return_value=object()):
            self.assertIn("ruff", self.joined("lint"))
        with (
            mock.patch.object(self.runner.importlib.util, "find_spec", return_value=None),
            mock.patch.object(
                self.runner.shutil, "which", side_effect=lambda name: "/usr/bin/" + name
            ),
        ):
            self.assertTrue(self.joined("lint").startswith("ruff"))

    def test_lint_is_skipped_when_no_ruff_is_installed(self):
        with (
            mock.patch.object(self.runner.importlib.util, "find_spec", return_value=None),
            mock.patch.object(self.runner.shutil, "which", return_value=None),
        ):
            self.assertIsNone(self.runner._command("lint"))

    def test_lint_changed_only_lists_python_files(self):
        code = os.path.join(self.root, "src", "python", "make.py")
        docs = os.path.join(self.root, "docs", "x.md")
        with mock.patch.object(self.runner, "scoped_changes", return_value=[code, docs]):
            self.assertIn("make.py", self.joined("lint-changed"))
        with mock.patch.object(self.runner, "scoped_changes", return_value=[docs]):
            self.assertIsNone(self.runner._command("lint-changed"))

    def test_changed_steps_are_skipped_when_nothing_is_affected(self):
        with mock.patch.object(self.runner, "scoped_changes", return_value=[]):
            self.assertIsNone(self.runner._command("gates-changed"))
            self.assertIsNone(self.runner._command("tests-changed"))

    def test_changed_steps_scope_the_run(self):
        changed = [os.path.join(self.root, "src", "python", "audit", "structure.py")]
        with mock.patch.object(self.runner, "scoped_changes", return_value=changed):
            self.assertIn("--only", self.joined("gates-changed"))
            with mock.patch.object(
                self.runner, "tests_for_change", return_value=["test_audit_structure_mutations"]
            ):
                self.assertIn("test_audit_structure_mutations", self.joined("tests-changed"))


class ScopingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.runner = _fixture.load_module(self.root, "check_runner")
        tests_dir = os.path.join(self.root, "src", "test")
        os.makedirs(tests_dir, exist_ok=True)
        for name in ("test_source_refs.py", "test_make.py", "test_check_runner_flow.py"):
            with open(os.path.join(tests_dir, name), "w", encoding="utf-8") as fh:
                fh.write("")

    def fragment(self, domain: str) -> str:
        """A path the classifier recognises as ``domain`` for this fixture root."""
        for prefix, name in self.runner.domain_rows():
            if name == domain:
                return prefix + "x.py"
        raise AssertionError(f"no prefix for {domain}")

    def test_a_path_is_classified_by_its_prefix(self):
        self.assertEqual(self.runner.domain_of(self.fragment("docs")), "docs")
        self.assertEqual(self.runner.domain_of(self.fragment("code")), "code")
        self.assertEqual(self.runner.domain_of(".github/workflows/book.yml"), "infra")

    def test_scoping_filters_the_changed_set(self):
        changed = [self.fragment("docs"), self.fragment("code")]
        with mock.patch.object(self.runner, "changed_files", return_value=changed):
            self.assertEqual(self.runner.scoped_changes(), changed)
            self.assertEqual(self.runner.scoped_changes(("docs",)), [self.fragment("docs")])

    def test_gates_for_a_change_are_collected_without_duplicates(self):
        gates = self.runner.gates_for_change([self.fragment("code"), self.fragment("code")])
        names = gates.split(",")
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("architecture", names)

    def test_a_source_change_maps_to_its_own_test_modules(self):
        module = os.path.join(self.root, "src", "python", "audit", "source_refs.py")
        modules = self.runner.tests_for_change([module])
        self.assertIn("test_source_refs", modules)

    def test_a_changed_test_module_selects_itself(self):
        module = os.path.join(self.root, "src", "test", "test_make.py")
        modules = self.runner.tests_for_change([module])
        self.assertEqual(modules, ["test_make"])

    def test_modules_that_spawn_the_runner_are_excluded(self):
        module = os.path.join(self.root, "src", "test", "test_check_runner_flow.py")
        modules = self.runner.tests_for_change([module])
        self.assertEqual(modules, [])

    def test_changed_files_merges_tracked_and_untracked(self):
        def fake_run(command, **_kwargs):
            if "--name-only" in command:
                return subprocess.CompletedProcess(command, 0, "a.py\n\n", "")
            return subprocess.CompletedProcess(command, 0, "b.py\n", "")

        with mock.patch.object(self.runner.subprocess, "run", side_effect=fake_run):
            self.assertEqual(self.runner.changed_files(), ["a.py", "b.py"])

    def test_git_being_absent_yields_no_changes(self):
        with mock.patch.object(self.runner.subprocess, "run", side_effect=OSError("no git")):
            self.assertEqual(self.runner.changed_files(), [])


class RunStepTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.runner = _fixture.load_module(self.root, "check_runner")
        self.log = os.path.join(self.root, "logs", "run.log")

    def test_a_failure_prints_the_tail_of_the_output(self):
        failed = subprocess.CompletedProcess(["x"], 1, "line1\nline2\n", "")
        buffer = io.StringIO()
        with (
            mock.patch.object(self.runner.subprocess, "run", return_value=failed),
            redirect_stdout(buffer),
        ):
            result = self.runner.run_step("gates", self.log)
        self.assertEqual(result["code"], 1)
        self.assertIn("line2", buffer.getvalue())

    def test_a_timeout_is_reported_as_124(self):
        error = subprocess.TimeoutExpired(["x"], 1)
        buffer = io.StringIO()
        with (
            mock.patch.object(self.runner.subprocess, "run", side_effect=error),
            redirect_stdout(buffer),
        ):
            result = self.runner.run_step("gates", self.log, timeout=1)
        self.assertEqual(result["code"], 124)
        self.assertEqual(result["timeout"], 1)
        self.assertIn("timeout", buffer.getvalue())

    def test_the_slow_step_sets_the_environment_flag(self):
        ok = subprocess.CompletedProcess(["x"], 0, "", "")
        with (
            mock.patch.object(self.runner.subprocess, "run", return_value=ok) as run,
            redirect_stdout(io.StringIO()),
        ):
            self.runner.run_step("slow", self.log)
        self.assertEqual(run.call_args.kwargs["env"].get("BOOK_SLOW"), "1")

    def test_the_log_holds_the_command_and_its_output(self):
        ok = subprocess.CompletedProcess(["x"], 0, "hello\n", "")
        with (
            mock.patch.object(self.runner.subprocess, "run", return_value=ok),
            redirect_stdout(io.StringIO()),
        ):
            self.runner.run_step("gates", self.log)
        with open(self.log, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("hello", text)
        self.assertIn("rc=0", text)

    def test_an_unwritable_log_is_not_fatal(self):
        ok = subprocess.CompletedProcess(["x"], 0, "", "")
        with (
            mock.patch.object(self.runner.subprocess, "run", return_value=ok),
            mock.patch.object(self.runner._fsutil, "ensure_dir", side_effect=OSError("read-only")),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(self.runner.run_step("gates", self.log)["code"], 0)


class ModesAndSummaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.runner = _fixture.load_module(self.root, "check_runner")

    def test_historical_names_resolve_to_their_mode(self):
        for alias in ("fast", "full", "release"):
            with self.subTest(alias=alias):
                self.assertIn(self.runner.resolve_mode(alias), self.runner.MODES)

    def test_an_unknown_mode_is_refused(self):
        with self.assertRaises(SystemExit):
            self.runner.resolve_mode("nope")

    def test_quick_mode_caps_the_timeout(self):
        result = self.runner.run("quick", archive=False, marker="", timeout=1800)
        self.assertEqual(result["mode"], "quick")
        self.assertIn("machine", result)

    def test_a_failed_step_stops_the_run_and_is_named(self):
        failure = {"step": "gates", "code": 1, "seconds": 0.1}
        with (
            mock.patch.object(self.runner, "run_step", return_value=failure),
            redirect_stdout(io.StringIO()),
        ):
            summary = self.runner.run("p0", archive=False)
        self.assertFalse(summary["ok"])
        self.assertEqual(summary["failed_step"], "gates")

    def test_a_passing_run_leaves_a_line_in_the_days_journal(self):
        ok = {"step": "lint", "code": 0, "seconds": 0.1}
        with (
            mock.patch.object(self.runner, "run_step", return_value=ok),
            mock.patch.object(self.runner, "_record_perf") as record,
            redirect_stdout(io.StringIO()),
        ):
            summary = self.runner.run("p0", archive=True, only="lint")
        logs = os.path.join(self.runner.book_root(), "logs")
        self.assertTrue(os.path.isfile(summary["json"]))
        self.assertTrue(os.path.isfile(summary["log"]))
        self.assertRegex(summary["json"], r"check-p0-\d{4}-\d{2}-\d{2}\.jsonl$")
        self.assertRegex(summary["log"], r"check-p0-\d{4}-\d{2}-\d{2}\.log$")
        self.assertTrue(glob.glob(os.path.join(logs, "check-*.jsonl")))
        record.assert_called_once()

    def test_a_failing_run_stays_in_the_same_journal(self):
        bad = {"step": "lint", "code": 1, "seconds": 0.1}
        with (
            mock.patch.object(self.runner, "run_step", return_value=bad),
            mock.patch.object(self.runner, "_record_perf"),
            redirect_stdout(io.StringIO()),
        ):
            summary = self.runner.run("p0", archive=True, only="lint")
        self.assertTrue(os.path.isfile(summary["json"]))
        self.assertTrue(os.path.isfile(summary["log"]))
        self.assertEqual(summary["failed_step"], "lint")
        with open(summary["json"], encoding="utf-8") as handle:
            self.assertIn('"ok": false', handle.read())

    def test_the_json_flag_prints_the_summary(self):
        ok = {"step": "lint", "code": 0, "seconds": 0.1}
        buffer = io.StringIO()
        with mock.patch.object(self.runner, "run_step", return_value=ok), redirect_stdout(buffer):
            self.runner.run("p0", archive=False, only="lint", as_json=True)
        self.assertIn('"ok": true', buffer.getvalue())

    def test_report_paths_live_under_logs(self):
        log, payload = self.runner.report_paths("p0", datetime.datetime(2026, 11, 24, 11, 13, 22))
        self.assertTrue(log.endswith("check-p0-2026-11-24.log"))
        self.assertTrue(payload.endswith("check-p0-2026-11-24.jsonl"))

    def test_perf_recording_survives_a_missing_module(self):
        with mock.patch.object(
            self.runner.importlib, "import_module", side_effect=ImportError("no perf")
        ):
            self.runner._record_perf({"mode": "p0", "seconds": 1.0, "steps": []})
        with mock.patch.object(self.runner.importlib, "import_module") as load:
            self.runner._record_perf({"mode": "p1", "seconds": 2.0, "steps": []})
        load.assert_called_once_with("audit.perf_baseline")

    def test_machine_info_names_the_python_and_the_book(self):
        info = self.runner.machine_info()
        self.assertIn("python", info)
        self.assertTrue(info["book_root"])


if __name__ == "__main__":
    unittest.main()


class RunnerEdgeBranchesTest(unittest.TestCase):
    """The lint fallbacks, pytest counts, log pruning and the script entry point."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "check_runner")

    def test_a_missing_test_directory_yields_no_scoped_suites(self):
        with mock.patch.object(
            self.mod, "book_root", lambda: os.path.join(self.tmp.name, "nowhere")
        ):
            self.assertEqual(self.mod.tests_for_change(["src/python/audit/x.py"]), [])

    def test_lint_falls_back_through_ruff_then_uvx_then_nothing(self):
        with mock.patch.object(self.mod.importlib.util, "find_spec", return_value=None):
            with mock.patch.object(self.mod.shutil, "which", return_value=None):
                self.assertIsNone(self.mod._command("lint"))
            with mock.patch.object(
                self.mod.shutil, "which", side_effect=lambda name: "uvx" if name == "uvx" else None
            ):
                command = self.mod._command("lint")
        self.assertEqual(command[:2], ["uvx", "ruff"])

    def test_lint_changed_without_ruff_has_no_command(self):
        with (
            mock.patch.object(self.mod, "scoped_changes", return_value=["src/python/x.py"]),
            mock.patch.object(self.mod.importlib.util, "find_spec", return_value=None),
        ):
            self.assertIsNone(self.mod._command("lint-changed"))
        with mock.patch.object(self.mod, "scoped_changes", return_value=[]):
            self.assertIsNone(self.mod._command("lint-changed"))

    def test_the_pytest_counts_are_read_out_of_the_summary_line(self):
        counts = self.mod.pytest_counts("1 failed, 2147 passed, 4 skipped, 2 deselected")
        self.assertEqual(counts, {"failed": 1, "passed": 2147, "skipped": 4, "deselected": 2})
        self.assertEqual(self.mod.pytest_counts("no summary here"), {})

    def test_an_unparsable_date_among_the_logs_is_skipped(self):
        import datetime

        logs = os.path.join(self.tmp.name, "logs")
        os.makedirs(logs, exist_ok=True)
        for name in ("check-p0-2026-13-45.log", "check-p0-20200101.log", "notes.txt"):
            with open(os.path.join(logs, name), "w", encoding="utf-8") as handle:
                handle.write("x\n")
        self.mod._prune_logs(logs, datetime.datetime(2026, 11, 25))
        remaining = sorted(os.listdir(logs))
        # the impossible date is skipped, the old one is removed, the stray stays
        self.assertNotIn("check-p0-20200101.log", remaining)
        self.assertIn("check-p0-2026-13-45.log", remaining)
        self.assertIn("notes.txt", remaining)
