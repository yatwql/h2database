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
        patcher = mock.patch.object(self.mod, 'HISTORY', self.history)
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


if __name__ == '__main__':
    unittest.main()
