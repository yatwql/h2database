"""The timing history is a file format: one JSON line per run, newest last.

Two readers depend on it — the perf gate and the menu's estimate — so the parsing and
the windowing are pinned here rather than through either of them.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()

_history = __import__('lib._perfhistory', fromlist=['history', 'path'])


class PathTest(unittest.TestCase):
    def test_the_file_sits_under_the_active_books_logs(self):
        path = _history.path()
        self.assertTrue(path.endswith(os.path.join('logs', 'perf-history.jsonl')))
        self.assertTrue(os.path.isabs(path))


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, 'perf.jsonl')

    def write(self, *lines: str) -> None:
        with open(self.path, 'w', encoding='utf-8') as handle:
            handle.write('\n'.join(lines) + '\n')

    def test_a_missing_file_has_no_history(self):
        self.assertEqual(_history.history(10, self.path), [])

    def test_the_newest_runs_are_kept(self):
        runs = [json.dumps({'mode': 'p0', 'seconds': value}) for value in (1, 2, 3)]
        self.write(*runs)
        kept = _history.history(2, self.path)
        self.assertEqual([run['seconds'] for run in kept], [2, 3])

    def test_blank_and_malformed_lines_are_skipped(self):
        self.write(json.dumps({'mode': 'p0', 'seconds': 1}), '', '{not json',
                   json.dumps({'mode': 'p1', 'seconds': 2}))
        kept = _history.history(10, self.path)
        self.assertEqual([run['seconds'] for run in kept], [1, 2])

    def test_a_zero_window_returns_nothing(self):
        self.write(json.dumps({'mode': 'p0', 'seconds': 1}))
        self.assertEqual(_history.history(0, self.path), [])

    def test_an_unreadable_file_is_treated_as_no_history(self):
        self.write(json.dumps({'mode': 'p0', 'seconds': 1}))
        with mock.patch('builtins.open', side_effect=OSError('denied')):
            self.assertEqual(_history.history(5, self.path), [])


if __name__ == '__main__':
    unittest.main()
