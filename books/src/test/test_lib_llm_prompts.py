#!/usr/bin/env python3
"""Prompt resolution: the book's prompt, else its language's, else the built-in default."""

import types
import unittest
from unittest import mock

from _cases import FixtureCase

TAGS = ("layer:lib", "tier:fast")


class PromptResolutionTest(FixtureCase):
    """Resolution order with a fake book: the file plumbing is covered elsewhere."""

    def template_with(self, book_prompts=None, language_prompts=None, kind="lead"):
        module = self.module("_llm_prompts")
        book = types.SimpleNamespace(
            book_section=lambda name: {"prompts": book_prompts or {}} if name == "llm" else {},
            language=lambda: {"prompts": language_prompts or {}},
        )
        with mock.patch("lib._config.current", return_value=book):
            return module.template(kind)

    def test_the_book_wins_over_its_language(self):
        got = self.template_with({"lead": "book"}, {"lead": "language"})
        self.assertEqual(got, "book")

    def test_the_language_is_the_default(self):
        self.assertEqual(self.template_with({}, {"lead": "language"}), "language")

    def test_an_empty_override_falls_through_to_the_language(self):
        self.assertEqual(self.template_with({"lead": "  "}, {"lead": "language"}), "language")

    def test_nothing_configured_uses_the_built_in_default(self):
        self.assertIn("chapter lead", self.template_with({}, {}))

    def test_an_unknown_task_has_no_template(self):
        self.assertEqual(self.template_with({}, {}, kind="no-such-task"), "")

    def test_facts_are_filled_in_and_an_unknown_one_is_kept(self):
        module = self.module("_llm_prompts")
        book = types.SimpleNamespace(
            book_section=lambda name: {"prompts": {"lead": "覆盖 {pkgs} 个包，标题《{missing}》"}}
            if name == "llm" else {},
            language=lambda: {"prompts": {}},
        )
        with mock.patch("lib._config.current", return_value=book):
            rendered = module.render("lead", {"pkgs": 7})
        self.assertIn("7", rendered)
        self.assertIn("{missing}", rendered)

    def test_a_broken_template_does_not_crash_the_ingest(self):
        module = self.module("_llm_prompts")
        book = types.SimpleNamespace(
            book_section=lambda name: {"prompts": {"lead": "覆盖 {pkgs"}} if name == "llm" else {},
            language=lambda: {"prompts": {}},
        )
        with mock.patch("lib._config.current", return_value=book):
            self.assertIn("{pkgs", module.render("lead", {"pkgs": 1}))


if __name__ == "__main__":
    unittest.main()
