#!/usr/bin/env python3
"""llm_policy: the branches behind the report (git, the example key file, --json)."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class LlmPolicyBranchesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, "llm_policy")

    def write(self, name: str, text: str) -> str:
        path = os.path.join(self.root, "data", "config", name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def run_main(self, *args: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(list(args))
        return code, buffer.getvalue()

    def test_a_missing_or_broken_policy_file_reads_as_empty(self):
        self.assertEqual(self.mod.policy(), {})
        self.write("llm_settings.json", "{not json")
        self.assertEqual(self.mod.policy(), {})

    def test_the_policy_file_is_honoured(self):
        self.write("llm_settings.json", json.dumps({"policy": {"llm_scenarios": ["summary"]}}))
        self.assertEqual(self.mod.policy()["llm_scenarios"], ["summary"])

    def test_no_git_means_no_secret_findings(self):
        with mock.patch.object(self.mod.subprocess, "run", side_effect=OSError("no git")):
            self.assertEqual(self.mod.secret_files(), [])

    def test_a_tracked_key_file_is_reported(self):
        key = self.mod.SECRET_NAME
        done = subprocess.CompletedProcess(["git"], 0, stdout=f"data/config/{key}\n", stderr="")
        with mock.patch.object(self.mod.subprocess, "run", return_value=done):
            found = self.mod.secret_files()
        self.assertTrue(any("tracked by git" in item for item in found))

    def test_an_example_file_with_a_value_is_reported(self):
        done = subprocess.CompletedProcess(["git"], 0, stdout="", stderr="")
        self.write("llm_key.example.json", json.dumps({"keys": {"main": "sk-real"}}))
        with mock.patch.object(self.mod.subprocess, "run", return_value=done):
            found = self.mod.secret_files()
        self.assertTrue(any("is filled in" in item for item in found))

    def test_an_example_file_with_placeholder_values_is_fine(self):
        done = subprocess.CompletedProcess(["git"], 0, stdout="", stderr="")
        self.write("llm_key.example.json", json.dumps({"keys": {"main": "  "}}))
        with mock.patch.object(self.mod.subprocess, "run", return_value=done):
            self.assertEqual(self.mod.secret_files(), [])

    def test_an_unreadable_example_file_is_reported(self):
        done = subprocess.CompletedProcess(["git"], 0, stdout="", stderr="")
        self.write("llm_key.example.json", "{broken")
        with mock.patch.object(self.mod.subprocess, "run", return_value=done):
            found = self.mod.secret_files()
        self.assertTrue(any("invalid JSON" in item for item in found))

    def test_json_mode_reports_every_section(self):
        code, out = self.run_main("--json")
        payload = json.loads(out)
        self.assertEqual(sorted(payload), ["offenders", "policy", "secret_files"])
        self.assertEqual(code, 0 if not payload["offenders"] and not payload["secret_files"] else 1)

    def test_a_leak_makes_the_gate_fail_with_the_reason(self):
        done = subprocess.CompletedProcess(["git"], 0, stdout="", stderr="")
        self.write("llm_key.example.json", json.dumps({"keys": {"main": "sk-real"}}))
        with mock.patch.object(self.mod.subprocess, "run", return_value=done):
            code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("密钥文件不合规", out)

    def test_a_clean_book_says_which_scenarios_may_use_the_model(self):
        done = subprocess.CompletedProcess(["git"], 0, stdout="", stderr="")
        with mock.patch.object(self.mod.subprocess, "run", return_value=done):
            code, out = self.run_main()
        self.assertEqual(code, 0, out[-300:])
        self.assertIn("LLM 仅用于", out)

    def test_an_offending_import_is_named_with_its_layer(self):
        done = subprocess.CompletedProcess(["git"], 0, stdout="", stderr="")
        rogue = [{"file": "audit/rogue.py", "layer": "audit"}]
        with (
            mock.patch.object(self.mod, "offenders", return_value=rogue),
            mock.patch.object(self.mod.subprocess, "run", return_value=done),
        ):
            code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("LLM 使用越界 1 处", out)
        self.assertIn("audit/rogue.py（audit 层不应调用 LLM）", out)

    def test_running_the_script_as_a_program_reports_through_the_entrypoint(self):
        code, out = _fixture.run_inproc(self.root, "llm_policy.py")
        self.assertEqual(code, 0, out[-300:])


if __name__ == "__main__":
    unittest.main()
