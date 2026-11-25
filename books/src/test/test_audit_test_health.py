#!/usr/bin/env python3
"""The health view reads the same numbers the gates read, and nothing else."""

from __future__ import annotations

import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

COVERAGE_JSON = {
    "totals": {
        "percent_covered": 87.6,
        "num_statements": 100,
        "missing_lines": 12,
        "num_partial_branches": 9,
    },
    "files": {
        "books/src/python/thin.py": {
            "summary": {
                "percent_covered": 50.0,
                "num_statements": 20,
                "num_partial_branches": 7,
                "missing_lines": 10,
            }
        },
        "books/src/python/tiny.py": {
            "summary": {
                "percent_covered": 0.0,
                "num_statements": 2,
                "num_partial_branches": 0,
                "missing_lines": 2,
            }
        },
    },
}


class TestHealthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.health = _fixture.load_module(self.root, "test_health")

    def run_json(self, mode: str = "--json"):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.health.main([mode] if mode else [])
        return code, buffer.getvalue()

    def test_coverage_snapshot_reads_the_json_and_skips_tiny_files(self):
        with mock.patch.object(self.health, "_run", return_value=(0, json.dumps(COVERAGE_JSON))):
            snapshot = self.health.coverage_snapshot()
        self.assertEqual(snapshot["total_percent"], 87.6)
        self.assertEqual(
            [item["file"] for item in snapshot["thinnest"]], ["books/src/python/thin.py"]
        )
        self.assertEqual(snapshot["branch_heavy"][0]["half_branches"], 7)

    def test_an_unreadable_coverage_file_is_not_an_error(self):
        with mock.patch.object(self.health, "_run", return_value=(1, "")):
            self.assertEqual(self.health.coverage_snapshot(), {})
        with mock.patch.object(self.health, "_run", return_value=(0, "not json")):
            self.assertEqual(self.health.coverage_snapshot(), {})

    def test_below_baseline_names_the_file_that_dropped(self):
        baseline = os.path.join(self.root, "data", "baselines", "coverage.json")
        os.makedirs(os.path.dirname(baseline), exist_ok=True)
        with open(baseline, "w", encoding="utf-8") as fh:
            json.dump({"files": {"books/src/python/thin.py": 90.0}}, fh)
        coverage = {"files": [{"file": "books/src/python/thin.py", "percent": 50.0}]}
        self.assertEqual(
            self.health.below_baseline(coverage),
            [{"file": "books/src/python/thin.py", "baseline": 90.0, "now": 50.0}],
        )
        self.assertEqual(self.health.below_baseline({}), [])

    def test_long_functions_are_found_by_length(self):
        source = os.path.join(self.root, "src", "python")
        os.makedirs(source, exist_ok=True)
        body = "def wide():\n" + "".join(f"    x{i} = {i}\n" for i in range(70))
        with open(os.path.join(source, "wide.py"), "w", encoding="utf-8") as fh:
            fh.write(body)
        with (
            mock.patch.object(self.health, "PY_ROOT", source),
            mock.patch.object(self.health, "REPO_ROOT", self.root),
        ):
            found = self.health.long_functions(60)
        self.assertEqual([item["name"] for item in found], ["wide"])

    def test_a_function_below_the_threshold_is_not_listed(self):
        source = os.path.join(self.root, "src", "python")
        os.makedirs(source, exist_ok=True)
        with open(os.path.join(source, "mixed.py"), "w", encoding="utf-8") as fh:
            fh.write("def wide():\n" + "".join(f"    x{i} = {i}\n" for i in range(70)))
            fh.write("\n\ndef narrow():\n    return 1\n")
        with (
            mock.patch.object(self.health, "PY_ROOT", source),
            mock.patch.object(self.health, "REPO_ROOT", self.root),
        ):
            found = self.health.long_functions(60)
        self.assertEqual([item["name"] for item in found], ["wide"])

    def test_the_loose_assertion_count_covers_the_book_suite(self):
        path = os.path.join(self.root, "src", "test", "test_loose_probe.py")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # the call is assembled here so this file itself stays free of the
        # loose-assertion shape the gate below looks for
        loose = "self.assert" + "In(code, (0, 1))"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(
                "import unittest\n\n\nclass T(unittest.TestCase):\n"
                "    def test_x(self):\n"
                "        code = 1\n"
                f"        {loose}\n"
            )
        test_redundancy = importlib.import_module("audit.test_redundancy")
        package = importlib.import_module("audit")

        def forget():
            # leave the process as it was found: a later case checks the
            # unreadable-module path, which resolves through the package attribute
            package.__dict__.pop("test_redundancy", None)
            sys.modules.pop("audit.test_redundancy", None)

        self.addCleanup(forget)
        suite_dir = os.path.join(self.root, "src", "test")
        with mock.patch.object(test_redundancy, "TEST_ROOT", suite_dir):
            self.assertEqual(self.health.loose_assertions(), 1)

    def test_the_report_prints_every_reading(self):
        with (
            mock.patch.object(self.health, "_run", return_value=(0, json.dumps(COVERAGE_JSON))),
            mock.patch.object(
                self.health,
                "long_functions",
                return_value=[{"file": "a.py", "name": "wide", "lines": 99}],
            ),
            mock.patch.object(self.health, "loose_assertions", return_value=61),
        ):
            code, out = self.run_json()
        payload = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(payload["loose_assertions"], 61)
        self.assertEqual(payload["long_functions"][0]["lines"], 99)

    def test_the_table_names_the_thinnest_module(self):
        with (
            mock.patch.object(self.health, "_run", return_value=(0, json.dumps(COVERAGE_JSON))),
            mock.patch.object(self.health, "long_functions", return_value=[]),
            mock.patch.object(self.health, "loose_assertions", return_value=0),
        ):
            code, out = self.run_json("")
        self.assertEqual(code, 0)
        self.assertIn("books/src/python/thin.py", out)
        self.assertIn("松散断言", out)

    def test_no_coverage_data_says_so(self):
        with (
            mock.patch.object(self.health, "_run", return_value=(1, "")),
            mock.patch.object(self.health, "long_functions", return_value=[]),
            mock.patch.object(self.health, "loose_assertions", return_value=-1),
        ):
            code, out = self.run_json("")
        self.assertEqual(code, 0)
        self.assertIn("无数据", out)
        self.assertIn("不可读", out)


class TestHealthSurfacesTest(unittest.TestCase):
    """The reader's own surfaces: the subprocess helper, loose counts, the report."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(
            os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR)), "test_health"
        )

    def test_run_reports_the_code_and_the_stdout(self):
        code, out = self.mod._run([sys.executable, "-c", "print('hi')"])
        self.assertEqual((code, out.strip()), (0, "hi"))

    def test_an_unreadable_redundancy_module_reads_as_unknown(self):
        with mock.patch.dict(sys.modules, {"audit.test_redundancy": None}):
            self.assertEqual(self.mod.loose_assertions(), -1)

    def test_the_report_names_the_thinnest_files_and_the_baseline_drops(self):
        payload = {
            "coverage": {
                "total_percent": 94.0,
                "missing": 1,
                "statements": 100,
                "half_branches": 3,
                "thinnest": [{"percent": 88.0, "statements": 50, "file": "a.py"}],
                "branch_heavy": [{"half_branches": 7, "file": "b.py"}],
            },
            "coverage_threshold": 90,
            "below_baseline": [{"file": "c.py", "now": 80.0, "baseline": 85.0}],
            "loose_assertions": -1,
            "function_length_warn": 60,
            "long_functions": [{"lines": 70, "file": "d.py", "name": "long"}],
        }
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.mod.render(payload)
        text = buffer.getvalue()
        self.assertIn("a.py", text)
        self.assertIn("b.py", text)
        self.assertIn("c.py", text)
        self.assertIn("d.py::long", text)
        self.assertIn("不可读", text)


class ScriptGuardTest(unittest.TestCase):
    """`test_health.py` run as a script: `--help` answers instead of measuring."""

    def test_help_prints_the_json_flag_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _fixture.build_book(tmp)
            code, out = _fixture.run_inproc(root, "test_health.py", "--help")
        self.assertEqual(code, 0)
        self.assertIn("--json", out)


if __name__ == "__main__":
    unittest.main()
