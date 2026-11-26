#!/usr/bin/env python3
"""fetch_source: command shapes, the dry run, git failures and the refusals."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:core", "tier:fast")

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class FetchSourceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "fetch_source")

    def run_main(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(list(argv))
        return code, buffer.getvalue()

    def test_a_refresh_lands_on_the_requested_ref(self):
        commands = self.mod.update_commands("/src", "v1.2")
        self.assertIn("fetch", commands[0])
        self.assertIn(["git", "-C", "/src", "checkout", "v1.2"], commands)
        self.assertTrue(any("--ff-only" in part for part in commands[-1]))

    def test_a_refresh_without_a_ref_only_fetches(self):
        self.assertEqual(len(self.mod.update_commands("/src")), 1)

    def test_a_dry_run_prints_the_command_and_does_not_run_it(self):
        with (
            mock.patch.object(self.mod.subprocess, "run") as runner,
            redirect_stdout(io.StringIO()) as out,
        ):
            code = self.mod.run(["git", "status"], dry_run=True)
        self.assertEqual(code, 0)
        self.assertIn("would run: git status", out.getvalue())
        runner.assert_not_called()

    def test_a_missing_git_binary_is_reported_as_127(self):
        with (
            mock.patch.object(self.mod.subprocess, "run", side_effect=OSError("no git")),
            redirect_stdout(io.StringIO()) as out,
        ):
            code = self.mod.run(["git", "status"], dry_run=False)
        self.assertEqual(code, 127)
        self.assertIn("无法执行 git", out.getvalue())

    def test_a_failing_git_command_stops_the_sequence(self):
        done = mock.Mock(returncode=3)
        with mock.patch.object(self.mod.subprocess, "run", return_value=done):
            code, out = self.run_main(
                "--repo", "https://example.com/x.git", "--dir", os.path.join(self.tmp.name, "clone")
            )
        self.assertEqual(code, 3)
        self.assertIn("git 返回 3", out)

    def test_an_existing_clone_is_left_alone_without_update(self):
        target = os.path.join(self.tmp.name, "clone")
        os.makedirs(target, exist_ok=True)
        code, out = self.run_main("--repo", "https://example.com/x.git", "--dir", target)
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("已存在", out)

    def test_json_mode_describes_the_outcome(self):
        done = mock.Mock(returncode=0)
        with mock.patch.object(self.mod.subprocess, "run", return_value=done):
            code, out = self.run_main(
                "--repo",
                "https://example.com/x.git",
                "--dir",
                os.path.join(self.tmp.name, "clone"),
                "--json",
                "--dry-run",
            )
        self.assertEqual(code, 0, out[-300:])
        payload = json.loads(out[out.index("{") :])
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["updated"])

    def test_without_a_repository_the_tool_refuses(self):
        code, out = self.run_main("--dir", os.path.join(self.tmp.name, "x"))
        self.assertEqual(code, 2)
        self.assertIn("没有配置", out)

    def test_a_repository_that_yields_no_directory_is_refused(self):
        code, out = self.run_main("--repo", "  ")
        self.assertEqual(code, 2)
        self.assertIn("请给 --dir", out)

    def test_the_script_entrypoint_reports_through_the_error_wrapper(self):
        code, out = _fixture.run_inproc(self.root, "fetch_source.py")
        self.assertEqual(code, 2, out[-300:])
        self.assertIn("没有配置", out)


if __name__ == "__main__":
    unittest.main()
