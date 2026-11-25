#!/usr/bin/env python3
"""structure.py: the branches a healthy build never takes.

The gate aggregates many sub-checks; each one is wrapped so a broken tool is
reported instead of aborting the run. Those wrappers are what these cases drive.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class StructureBranchesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def gate(self, script: str = "structure.py", *args: str):
        return _fixture.run_inproc(self.root, script, *args)

    def test_a_sub_check_that_cannot_run_is_reported_not_raised(self):
        import subprocess

        real_run = subprocess.run

        def failing(command, **kwargs):
            if any("index" in str(part) for part in command):
                raise OSError("tool exploded")
            return real_run(command, **kwargs)

        with mock.patch.object(subprocess, "run", side_effect=failing):
            code, out = self.gate()
        self.assertEqual(code, 1, out[-400:])
        self.assertIn("Index", out)
        self.assertNotIn("Traceback", out)

    def test_a_missing_index_is_a_hard_failure(self):
        os.unlink(os.path.join(self.root, "data", "manuscript", "back", "index.md"))
        code, out = self.gate()
        self.assertEqual(code, 1, out[-400:])
        self.assertIn("Index", out)

    def test_a_broken_css_reference_warns_but_does_not_crash(self):
        code, out = self.gate()
        # the fixture book has its own gaps, so the gate exits 1; what matters
        # here is that the CSS check reported instead of raising
        self.assertEqual(code, 1, out[-400:])
        self.assertIn("CSS", out)
        self.assertNotIn("Traceback", out)

    def test_the_gate_reports_each_failing_check_by_name(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n```text\nunclosed fence\n")
        code, out = self.gate()
        self.assertEqual(code, 1, out[-600:])
        self.assertIn("FAIL:", out)


if __name__ == "__main__":
    unittest.main()


class ExtractedChecksTest(unittest.TestCase):
    """The CSS-hook and builder-script checks, judged without running the script."""

    def setUp(self):
        self.structure = __import__("audit.structure", fromlist=["css_style_missing"])

    def test_every_hook_present_reports_nothing(self):
        source = "\n".join(self.structure.CSS_HINTS.values())
        self.assertEqual(self.structure.css_style_missing(source), [])

    def test_a_missing_hook_is_named_with_its_selector(self):
        missing = self.structure.css_style_missing("h1::before")
        self.assertTrue(missing)
        self.assertIn("print styles (@media print)", missing)

    def test_a_broken_builder_script_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "glossary.py")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("def broken(:\n")
            broken, missing = self.structure.builder_script_problems({"glossary.py": path})
        self.assertEqual(missing, [])
        self.assertIn("syntax error", broken[0])

    def test_a_missing_builder_script_is_only_a_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            broken, missing = self.structure.builder_script_problems(
                {"glossary.py": os.path.join(directory, "gone.py")}
            )
        self.assertEqual(broken, [])
        self.assertEqual(missing, ["glossary.py not found"])

    def test_the_sources_it_reads_are_the_real_ones(self):
        """The check used to read audit/to_html.py and audit/glossary.py after both
        moved, so it silently took the "skipped" branch for months."""
        src = __import__("pathlib").Path(self.structure.__file__).resolve()
        python_root = src.parent.parent
        self.assertTrue((python_root / "render" / "to_html.py").is_file())
        self.assertTrue((python_root / "render" / "html_shell.py").is_file())
        self.assertTrue((python_root / "manuscript" / "glossary.py").is_file())
        self.assertTrue((python_root / "manuscript" / "index.py").is_file())


class SubCheckFailureModesTest(unittest.TestCase):
    """Every advisory sub-check must report instead of raising, and say when absent."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def gate(self):
        return _fixture.run_inproc(self.root, "structure.py")

    def test_a_sub_check_that_cannot_run_is_reported_for_every_advisory_tool(self):
        import subprocess

        real_run = subprocess.run

        def failing(command, **kwargs):
            if any(
                name in str(part)
                for part in command
                for name in ("captions", "figure_clusters", "exercises")
            ):
                raise OSError("tool exploded")
            return real_run(command, **kwargs)

        with mock.patch.object(subprocess, "run", side_effect=failing):
            code, out = self.gate()
        self.assertIn(code, (0, 1))
        self.assertIn("failed to run", out)
        self.assertNotIn("Traceback", out)

    def test_a_missing_advisory_tool_is_a_hard_failure(self):
        real_exists = os.path.exists
        hidden = ("captions.py", "figure_clusters.py", "exercises.py")

        def exists(path):
            if str(path).endswith(hidden):
                return False
            return real_exists(path)

        with mock.patch.object(os.path, "exists", side_effect=exists):
            code, out = self.gate()
        self.assertEqual(code, 1, out[-400:])
        self.assertIn("tool missing", out)

    def test_a_repository_without_the_style_tool_reports_it_and_moves_on(self):
        real_exists = os.path.exists
        absent = ("style.py", "index_xrefs.py")

        def exists(path):
            if str(path).endswith(absent):
                return False
            return real_exists(path)

        with mock.patch.object(os.path, "exists", side_effect=exists):
            code, out = self.gate()
        self.assertIn(code, (0, 1))
        self.assertIn("style.py not found", out)
        self.assertNotIn("see-also", out)


class SubCheckToolWiringTest(unittest.TestCase):
    """The advisory tools structure.py reaches for, present and absent.

    The gate looks for these tools next to itself, so the fixture book cannot
    supply them: the boundary (``os.path.exists``/``subprocess.run``) is stubbed
    and the check itself runs for real.
    """

    AUDIT_DIR = os.path.join(TOOLS_DIR, "audit")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.hierarchy_tool = os.path.join(self.AUDIT_DIR, "index.py")

    def test_the_index_hierarchy_floor_is_checked_when_the_tool_runs(self):
        import subprocess

        real_exists, real_run = os.path.exists, subprocess.run

        def exists(path):
            if str(path) == self.hierarchy_tool:
                return True
            return real_exists(path)

        def run(command, **kwargs):
            if str(command[1]) == self.hierarchy_tool:
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            return real_run(command, **kwargs)

        with mock.patch.object(os.path, "exists", side_effect=exists):
            with mock.patch.object(subprocess, "run", side_effect=run):
                code, out = _fixture.run_inproc(self.root, "structure.py")
        self.assertIn(code, (0, 1))
        self.assertIn("Index hierarchy floor", out)
        self.assertIn("see-also>=", out)

    def test_a_hierarchy_tool_that_cannot_start_is_reported_by_name(self):
        import subprocess

        real_exists, real_run = os.path.exists, subprocess.run

        def exists(path):
            if str(path) == self.hierarchy_tool:
                return True
            return real_exists(path)

        def run(command, **kwargs):
            if str(command[1]) == self.hierarchy_tool:
                raise OSError("tool exploded")
            return real_run(command, **kwargs)

        with mock.patch.object(os.path, "exists", side_effect=exists):
            with mock.patch.object(subprocess, "run", side_effect=run):
                code, out = _fixture.run_inproc(self.root, "structure.py")
        self.assertEqual(code, 1, out[-400:])
        self.assertIn("Index hierarchy check failed to run", out)


class GlossaryAndIndexContentTest(unittest.TestCase):
    """Content shapes the shipped manuscript never produces."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.back = os.path.join(self.root, "data", "manuscript", "back")

    def gate(self):
        return _fixture.run_inproc(self.root, "structure.py")

    def append(self, name: str, text: str) -> None:
        with open(os.path.join(self.back, name), "a", encoding="utf-8") as handle:
            handle.write(text)

    def test_a_index_entry_naming_a_chapter_outside_the_book_is_ignored(self):
        self.append("index.md", "\n- 越界条目 §99.1\n")
        code, out = self.gate()
        self.assertIn(code, (0, 1))
        self.assertIn("Index:", out)

    def test_a_glossary_ending_on_a_boundary_closes_its_last_entry(self):
        self.append("glossary.md", "\n## 附录\n")
        code, out = self.gate()
        self.assertIn(code, (0, 1))
        self.assertIn("Glossary:", out)

    def test_a_builder_script_that_does_not_parse_fails_the_gate(self):
        _fsutil = __import__("lib._fsutil", fromlist=["read_text_raw"])
        real = _fsutil.read_text_raw
        builder = os.path.join("manuscript", "glossary.py")

        def broken(path):
            if str(path).endswith(builder):
                return "def broken(:\n"
            return real(path)

        with mock.patch.object(_fsutil, "read_text_raw", side_effect=broken):
            code, out = self.gate()
        self.assertEqual(code, 1, out[-600:])
        self.assertIn("FAIL: glossary.py — syntax error", out)
        self.assertIn("Glossary builder scripts available", out)
