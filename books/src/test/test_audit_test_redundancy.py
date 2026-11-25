#!/usr/bin/env python3
"""Test-hygiene gate: duplicate bodies, missing assertions, dead cases."""

from __future__ import annotations

import ast
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import _fixture

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

TAGS = ("layer:audit", "tier:fast")


class LooseBaselineTest(unittest.TestCase):
    """The accepted backlog shrinks visibly instead of rotting silently."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.mod = _fixture.load_module(_fixture.build_book(self.tmp), "test_redundancy")

    def write_case(self, body: str) -> None:
        path = os.path.join(self.tmp, "src", "test", "test_loose.py")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)

    def test_a_case_with_only_an_exit_code_check_is_a_candidate(self):
        self.write_case(
            "import unittest\n\n"
            "class T(unittest.TestCase):\n"
            "    def test_x(self):\n"
            "        code = 1\n"
            "        self.assertIn(code, (0, 1))\n"
        )
        found = self.mod.loose_candidates(os.path.join(self.tmp, "src", "test"))
        self.assertEqual([item["detail"].split(":")[0] for item in found], ["test_x"])

    def test_a_baseline_entry_that_stopped_matching_is_reported_as_stale(self):
        baseline = os.path.join(self.tmp, "data", "baselines", "loose-assertions.json")
        os.makedirs(os.path.dirname(baseline), exist_ok=True)
        with open(baseline, "w", encoding="utf-8") as fh:
            json.dump({"accepted": ["books/src/test/test_gone.py::test_gone"]}, fh)
        self.assertEqual(self.mod._loose_baseline(), {"books/src/test/test_gone.py::test_gone"})
        self.assertEqual(self.mod._loose_key({"file": "a.py", "detail": "name: x"}), "a.py::name")


class TestRedundancyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, "test_redundancy")

    def suite(self, name: str, body: str) -> None:
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)

    def analyse(self) -> list[dict]:
        return self.mod.analyse(self.tmp.name)

    def kinds(self) -> list[str]:
        return [item["kind"] for item in self.analyse()]

    def test_a_single_well_formed_case_is_clean(self):
        self.suite(
            "test_one.py",
            "import unittest\n\n\nclass WidgetTest(unittest.TestCase):\n"
            "    def test_runs(self):\n"
            "        self.assertEqual(1, 1)\n",
        )
        self.assertEqual(self.analyse(), [])

    def widget_suite(self, name: str, symbols: list[str]) -> None:
        body = "import _fixture\n\n\nclass WidgetTest(unittest.TestCase):\n"
        body += "    def test_" + name.removesuffix(".py") + "(self):\n"
        body += '        mod = _fixture.load_module(ROOT, "widget")\n'
        for symbol in symbols:
            body += f'        self.assertEqual(mod.{symbol}("a"), 1)\n'
        self.suite(name, body)

    def test_a_suite_that_only_restates_another_is_reported(self):
        self.widget_suite(
            "test_broad.py", ["parse", "compare", "describe", "targets", "write_back"]
        )
        self.widget_suite("test_narrow.py", ["parse", "compare", "describe", "targets"])
        findings = [item for item in self.analyse() if item["kind"] == "SUBSUMED"]
        self.assertEqual(len(findings), 1)
        self.assertIn("test_narrow.py", findings[0]["file"])
        self.assertIn("test_broad.py", findings[0]["detail"])

    def test_a_suite_with_a_symbol_of_its_own_is_not_subsumed(self):
        self.widget_suite("test_broad.py", ["parse", "compare", "describe", "targets"])
        self.widget_suite("test_own.py", ["parse", "compare", "write_back"])
        self.assertEqual([i for i in self.analyse() if i["kind"] == "SUBSUMED"], [])

    def test_a_handful_of_shared_symbols_is_not_evidence_of_a_copy(self):
        self.widget_suite("test_broad.py", ["parse", "compare", "describe", "targets"])
        self.widget_suite("test_thin.py", ["parse"])
        self.assertEqual([i for i in self.analyse() if i["kind"] == "SUBSUMED"], [])

    def test_a_suite_that_does_not_parse_is_skipped_by_the_subsumption_scan(self):
        self.suite("test_broken.py", "def (:\n")
        self.assertEqual(self.mod.subsumed(self.tmp.name), [])

    def test_only_load_module_bindings_count_as_module_access(self):
        tree = ast.parse('d["k"] = 1\nf().parse(1)\nx = _fixture.load_module(R, "w")\nx.parse(1)\n')
        self.assertEqual(self.mod._module_aliases(tree), {"x": "w"})
        subscript, call = tree.body[0], tree.body[1]
        assert isinstance(subscript, ast.Assign)  # narrows for the type checker
        assert isinstance(call, ast.Expr) and isinstance(call.value, ast.Call)
        self.assertEqual(self.mod._target_name(subscript.targets[0]), "")
        self.assertEqual(self.mod._root_name(call.value.func), "")

    def test_identical_bodies_are_reported_as_duplicates(self):
        body = (
            "import unittest\n\n\nclass WidgetTest(unittest.TestCase):\n"
            "    def test_a(self):\n        self.assertEqual(1, 1)\n"
            "    def test_b(self):\n        self.assertEqual(1, 1)\n"
        )
        self.suite("test_dup.py", body)
        self.assertIn("DUPLICATE", self.kinds())

    def test_a_case_without_assertions_is_reported(self):
        self.suite(
            "test_noassert.py",
            "import unittest\n\n\n"
            "class WidgetTest(unittest.TestCase):\n"
            "    def test_silent(self):\n        value = 1\n",
        )
        self.assertIn("NO-ASSERT", self.kinds())

    def test_trivial_body_is_reported(self):
        self.suite(
            "test_trivial.py",
            "import unittest\n\n\n"
            "class WidgetTest(unittest.TestCase):\n"
            "    def test_nothing(self):\n        pass\n",
        )
        self.assertIn("NO-ASSERT", self.kinds())

    def test_test_methods_outside_a_test_case_are_dead(self):
        self.suite(
            "test_dead.py", "class Helper:\n    def test_stray(self):\n        assert True\n"
        )
        self.assertIn("DEAD", self.kinds())

    def test_shadowed_method_names_are_dead(self):
        self.suite(
            "test_shadow.py",
            "import unittest\n\n\n"
            "class WidgetTest(unittest.TestCase):\n"
            "    def test_a(self):\n        self.assertTrue(True)\n"
            "    def test_a(self):\n        self.assertTrue(True)\n",
        )
        self.assertIn("DEAD", self.kinds())

    def test_a_tuple_binding_is_not_a_module_alias(self):
        tree = ast.parse('left, right = _fixture.load_module(R, "widget")\n')
        self.assertEqual(self.mod._module_aliases(tree), {})

    def test_a_stale_baseline_entry_warns_on_stderr(self):
        self.suite(
            "test_plain.py",
            "import unittest\n\n\nclass WidgetTest(unittest.TestCase):\n"
            "    def test_runs(self):\n        self.assertEqual(1, 1)\n",
        )
        stderr = io.StringIO()
        stale = {"books/src/test/test_gone.py::test_gone"}
        with (
            mock.patch.object(self.mod, "_loose_baseline", lambda: stale),
            redirect_stderr(stderr),
        ):
            findings = self.mod.analyse(self.tmp.name)
        self.assertEqual(findings, [])
        self.assertIn("1 条松散断言基线已不再命中", stderr.getvalue())

    def test_json_output_reports_the_counts(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(["--json"])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertIn("findings", payload)
        self.assertIn("blocking", payload)

    def test_the_real_suite_is_clean(self):
        code, out = _fixture.run_inproc(BOOK_ROOT, "test_redundancy.py")
        self.assertEqual(code, 0, out[-600:])


if __name__ == "__main__":
    unittest.main()


class RedundancyGateEdgesTest(unittest.TestCase):
    """Baseline absence, unparsable bindings, the human report and the exit code."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, "test_redundancy")

    def test_a_missing_or_broken_loose_baseline_reads_as_empty(self):
        with open(os.path.join(self.tmp.name, "broken.json"), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        for name, present in (("absent.json", False), ("broken.json", True)):
            with (
                self.subTest(name=name),
                mock.patch.object(self.mod, "LOOSE_BASELINE", name),
                mock.patch.object(self.mod._config, "BOOK_ROOT", self.tmp.name),
            ):
                self.assertEqual(self.mod._loose_baseline(), set(), present)

    def test_a_binding_whose_module_is_not_a_string_is_skipped(self):
        import ast

        tree = ast.parse("x = _fixture.load_module(R, 7)\ny = 1\n")
        self.assertEqual(self.mod._module_aliases(tree), {})

    def test_the_human_report_lists_findings_and_returns_one(self):
        finding = {
            "kind": "NO-ASSERT",
            "file": "src/test/test_x.py",
            "line": 9,
            "detail": "Class.test_case",
        }
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "analyse", return_value=[finding]),
            mock.patch.object(self.mod, "loose_candidates", return_value=[]),
            mock.patch.object(self.mod, "_loose_baseline", return_value=set()),
            redirect_stdout(buffer),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            self.assertEqual(self.mod.main([]), 1)
        self.assertIn("NO-ASSERT", buffer.getvalue())
        self.assertIn("test_case", buffer.getvalue())

    def test_a_clean_tree_reports_the_verdict(self):
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "analyse", return_value=[]),
            mock.patch.object(self.mod, "loose_candidates", return_value=[]),
            mock.patch.object(self.mod, "_loose_baseline", return_value=set()),
            redirect_stdout(buffer),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            self.assertEqual(self.mod.main([]), 0)
        self.assertIn("无冗余", buffer.getvalue())
