#!/usr/bin/env python3
"""Tests for the drafting contract and the call ledger.

The contract exists to keep a model from adding facts, so the cases below check the
rejection, not just the shape: an invented number must be named, a number that came from
the supplied facts must pass, and a rejected draft must be recorded as rejected.
"""

import importlib
import json
import os
import unittest
from unittest import mock

from _cases import FixtureCase

TAGS = ("layer:lib", "tier:fast")


class ContractTest(FixtureCase):
    def test_the_defaults_apply_when_the_book_declares_nothing(self):
        contract = self.module("_llm_contract")
        rules = contract.contract("lead")
        self.assertEqual(rules["max_chars"], 220)
        self.assertFalse(rules["allow_unknown_digits"])

    def test_a_book_override_wins_over_the_defaults(self):
        self.write("data/book/llm-tasks.toml",
                   "[default]\nmin_chars = 5\n\n[tasks.lead]\nmax_chars = 40\n")
        contract = self.module("_llm_contract")
        self.assertEqual(contract.contract("lead")["max_chars"], 40)
        self.assertEqual(contract.contract("lead")["min_chars"], 5)
        self.assertEqual(contract.contract("summary")["max_chars"], 220)

    def test_an_invalid_contract_file_is_reported_rather_than_ignored(self):
        self.write("data/book/llm-tasks.toml", "[default\nbroken\n")
        contract = self.module("_llm_contract")
        with self.assertRaises(SystemExit) as caught:
            contract.contract("lead")
        self.assertIn("invalid TOML", str(caught.exception))

    def test_numbers_missing_from_the_facts_are_rejected(self):
        contract = self.module("_llm_contract")
        facts = {"pkgs": 12, "lines": 3}
        problems = contract.check("lead", "本章覆盖 12 个包、3 行实现，导读先给出整体规模。", facts)
        self.assertEqual(problems, [])
        problems = contract.check("lead", "本章覆盖 12 个包、9999 行实现，导读先给出整体规模。", facts)
        self.assertEqual(len(problems), 1)
        self.assertIn("9999", problems[0])

    def test_a_task_may_allow_unknown_digits_explicitly(self):
        self.write("data/book/llm-tasks.toml", "[tasks.lead]\nallow_unknown_digits = true\n")
        contract = self.module("_llm_contract")
        self.assertEqual(contract.check("lead", "覆盖 9999 行，导读先给出整体规模。", {}), [])

    def test_length_and_paragraph_bounds_are_enforced(self):
        contract = self.module("_llm_contract")
        short = contract.check("lead", "太短", {})
        self.assertTrue(any("shorter than" in problem for problem in short))
        long_text = "字" * 300
        self.assertTrue(any("longer than" in problem
                            for problem in contract.check("lead", long_text, {})))
        two_paragraphs = "一段话。" * 10 + "\n\n" + "另一段。" * 10
        self.assertTrue(any("more than one paragraph" in problem
                            for problem in contract.check("lead", two_paragraphs, {})))


class LedgerTest(FixtureCase):
    def test_every_attempt_is_appended_with_stable_digests(self):
        contract = self.module("_llm_contract")
        contract.record("lead", "prompt", "response", "provider", [])
        contract.record("lead", "prompt", "response", "provider", ["invented 7"])
        with open(contract.ledger_path(), encoding="utf-8") as fh:
            lines = [json.loads(line) for line in fh]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0]["accepted"])
        self.assertEqual(lines[1]["problems"], ["invented 7"])
        self.assertEqual(lines[0]["prompt"], lines[1]["prompt"])
        self.assertEqual(lines[0]["prompt"], contract.digest("prompt"))
        self.assertEqual(len(lines[0]["config"]), 12)

    def test_a_ledger_that_cannot_be_written_warns_instead_of_raising(self):
        contract = self.module("_llm_contract")
        blocker = os.path.dirname(contract.ledger_path())
        with open(blocker, "w", encoding="utf-8") as fh:
            fh.write("not a directory")
        contract.record("lead", "p", "r", "provider", [])  # must not raise
        self.assertTrue(os.path.isfile(blocker))


class ProseContractTest(FixtureCase):
    def test_a_draft_that_invents_a_number_falls_back_to_the_deterministic_text(self):
        chapters = self.module("chapters")
        reply = "本章覆盖 7 个包、9999 行实现，导读先给出规模。"
        with mock.patch("lib._llm.complete", return_value=reply):
            text = chapters.prose("lead", "确定性文本。", enabled=True, pkgs=7, lines=1200)
        self.assertEqual(text, "确定性文本。")

    def test_a_draft_within_the_contract_is_used_and_recorded(self):
        chapters = self.module("chapters")
        reply = "本章覆盖 7 个包、1200 行实现，导读先给出整体规模。"
        with mock.patch("lib._llm.complete", return_value=reply):
            text = chapters.prose("lead", "确定性文本。", enabled=True, pkgs=7, lines=1200)
        self.assertNotEqual(text, "确定性文本。")
        # the same module instance prose() imported, so the ledger path matches
        contract = importlib.import_module("lib._llm_contract")
        with open(contract.ledger_path(), encoding="utf-8") as fh:
            self.assertTrue(json.loads(fh.readline())["accepted"])


if __name__ == "__main__":
    unittest.main()
