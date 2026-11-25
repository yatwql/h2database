#!/usr/bin/env python3
"""CLI channel: the ingest switches reach `actions.run` and nothing else."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

import _fixture

TAGS = ("layer:app", "tier:fast")

_fixture.ensure_tools_path()


class CliSwitchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.cli = _fixture.load_module(self.root, "cli")
        self.calls: list[tuple[str, dict]] = []
        patcher = mock.patch.object(
            self.cli.actions,
            "run",
            side_effect=lambda action, **kwargs: self.calls.append((action, kwargs)) or (0, ""),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        # the CLI writes BOOKS_DIR/BOOK_ROOT for child processes; a test must not
        # leave those pointing at a directory it is about to delete
        for name in ("BOOKS_DIR", "BOOK_ROOT"):
            previous = os.environ.get(name)
            self.addCleanup(
                lambda n=name, v=previous: (
                    os.environ.__setitem__(n, v) if v is not None else os.environ.pop(n, None)
                )
            )

    def switches(self) -> dict:
        """The action kwargs without the book selection every call carries."""
        return {
            key: value for key, value in self.calls[0][1].items() if key not in ("book", "edition")
        }

    def test_refresh_facts_reaches_the_shared_action(self):
        self.cli.main(["analyze", "--refresh-facts"])
        self.assertEqual(self.calls[0][0], "analyze")
        self.assertEqual(self.switches(), {"force": False, "refresh": True})

    def test_force_reaches_the_shared_action(self):
        self.cli.main(["analyze", "--force"])
        self.assertEqual(self.switches(), {"force": True, "refresh": False})

    def test_plain_analyze_passes_both_switches_off(self):
        self.cli.main(["analyze"])
        self.assertEqual(self.switches(), {"force": False, "refresh": False})

    def test_every_action_carries_the_resolved_book(self):
        self.cli.main(["analyze"])
        self.assertTrue(self.calls[0][1]["book"].endswith(os.path.basename(self.root)))
        self.assertEqual(self.calls[0][1]["edition"], "")

    def test_explicit_book_wins_over_the_environment(self):
        other = _fixture.build_book(os.path.join(self.tmp.name, "other", "book"))
        self.calls.clear()
        self.cli.main(["analyze", "--book", other])
        self.assertEqual(self.calls[0][1]["book"], other)

    def test_a_directory_without_book_toml_is_refused(self):
        empty = os.path.join(self.tmp.name, "empty")
        os.makedirs(empty, exist_ok=True)
        self.assertEqual(self.cli.main(["analyze", "--book", empty]), 2)
        self.assertEqual(self.calls, [])

    def test_the_switches_are_refused_on_other_actions(self):
        for action in ("status", "build", "check"):
            with self.subTest(action=action):
                self.calls.clear()
                self.assertEqual(self.cli.main([action, "--force"]), 2)
                self.assertEqual(self.calls, [])

    def test_force_and_refresh_cannot_be_combined(self):
        self.assertEqual(self.cli.main(["analyze", "--force", "--refresh-facts"]), 2)
        self.assertEqual(self.calls, [])

    def test_a_books_directory_with_one_book_is_used_directly(self):
        library = os.path.join(self.tmp.name, "library")
        only = _fixture.build_book(os.path.join(library, "only-book"))
        self.calls.clear()
        self.cli.main(["analyze", "--books-dir", library])
        self.assertEqual(self.calls[0][1]["book"], only)

    def test_several_books_are_listed_instead_of_guessed(self):
        library = os.path.join(self.tmp.name, "library2")
        _fixture.build_book(os.path.join(library, "one"))
        _fixture.build_book(os.path.join(library, "two"))
        self.calls.clear()
        self.assertEqual(self.cli.main(["analyze", "--books-dir", library]), 2)
        self.assertEqual(self.calls, [])

    def test_an_unreadable_book_toml_in_the_library_is_named_as_such(self):
        library = os.path.join(self.tmp.name, "library4")
        _fixture.build_book(os.path.join(library, "good"))
        broken = os.path.join(library, "broken", "data", "book")
        os.makedirs(broken)
        with open(os.path.join(broken, "book.toml"), "w", encoding="utf-8") as fh:
            fh.write("[book\ntitle = 1\n")
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            self.assertEqual(self.cli._book_from_dir(library), ("", 2))
        self.assertIn("（配置读不出）", stderr.getvalue())

    def test_llm_ask_passes_its_prompt_and_scenario(self):
        self.calls.clear()
        self.cli.main(["llm-ask", "总结", "第三章", "--scenario", "deep"])
        self.assertEqual(self.calls[0][0], "llm-ask")
        self.assertEqual(self.switches(), {"prompt": "总结 第三章", "scenario": "deep"})

    def test_an_empty_books_directory_is_an_error(self):
        empty = os.path.join(self.tmp.name, "empty-library")
        os.makedirs(empty, exist_ok=True)
        self.assertEqual(self.cli.main(["analyze", "--books-dir", empty]), 2)

    def test_the_environment_overrides_the_library(self):
        library = os.path.join(self.tmp.name, "library3")
        os.makedirs(library, exist_ok=True)
        os.environ["BOOKS_DIR"] = library
        cfg = self.cli._config.Config(self.root)
        self.assertEqual(cfg.library_dir(), os.path.abspath(library))


if __name__ == "__main__":
    unittest.main()
