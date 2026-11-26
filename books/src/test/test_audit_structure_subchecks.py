#!/usr/bin/env python3
"""structure.py: the branches a healthy build never takes.

The gate aggregates many sub-checks; each one is wrapped so a broken tool is
reported instead of aborting the run. Those wrappers are what these cases drive.
"""

from __future__ import annotations

import os
import shutil
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


class StructureGateCase(unittest.TestCase):
    """A fixture book, and the gate run against it in this process."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def gate(self, script: str = "structure.py", *args: str):
        return _fixture.run_inproc(self.root, script, *args)


class SubCheckWrapperTest(StructureGateCase):
    """A sub-check that cannot run is reported, never raised."""

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

    def test_the_gate_reports_each_failing_check_by_name(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n```text\nunclosed fence\n")
        code, out = self.gate()
        self.assertEqual(code, 1, out[-600:])
        self.assertIn("FAIL:", out)


class CssCheckSourceTest(StructureGateCase):
    """The CSS check reads the renderer beside the gate, and says so when absent.

    Both cases read the files the check really opens: removing a hook from the
    renderer, or the renderer from the tree, is what makes them fail.
    """

    def setUp(self):
        super().setUp()
        # load through the fixture (so the config resolves) and tolerate the gate the
        # script runs at import time: a red gate must not become a test error
        self.structure = _fixture.load_module(self.root, "structure")

    def test_the_shipped_renderer_carries_every_hook(self):
        render_dir = os.path.join(TOOLS_DIR, "render")
        fsutil = __import__("lib._fsutil", fromlist=["read_text_raw"])
        source = "\n".join(
            fsutil.read_text_raw(os.path.join(render_dir, name))
            for name in ("to_html.py", "html_shell.py")
        )
        self.assertEqual(self.structure.css_style_missing(source), [])

    def test_a_tree_without_the_renderer_skips_the_css_check(self):
        tree = os.path.join(self.tmp.name, "python")
        os.makedirs(os.path.join(tree, "audit"))
        # the gate looks for the renderer next to itself, so the copy has to sit in
        # a tree of its own: patching the reader would prove nothing about the path
        copy = os.path.join(tree, "audit", "structure.py")
        source = self.structure.__file__
        assert source is not None        # a loaded module always has one
        shutil.copyfile(source, copy)
        code, out = _fixture.run_inproc(self.root, copy)
        self.assertIn(code, (0, 1))
        self.assertIn("CSS check skipped (to_html.py not found)", out)


class AdvisorySubCheckTest(StructureGateCase):
    """Every advisory sub-check must report instead of raising, and say when absent."""

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


class SubCheckToolWiringTest(StructureGateCase):
    """The advisory tools structure.py reaches for, present and absent.

    The gate looks for these tools next to itself, so the fixture book cannot
    supply them: the boundary (``os.path.exists``/``subprocess.run``) is stubbed
    and the check itself runs for real.
    """

    AUDIT_DIR = os.path.join(TOOLS_DIR, "audit")

    def setUp(self):
        super().setUp()
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
                code, out = self.gate()
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
                code, out = self.gate()
        self.assertEqual(code, 1, out[-400:])
        self.assertIn("Index hierarchy check failed to run", out)


class GlossaryAndIndexContentTest(StructureGateCase):
    """Content shapes the shipped manuscript never produces."""

    def setUp(self):
        super().setUp()
        self.back = os.path.join(self.root, "data", "manuscript", "back")

    def append(self, name: str, text: str) -> None:
        with open(os.path.join(self.back, name), "a", encoding="utf-8") as handle:
            handle.write(text)

    def test_an_index_entry_naming_a_chapter_outside_the_book_is_reported(self):
        self.append("index.md", "\n- 越界条目 §99.1\n")
        code, out = self.gate()
        self.assertEqual(code, 1, out[-600:])
        self.assertIn("Index references non-existent chapters: [99]", out)

    def test_a_glossary_ending_on_a_boundary_closes_its_last_entry(self):
        # the chapter reference sits past the boundary: it belongs to no entry, so
        # the entry before the boundary is the one reported as unreferenced
        self.append("glossary.md", "- **BTree**: 索引结构。\n## 附录\n第3章 与本表无关\n")
        code, out = self.gate()
        self.assertEqual(code, 1, out[-600:])
        self.assertIn("MISSING CHAPTER REF: BTree", out)
        self.assertNotIn("MISSING CHAPTER REF: MVStore", out)

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


if __name__ == "__main__":
    unittest.main()
