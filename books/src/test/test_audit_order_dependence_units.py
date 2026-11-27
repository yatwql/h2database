#!/usr/bin/env python3
"""Unit tests for the order-dependence helpers.

The end-to-end file spawns nested pytest runs, so it belongs to the slow tier and cannot
hold the per-file coverage floor on its own. These cases drive the same functions with
fakes: the comparison rules, the bisection loop, and module discovery against a temporary
directory.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from _cases import FixtureCase

TAGS = ("layer:audit", "tier:fast")


class CompareTest(FixtureCase):
    def test_identical_orders_are_clean(self):
        module = self.module("order_dependence")
        report = module.compare({"a": "ok"}, {"a": "ok"})
        self.assertTrue(report["ok"])
        self.assertEqual(report["order_dependent"], [])

    def test_a_flipped_outcome_names_the_case_and_both_sides(self):
        module = self.module("order_dependence")
        report = module.compare({"a": "ok", "b": "fail"}, {"a": "fail", "b": "fail"})
        self.assertFalse(report["ok"])
        self.assertEqual(report["order_dependent"],
                         [{"test": "a", "normal": "ok", "reverse": "fail"}])
        self.assertEqual(report["normal_failures"], 1)

    def test_a_skip_on_either_side_is_not_counted(self):
        module = self.module("order_dependence")
        report = module.compare({"a": "skip"}, {"a": "ok"})
        self.assertTrue(report["ok"])
        self.assertEqual(report["normal_failures"], 0)

    def test_a_case_missing_from_the_reverse_run_is_ignored(self):
        module = self.module("order_dependence")
        self.assertTrue(module.compare({"a": "ok"}, {})["ok"])


class BisectTest(FixtureCase):
    def bisect(self, outcomes, **kwargs):
        """Bisection over a fake prefix runner: ``outcomes`` maps prefix size -> result."""
        module = self.module("order_dependence")

        def fake(prefix, target):
            return outcomes(len(prefix))

        with mock.patch.object(module, "run_prefix", fake):
            return module.bisect("target", pool=["a", "b", "c", "d"], **kwargs)

    def test_a_target_that_does_not_pass_alone_is_not_order_dependent(self):
        report = self.bisect(lambda size: "fail")
        self.assertFalse(report["ok"])
        self.assertIn("does not pass on its own", report["reason"])

    def test_a_target_that_passes_in_the_full_order_needs_no_bisection(self):
        report = self.bisect(lambda size: "ok")
        self.assertTrue(report["ok"])
        self.assertIn("passes in the full order", report["reason"])

    def test_bisection_shrinks_the_prefix_to_the_first_polluter(self):
        # only the first module in the prefix makes the target fail
        report = self.bisect(lambda size: "ok" if size == 0 else "fail")
        self.assertTrue(report["ok"])
        self.assertEqual(report["prefix"], ["a"])
        self.assertEqual(report["prefix_size"], 1)
        self.assertGreater(report["steps"], 0)

    def test_the_step_cap_stops_a_long_bisection(self):
        report = self.bisect(lambda size: "ok" if size == 0 else "fail", max_steps=1)
        self.assertEqual(report["steps"], 1)


class ModuleDiscoveryTest(FixtureCase):
    def test_modules_are_listed_sorted_and_filtered(self):
        module = self.module("order_dependence")
        with tempfile.TemporaryDirectory() as folder:
            for name in ("test_b.py", "test_a.py", "helper.py", "notes.txt"):
                with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
                    fh.write("VALUE = 1\n")
            with mock.patch.object(module, "TEST_DIR", folder):
                self.assertEqual(module._all_modules(), ["test_a", "test_b"])
            with mock.patch.object(module, "TEST_DIR", os.path.join(folder, "missing")):
                with self.assertRaises(SystemExit):
                    module._all_modules()

    def test_loading_honours_only_and_reverse(self):
        module = self.module("order_dependence")
        with tempfile.TemporaryDirectory() as folder:
            for name in ("test_one.py", "test_two.py"):
                with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
                    fh.write("import unittest\n\n"
                             "class T(unittest.TestCase):\n"
                             "    def test_ok(self):\n        pass\n")
            sys.path.insert(0, folder)
            self.addCleanup(sys.path.remove, folder)
            def ids(suite):
                """Flatten the loaded suites: a loader nests them per module."""
                found = []
                for case in suite:
                    found.extend(sub.id() for sub in getattr(case, "_tests", [case]))
                return found

            with mock.patch.object(module, "TEST_DIR", folder):
                self.assertTrue(all("test_two" in case_id
                                    for case_id in ids(module._load_modules(False,
                                                                            only=["test_two"]))))
                self.assertTrue(ids(module._load_modules(True))[0].startswith("test_two"))


class CollectorTest(FixtureCase):
    def test_each_outcome_kind_is_recorded(self):
        module = self.module("order_dependence")

        class FakeTest:
            def id(self):
                return "mod.Test.test_x"

        collector = module._Collector(io.StringIO(), None, 0)
        collector.outcomes = {}
        collector.addSuccess(FakeTest())
        self.assertEqual(collector.outcomes["mod.Test.test_x"], "ok")
        with mock.patch.object(module.unittest.TestResult, "addFailure"), \
                mock.patch.object(module.unittest.TestResult, "addError"), \
                mock.patch.object(module.unittest.TestResult, "addSkip"):
            collector.addFailure(FakeTest(), None)
            collector.addError(FakeTest(), None)
            collector.addSkip(FakeTest(), "reason")
        self.assertEqual(collector.outcomes["mod.Test.test_x"], "skip")


class WorkerRunsTest(FixtureCase):
    """The two worker runs are subprocesses; the parsing and the failure paths are here."""

    def test_two_workers_are_compared(self):
        module = self.module("order_dependence")
        replies = [
            mock.Mock(returncode=0, stdout='{"outcomes": {"a": "ok"}}', stderr=''),
            mock.Mock(returncode=0, stdout='{"outcomes": {"a": "fail"}}', stderr=''),
        ]
        with mock.patch.object(module.subprocess, "run", side_effect=replies):
            report = module.run_both(only="test_a")
        self.assertFalse(report["ok"])
        self.assertEqual(report["order_dependent"][0]["test"], "a")

    def test_a_failing_worker_stops_the_run_with_its_message(self):
        module = self.module("order_dependence")
        reply = mock.Mock(returncode=3, stdout='', stderr='boom')
        with mock.patch.object(module.subprocess, "run", return_value=reply):
            with self.assertRaises(SystemExit) as caught:
                module.run_both()
        self.assertIn("worker failed", str(caught.exception))

    def test_a_worker_that_prints_no_json_stops_the_run(self):
        module = self.module("order_dependence")
        reply = mock.Mock(returncode=0, stdout='not json', stderr='')
        with mock.patch.object(module.subprocess, "run", return_value=reply):
            with self.assertRaises(SystemExit) as caught:
                module.run_both()
        self.assertIn("no JSON", str(caught.exception))

    def test_the_worker_mode_prints_one_json_line(self):
        module = self.module("order_dependence")
        with mock.patch.object(module, "collect", return_value={"a": "ok"}):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                self.assertEqual(module._worker(True, "test_a"), 0)
        self.assertEqual(json.loads(out.getvalue()), {"reverse": True, "outcomes": {"a": "ok"}})


class MainTest(FixtureCase):
    def run_main(self, argv, result=None, collect=None):
        module = self.module("order_dependence")
        out = io.StringIO()
        with (
            mock.patch.object(module, "bisect", return_value=result or {"ok": True}),
            mock.patch.object(module, "run_both", return_value=result or {"ok": True}),
            mock.patch.object(module, "collect", return_value=collect or {}),
            mock.patch("sys.stdout", new=out),
        ):
            code = module.main(argv)
        return code, out.getvalue()

    def test_bisect_json_exits_zero_when_ok_and_two_when_not(self):
        self.assertEqual(self.run_main(["--json", "--bisect", "m"], result={"ok": True})[0], 0)
        self.assertEqual(self.run_main(["--json", "--bisect", "m"], result={"ok": False})[0], 2)

    def test_the_worker_flag_runs_the_worker_not_the_report(self):
        code, _out = self.run_main(["--run", "reverse", "--only", "test_a"], collect={"a": "ok"})
        self.assertEqual(code, 0)


class RealSuiteRunTest(FixtureCase):
    """`collect`/`run_prefix` drive unittest itself; a two-case module proves the wiring."""

    def fixture_dir(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        with open(os.path.join(folder.name, "test_probe.py"), "w", encoding="utf-8") as fh:
            fh.write("import unittest\n\n"
                     "class Probe(unittest.TestCase):\n"
                     "    def test_ok(self):\n        pass\n"
                     "    def test_bad(self):\n        self.fail('deliberate')\n")
        return folder.name

    def test_collect_reports_each_case_outcome(self):
        module = self.module("order_dependence")
        folder = self.fixture_dir()
        with mock.patch.object(module, "TEST_DIR", folder):
            outcomes = module.collect(False, ["test_probe"])
        self.assertEqual(outcomes["test_probe.Probe.test_ok"], "ok")
        self.assertEqual(outcomes["test_probe.Probe.test_bad"], "fail")

    def test_run_prefix_returns_the_target_outcome_and_none_when_absent(self):
        module = self.module("order_dependence")
        folder = self.fixture_dir()
        with mock.patch.object(module, "TEST_DIR", folder):
            self.assertEqual(module.run_prefix([], "test_probe"), "fail")
            self.assertIsNone(module.run_prefix([], "test_missing"))

    def test_the_default_report_prints_the_comparison(self):
        module = self.module("order_dependence")
        out = io.StringIO()
        with (
            mock.patch.object(module, "run_both",
                              return_value={"ok": True, "order_dependent": [],
                                            "normal_failures": 0, "reverse_failures": 0}),
            mock.patch("sys.stdout", new=out),
        ):
            self.assertEqual(module.main([]), 0)
        self.assertIn("无顺序依赖", out.getvalue())


class RemainingPathsTest(FixtureCase):
    def test_an_unreadable_suite_directory_is_a_clean_error(self):
        module = self.module("order_dependence")
        with mock.patch.object(module, "TEST_DIR", "/nonexistent/suite"):
            with self.assertRaises(SystemExit):
                module._load_modules(False)

    def test_run_prefix_skips_modules_that_cannot_be_imported(self):
        module = self.module("order_dependence")
        with mock.patch.object(module, "TEST_DIR", os.path.dirname(os.path.abspath(__file__))):
            self.assertIsNone(module.run_prefix(["test_no_such_module"], "test_no_such_module"))

    def test_a_bisect_with_a_prefix_prints_the_culprits(self):
        module = self.module("order_dependence")
        result = {"ok": True, "prefix_size": 2, "steps": 3, "prefix": ["a", "b"]}
        out = io.StringIO()
        with (
            mock.patch.object(module, "bisect", return_value=result),
            mock.patch.object(module, "run_both", return_value={"ok": True}),
            mock.patch("sys.stdout", new=out),
        ):
            self.assertEqual(module.main(["--bisect", "target"]), 0)
        self.assertIn("最小前置集合", out.getvalue())
        self.assertIn("  a", out.getvalue())

    def test_json_report_exits_one_when_a_case_is_order_dependent(self):
        module = self.module("order_dependence")
        report = {"ok": False,
                  "order_dependent": [{"test": "a", "normal": "ok", "reverse": "fail"}],
                  "normal_failures": 0, "reverse_failures": 0}
        out = io.StringIO()
        with (
            mock.patch.object(module, "run_both", return_value=report),
            mock.patch("sys.stdout", new=out),
        ):
            self.assertEqual(module.main([]), 1)
            self.assertEqual(module.main(["--json"]), 1)
        self.assertIn("顺序依赖用例 1 个", out.getvalue())


if __name__ == "__main__":
    unittest.main()
