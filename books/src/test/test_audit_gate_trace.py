#!/usr/bin/env python3
"""Gate trace: the testplan and make.py must name the same gates."""

from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))


class GateTraceTest(unittest.TestCase):
    def setUp(self):
        # gate_trace inspects the real testplan and make.py, not a fixture book
        self.trace = _fixture.load_module(BOOK_ROOT, "gate_trace")

    def test_gate_scripts_reads_the_step_table(self):
        gates = self.trace.gate_scripts()
        self.assertIn("architecture", gates)
        self.assertTrue(gates["architecture"].endswith("check_architecture.py"))

    def test_testplan_scripts_lists_documented_names(self):
        documented = self.trace.testplan_scripts()
        self.assertTrue(documented)
        self.assertTrue(all(name.endswith(".py") for name in documented))

    def test_available_lists_source_relative_paths(self):
        present = self.trace.available()
        self.assertTrue(present)
        self.assertIn("audit/structure.py", present)
        self.assertTrue(all(not os.path.isabs(path) for path in present))

    def test_main_passes_on_the_real_tree(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.trace.main([])
        self.assertEqual(code, 0, buffer.getvalue()[-300:])
        self.assertRegex(buffer.getvalue(), r"✅|OK|通过|PASS")
        self.assertTrue(buffer.getvalue())

    def test_json_output_lists_problems(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.trace.main(["--json"])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertIn("problems", payload)

    def test_a_documented_gate_missing_from_make_is_reported(self):
        with (
            mock.patch.object(self.trace, "gate_scripts", return_value={}),
            mock.patch.object(
                self.trace,
                "testplan_scripts",
                return_value={os.path.join(BOOK_ROOT, "src/python/audit/traces.py")},
            ),
            mock.patch.object(
                self.trace,
                "available",
                return_value={os.path.join(BOOK_ROOT, "src/python/audit/traces.py")},
            ),
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = self.trace.main([])
        self.assertEqual(code, 1)
        self.assertIn("make.py does not run it", buffer.getvalue())

    def test_a_missing_script_is_reported(self):
        ghost = os.path.join(BOOK_ROOT, "src/python/audit/ghost.py")
        with (
            mock.patch.object(self.trace, "gate_scripts", return_value={"ghost": ghost}),
            mock.patch.object(self.trace, "testplan_scripts", return_value=set()),
            mock.patch.object(self.trace, "available", return_value=set()),
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = self.trace.main([])
        self.assertEqual(code, 1)
        self.assertIn("missing script", buffer.getvalue())

    def test_a_documented_script_that_is_absent_is_reported(self):
        present = os.path.join(BOOK_ROOT, "src/python/audit/traces.py")
        ghost = os.path.join(BOOK_ROOT, "src/python/audit/ghost.py")
        with (
            mock.patch.object(self.trace, "gate_scripts", return_value={"traces": present}),
            mock.patch.object(self.trace, "testplan_scripts", return_value={ghost}),
            mock.patch.object(self.trace, "available", return_value={present}),
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = self.trace.main([])
        self.assertEqual(code, 1)
        self.assertIn("testplan.md names a missing script", buffer.getvalue())

    def test_script_entrypoint_reports_through_the_error_wrapper(self):
        code, out = _fixture.run_inproc(BOOK_ROOT, "gate_trace.py", "--json")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('"gates"', out)


if __name__ == "__main__":
    unittest.main()
