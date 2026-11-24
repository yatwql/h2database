#!/usr/bin/env python3
"""Perf baseline: record runs, compare with the median, flag regressions."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

TAGS = ('layer:audit', 'tier:fast')


def run(seconds: float, steps: list[tuple[str, float]], mode: str = 'p0') -> dict:
    return {'mode': mode, 'seconds': seconds,
            'steps': [{'step': name, 'seconds': value} for name, value in steps]}


class PerfBaselineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.history = os.path.join(self.tmp.name, 'perf.jsonl')
        self.mod = _fixture.load_module(BOOK_ROOT, 'perf_baseline')
        # no reviewed floor: this class is about the window-median fallback
        for name, value in (('HISTORY', self.history),
                            ('BASELINE', os.path.join(self.tmp.name, 'absent.json'))):
            patcher = mock.patch.object(self.mod, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_history(self, *runs: dict) -> None:
        lines = [json.dumps(item) + '\n' for item in runs]
        with open(self.history, 'w', encoding='utf-8') as fh:
            fh.writelines(lines)

    def test_recording_appends_one_line(self):
        self.mod.record(run(10, [('lint', 2)]))
        self.mod.record(run(11, [('lint', 2)]))
        with open(self.history, encoding='utf-8') as fh:
            self.assertEqual(len(fh.readlines()), 2)

    def test_missing_history_is_not_a_regression(self):
        report = self.mod.compare()
        self.assertFalse(report['ok'] is False)
        self.assertIn('not enough history', report.get('reason', ''))

    def test_a_stable_run_has_no_regression(self):
        self.write_history(run(10, [('lint', 2.0)]), run(10.5, [('lint', 2.1)]),
                           run(10.2, [('lint', 2.2)]))
        report = self.mod.compare()
        self.assertTrue(report['ok'])
        self.assertEqual(report['regressions'], [])

    def test_a_slow_step_is_reported(self):
        self.write_history(run(10, [('lint', 1.0)]), run(10, [('lint', 1.0)]),
                           run(40, [('lint', 30.0)]))
        report = self.mod.compare()
        self.assertFalse(report['ok'])
        self.assertEqual(report['regressions'][0]['step'], 'lint')

    def test_a_slow_total_is_reported(self):
        self.write_history(run(10, [('lint', 1.0)]), run(10, [('lint', 1.0)]),
                           run(90, [('lint', 1.5)]))
        steps = {item['step'] for item in self.mod.compare()['regressions']}
        self.assertIn('TOTAL', steps)

    def test_thresholds_come_from_style_policy(self):
        with mock.patch.object(self.mod, 'thresholds', return_value=(2.0, 0.0)):
            factor, slack = self.mod.thresholds()
        self.assertEqual((factor, slack), (2.0, 0.0))

    def test_main_is_advisory_by_default(self):
        self.write_history(run(10, [('lint', 1.0)]), run(10, [('lint', 1.0)]),
                           run(40, [('lint', 30.0)]))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.main([]), 0)

    def test_main_strict_fails_on_a_regression(self):
        self.write_history(run(10, [('lint', 1.0)]), run(10, [('lint', 1.0)]),
                           run(40, [('lint', 30.0)]))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.main(['--strict']), 1)

    def test_json_output_lists_the_regressions(self):
        self.write_history(run(10, [('lint', 1.0)]), run(10, [('lint', 1.0)]),
                           run(40, [('lint', 30.0)]))
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.mod.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload['ok'])


class WindowAndBaselineTest(unittest.TestCase):
    """The rolling window is scratch; the reviewed floor is the reference."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.history = os.path.join(self.tmp.name, 'perf.jsonl')
        self.baseline = os.path.join(self.tmp.name, 'perf-baseline.json')
        self.mod = _fixture.load_module(BOOK_ROOT, 'perf_baseline')
        for name, value in (('HISTORY', self.history), ('BASELINE', self.baseline)):
            patcher = mock.patch.object(self.mod, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_history(self, *runs: dict) -> None:
        with open(self.history, 'w', encoding='utf-8') as handle:
            handle.writelines(json.dumps(item) + '\n' for item in runs)

    def test_the_window_drops_the_oldest_runs_and_keeps_the_newest(self):
        with mock.patch.object(self.mod, 'window_runs', return_value=5):
            for index in range(12):
                self.mod.record(run(10 + index, [('lint', 1.0)]))
        with open(self.history, encoding='utf-8') as handle:
            kept = [json.loads(line) for line in handle if line.strip()]
        self.assertLessEqual(len(kept), 6)
        self.assertEqual(kept[-1]['seconds'], 21)

    def test_a_short_history_is_not_trimmed(self):
        with mock.patch.object(self.mod, 'window_runs', return_value=200):
            for index in range(3):
                self.mod.record(run(index, [('lint', 1.0)]))
        with open(self.history, encoding='utf-8') as handle:
            self.assertEqual(len(handle.readlines()), 3)

    def test_the_reviewed_baseline_is_the_reference_when_present(self):
        # four fast runs fix the floor; a slow run then reads as a regression even
        # though the window's own median has already moved with it
        self.write_history(run(10, [('lint', 2.0)]), run(10, [('lint', 2.0)]),
                           run(10, [('lint', 2.0)]), run(10, [('lint', 2.0)]),
                           run(40, [('lint', 20.0)]))
        with mock.patch.object(self.mod, 'thresholds', return_value=(1.5, 1.0)):
            self.assertEqual(self.mod.compare()['source'], 'history')
            self.mod.save_baseline('reviewer', 'after the split', window=4)
            report = self.mod.compare()
        self.assertEqual(report['source'], 'baseline')
        self.assertFalse(report['ok'])
        self.assertIn('lint', [item['step'] for item in report['regressions']])

    def test_saving_a_baseline_records_who_and_which_commit(self):
        self.write_history(run(10, [('lint', 2.0)]), run(11, [('lint', 4.0)]))
        path = self.mod.save_baseline('alice', 'tuned', window=2)
        with open(path, encoding='utf-8') as handle:
            payload = json.load(handle)
        self.assertEqual(payload['reviewed']['by'], 'alice')
        self.assertEqual(payload['reviewed']['reason'], 'tuned')
        self.assertEqual(payload['steps']['lint'], 3.0)
        self.assertEqual(payload['total'], 10.5)

    def test_the_cli_updates_the_baseline(self):
        self.write_history(run(10, [('lint', 2.0)]), run(11, [('lint', 4.0)]))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.mod.main(['--update-baseline',
                                            '--reviewed-by', 'bob']), 0)
        self.assertTrue(os.path.isfile(self.baseline))


if __name__ == '__main__':
    unittest.main()
