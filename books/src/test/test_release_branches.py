#!/usr/bin/env python3
"""release.py: the four subcommands, the dirty-tree refusal, the manifest."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:infra", "tier:fast")

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "release")

    def run_main(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = self.mod.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def publish_args(self, **overrides) -> argparse.Namespace:
        base = {"title": "", "allow_dirty": False}
        base.update(overrides)
        return argparse.Namespace(**base)

    # -- git helpers -----------------------------------------------------
    def test_a_missing_git_reports_nothing_instead_of_raising(self):
        with mock.patch.object(self.mod.subprocess, "run", side_effect=OSError("no git")):
            self.assertEqual(self.mod.git("status"), "")
        with mock.patch.object(self.mod.subprocess, "run", side_effect=OSError("no git")):
            self.assertFalse(self.mod.tree_is_dirty())

    def test_a_failing_git_command_is_empty(self):
        done = subprocess.CompletedProcess(["git"], 1, stdout="x", stderr="")
        with mock.patch.object(self.mod.subprocess, "run", return_value=done):
            self.assertEqual(self.mod.git("status"), "")

    def test_a_dirty_tree_is_detected(self):
        done = subprocess.CompletedProcess(["git"], 0, stdout=" M books/x\n", stderr="")
        with mock.patch.object(self.mod.subprocess, "run", return_value=done):
            self.assertTrue(self.mod.tree_is_dirty())

    # -- manifest --------------------------------------------------------
    def test_the_manifest_records_every_built_artifact(self):
        payload = self.mod.write_manifest("测试发布")
        with open(payload, encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest["title"], "测试发布")
        self.assertIn("versions", manifest)
        self.assertIn("artifacts", manifest)

    def test_the_manifest_hashes_the_artifacts_that_were_built(self):
        built = self.mod.artifacts()[0]
        os.makedirs(self.mod._config.DIST_DIR, exist_ok=True)
        with open(os.path.join(self.mod._config.DIST_DIR, built), "wb") as fh:
            fh.write(b"%PDF-1.4")
        with open(self.mod.write_manifest(), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual(list(manifest["artifacts"]), [built])
        self.assertEqual(manifest["artifacts"][built]["bytes"], 8)
        self.assertEqual(len(manifest["artifacts"][built]["sha256"]), 64)

    # -- commands --------------------------------------------------------
    def test_status_lists_versions_and_artifacts(self):
        code, out, _err = self.run_main("status")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("versions :", out)
        self.assertIn("dist     :", out)

    def test_gate_delegates_to_the_p2_runner(self):
        with mock.patch.object(self.mod, "run_runner", return_value=0) as runner:
            code, _out, _err = self.run_main("gate")
        self.assertEqual(code, 0)
        runner.assert_called_once_with("p2")

    def test_run_runner_spawns_the_check_runner_and_returns_its_code(self):
        done = subprocess.CompletedProcess(args=[], returncode=7)
        with mock.patch.object(self.mod.subprocess, "run", return_value=done) as run:
            code = self.mod.run_runner("p2")
        self.assertEqual(code, 7)
        argv = run.call_args.args[0]
        self.assertTrue(argv[1].endswith("check_runner.py"), argv)
        self.assertEqual(argv[2:], ["--mode", "p2"])

    def test_the_script_entrypoint_reports_through_the_error_wrapper(self):
        code, out = _fixture.run_inproc(self.root, "release.py", "status")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("versions :", out)

    def test_manifest_rewrites_the_file(self):
        code, out, _err = self.run_main("manifest")
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("manifest :", out)

    def test_publish_refuses_a_dirty_tree(self):
        with mock.patch.object(self.mod, "tree_is_dirty", return_value=True):
            code, _out, err = self.run_main("publish")
        self.assertEqual(code, 2)
        self.assertIn("working tree is dirty", err)

    def test_publish_stops_when_the_gate_fails(self):
        with (
            mock.patch.object(self.mod, "tree_is_dirty", return_value=False),
            mock.patch.object(self.mod, "run_runner", return_value=1),
        ):
            code, _out, err = self.run_main("publish")
        self.assertEqual(code, 1)
        self.assertIn("release gate failed", err)

    def test_publish_writes_the_manifest_and_names_the_next_step(self):
        with (
            mock.patch.object(self.mod, "tree_is_dirty", return_value=False),
            mock.patch.object(self.mod, "run_runner", return_value=0),
        ):
            code, out, _err = self.run_main("publish", "--title", "定版")
        self.assertEqual(code, 0, out[-400:])
        self.assertIn("manifest :", out)
        self.assertIn("git tag -a", out)

    def test_publish_may_run_from_a_dirty_tree_when_asked(self):
        with (
            mock.patch.object(self.mod, "tree_is_dirty", return_value=True),
            mock.patch.object(self.mod, "run_runner", return_value=0),
        ):
            code, out, _err = self.run_main("publish", "--allow-dirty")
        self.assertEqual(code, 0, out[-400:])


if __name__ == "__main__":
    unittest.main()
