#!/usr/bin/env python3
"""Tier runner and release flow: modes, reports, manifest, hook wiring."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:infra', 'tier:fast')

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))
REPO_ROOT = os.path.dirname(BOOK_ROOT)
PY_ROOT = _fixture.TOOLS_DIR

class RunnerModesTest(unittest.TestCase):
    def setUp(self):
        self.runner = _fixture.load_module(BOOK_ROOT, 'check_runner')

    def test_mode_aliases_map_to_tiers(self):
        self.assertEqual(self.runner.resolve_mode('fast'), 'p0')
        self.assertEqual(self.runner.resolve_mode('full'), 'p1')
        self.assertEqual(self.runner.resolve_mode('release'), 'p2')

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.runner.resolve_mode('p9')

    def test_p0_steps_are_lint_gates_tests(self):
        _label, steps = self.runner.MODES['p0']
        self.assertEqual(steps, ('lint', 'fast-gates', 'tests'))

    def test_p2_adds_slow_suite_and_deliver(self):
        _label, steps = self.runner.MODES['p2']
        self.assertIn('slow', steps)
        self.assertIn('deliver', steps)

    def test_commands_use_derived_paths(self):
        command = self.runner._command('fast-gates')
        self.assertIn('check', command)
        self.assertIn('--only', command)
        # the make.py path must be absolute (derived), not a repo-relative literal
        self.assertTrue(os.path.isabs(command[1]), command)

    def test_run_stops_at_the_first_failure_and_archives(self):
        calls = []

        def fake_run_step(step, log_path, timeout=0):
            calls.append(step)
            return {'step': step, 'code': 1 if step == 'fast-gates' else 0, 'seconds': 0.0}

        with mock.patch.object(self.runner, 'run_step', side_effect=fake_run_step), \
                mock.patch.object(self.runner, 'report_paths',
                                  return_value=(os.path.join(tempfile.gettempdir(), 'l.log'),
                                                os.path.join(tempfile.gettempdir(), 'l.json'))), \
                mock.patch.object(self.runner._fsutil, 'write_text'), \
                redirect_stdout(io.StringIO()):
            summary = self.runner.run('p0')
        self.assertFalse(summary['ok'])
        self.assertEqual(summary['failed_step'], 'fast-gates')
        self.assertEqual(calls, ['lint', 'fast-gates'])

    def test_main_returns_one_when_a_step_fails(self):
        with mock.patch.object(self.runner, 'run',
                               return_value={'ok': False, 'mode': 'p0', 'steps': []}), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(self.runner.main(['--mode', 'p0']), 1)

    def test_main_json_mode_asks_the_runner_for_json(self):
        summary = {'ok': True, 'mode': 'p0', 'label': 'commit gate', 'seconds': 1.0,
                   'steps': [], 'log': '', 'json': ''}
        with mock.patch.object(self.runner, 'run', return_value=summary) as run, \
                redirect_stdout(io.StringIO()):
            self.runner.main(['--mode', 'p0', '--json'])
        self.assertTrue(run.call_args.kwargs['as_json'])

class ReleaseFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.release = _fixture.load_module(self.root, 'release')

    def test_status_reports_versions_and_artifacts(self):
        snapshot = self.release.status()
        self.assertIn('tool', snapshot['versions'])
        self.assertIn('artifacts', snapshot)

    def test_publish_refuses_a_dirty_tree(self):
        with mock.patch.object(self.release, 'tree_is_dirty', return_value=True), \
                redirect_stdout(io.StringIO()), \
                mock.patch('sys.stderr', new_callable=io.StringIO):
            code = self.release.main(['publish'])
        self.assertEqual(code, 2)

    def test_publish_stops_when_the_gate_fails(self):
        with mock.patch.object(self.release, 'tree_is_dirty', return_value=False), \
                mock.patch.object(self.release, 'run_runner', return_value=1), \
                redirect_stdout(io.StringIO()), \
                mock.patch('sys.stderr', new_callable=io.StringIO):
            code = self.release.main(['publish', '--title', 'x'])
        self.assertEqual(code, 1)

    def test_publish_writes_a_manifest_after_a_passing_gate(self):
        with mock.patch.object(self.release, 'tree_is_dirty', return_value=False), \
                mock.patch.object(self.release, 'run_runner', return_value=0), \
                mock.patch.object(self.release, 'write_manifest',
                                  return_value=os.path.join(self.root, 'release.json')), \
                redirect_stdout(io.StringIO()):
            code = self.release.main(['publish', '--title', '6.5'])
        self.assertEqual(code, 0)

    def test_manifest_records_versions_and_hashes(self):
        artifact = os.path.join(self.root, 'dist', 'a.md')
        os.makedirs(os.path.dirname(artifact), exist_ok=True)
        with open(artifact, 'w', encoding='utf-8') as fh:
            fh.write('payload')
        payload = self.release.write_manifest('title')
        with open(payload, encoding='utf-8') as fh:
            data = json.load(fh)
        self.assertIn('versions', data)
        self.assertIn('artifacts', data)

    def test_sha256_is_stable_and_tolerant(self):
        path = os.path.join(self.tmp.name, 'x.bin')
        with open(path, 'wb') as fh:
            fh.write(b'abc')
        self.assertEqual(self.release.sha256(path), self.release.sha256(path))
        self.assertEqual(self.release.sha256(os.path.join(self.tmp.name, 'missing')), '')

class HookWiringTest(unittest.TestCase):
    """The hooks and the tiers must not drift apart."""

    def hook(self, name: str) -> str:
        path = os.path.join(REPO_ROOT, '.githooks', name)
        self.assertTrue(os.path.isfile(path), f'{name} missing')
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_pre_commit_runs_the_p0_tier(self):
        text = self.hook('pre-commit')
        self.assertIn('--mode p0', text)
        self.assertIn('check_runner.py', text)

    def test_pre_push_runs_the_p1_tier(self):
        self.assertIn('--mode p1', self.hook('pre-push'))

    def test_installer_points_git_at_the_tracked_hooks(self):
        installer = os.path.join(os.path.dirname(os.path.dirname(PY_ROOT)),
                        'scripts', 'install-hooks.sh')
        with open(installer, encoding='utf-8') as fh:
            text = fh.read()
        self.assertIn('core.hooksPath .githooks', text)

if __name__ == '__main__':
    unittest.main()
