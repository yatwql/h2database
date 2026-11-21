#!/usr/bin/env python3
"""CLI channel: the ingest switches reach `actions.run` and nothing else."""

from __future__ import annotations

import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:app', 'tier:fast')

_fixture.ensure_tools_path()


class CliSwitchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.cli = _fixture.load_module(self.root, 'cli')
        self.calls: list[tuple[str, dict]] = []
        patcher = mock.patch.object(
            self.cli.actions, 'run',
            side_effect=lambda action, **kwargs: (self.calls.append((action, kwargs)) or (0, '')))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_refresh_facts_reaches_the_shared_action(self):
        self.cli.main(['analyze', '--refresh-facts'])
        self.assertEqual(self.calls, [('analyze', {'force': False, 'refresh': True})])

    def test_force_reaches_the_shared_action(self):
        self.cli.main(['analyze', '--force'])
        self.assertEqual(self.calls, [('analyze', {'force': True, 'refresh': False})])

    def test_plain_analyze_passes_both_switches_off(self):
        self.cli.main(['analyze'])
        self.assertEqual(self.calls, [('analyze', {'force': False, 'refresh': False})])

    def test_the_switches_are_refused_on_other_actions(self):
        for action in ('status', 'build', 'check'):
            with self.subTest(action=action):
                self.calls.clear()
                self.assertEqual(self.cli.main([action, '--force']), 2)
                self.assertEqual(self.calls, [])

    def test_force_and_refresh_cannot_be_combined(self):
        self.assertEqual(self.cli.main(['analyze', '--force', '--refresh-facts']), 2)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
