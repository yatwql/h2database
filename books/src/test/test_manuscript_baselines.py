#!/usr/bin/env python3
"""The baseline inventory: what each accepted-state file records, and what is stale.

The command exists because the directory had grown eleven files in three shapes; these
cases pin the three things that make it useful — every shape is counted correctly, an
unclaimed or empty file is called out, and the command never writes anything.
"""

import io
import json
import os
import unittest
from contextlib import redirect_stdout

from _cases import FixtureCase

TAGS = ("layer:manuscript", "tier:fast")


class BaselineInventoryTest(FixtureCase):
    def baselines(self) -> str:
        folder = os.path.join(self.root, "data", "baselines")
        os.makedirs(folder, exist_ok=True)
        return folder

    def put(self, name, payload):
        with open(os.path.join(self.baselines(), name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def test_each_shape_is_counted_the_way_it_is_stored(self):
        self.put("captions-findings.json", {"updated": "2026-01-01", "accepted": ["a", "b"]})
        self.put("coverage.json", {"files": {"x.py": 100.0}})
        self.put("perf-baseline.json", {"reviewed": {"at": "2026-01-02T10:00:00"},
                                        "steps": {"tests": 70.0}})
        module = self.module("baselines")
        rows = {row["file"]: row for row in module.rows()}
        self.assertEqual(rows["captions-findings.json"]["count"], 2)
        self.assertEqual(rows["coverage.json"]["count"], 1)
        self.assertEqual(rows["perf-baseline.json"]["count"], 1)
        self.assertEqual(rows["perf-baseline.json"]["updated"], "2026-01-02")

    def test_an_unregistered_file_is_reported_not_hidden(self):
        self.put("mystery.json", {"accepted": ["x"]})
        module = self.module("baselines")
        rows = module.rows()
        self.assertEqual(rows[0]["shape"], "unknown")
        self.assertTrue(any("no gate claims it" in problem
                            for problem in module.problems(rows)))

    def test_an_empty_baseline_is_reported(self):
        self.put("loose-assertions.json", {"accepted": []})
        module = self.module("baselines")
        self.assertTrue(any("empty" in problem for problem in module.problems(module.rows())))

    def test_check_exits_non_zero_only_when_something_is_wrong(self):
        self.put("captions-findings.json", {"accepted": ["a"]})
        module = self.module("baselines")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(module.main([]), 0)
            self.assertEqual(module.main(["--check"]), 0)
        self.put("loose-assertions.json", {"accepted": []})
        with redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(["--check"]), 1)

    def test_json_mode_emits_the_same_rows(self):
        self.put("coverage.json", {"files": {"x.py": 100.0}})
        module = self.module("baselines")
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(module.main(["--json"]), 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["baselines"][0]["file"], "coverage.json")

    def test_an_empty_directory_says_so(self):
        module = self.module("baselines")
        self.assertEqual(module.rows(), [])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.assertEqual(module.main([]), 0)
        self.assertIn("no baselines", buffer.getvalue())

    def test_a_broken_file_is_named_with_its_error(self):
        with open(os.path.join(self.baselines(), "coverage.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{ not json")
        module = self.module("baselines")
        rows = module.rows()
        self.assertIn("无法读取", rows[0]["problem"])


if __name__ == "__main__":
    unittest.main()
