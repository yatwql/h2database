#!/usr/bin/env python3
"""LLM policy: allowed layers, secret-file hygiene and the CLI."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))

class LlmPolicyUnitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.policy = _fixture.load_module(BOOK_ROOT, 'llm_policy')

    def test_policy_block_is_read(self):
        pol = self.policy.policy()
        self.assertIn('llm_scenarios', pol)
        self.assertIn('chapter-draft', pol['llm_scenarios'])

    def test_offenders_lists_only_disallowed_layers(self):
        offenders = self.policy.offenders()
        self.assertFalse([o for o in offenders if o['layer'] in ('core', 'ingest', 'lib')])

    def test_example_key_file_must_stay_empty(self):
        self.assertEqual(self.policy.secret_files(), [])

    def test_a_tracked_key_file_is_reported(self):
        tracked = mock.Mock(returncode=0, stdout='books/data/config/llm_key.json\n', stderr='')
        with mock.patch.object(self.policy.subprocess, 'run', return_value=tracked):
            problems = self.policy.secret_files()
        self.assertTrue(any('tracked by git' in p for p in problems))

    def test_a_filled_example_key_file_is_reported(self):
        path = os.path.join(BOOK_ROOT, 'data', 'config', 'llm_key.example.json')
        with open(path, encoding='utf-8') as fh:
            original = fh.read()
        payload = json.loads(original)
        payload['keys'] = {'x': 'secret'}
        with mock.patch.object(self.policy, '_fsutil') as fsutil, \
                mock.patch.object(self.policy.subprocess, 'run',
                                  return_value=mock.Mock(stdout='', stderr='')):
            fsutil.read_text.return_value = json.dumps(payload)
            problems = self.policy.secret_files()
        self.assertTrue(any('filled in' in p for p in problems))

    def test_an_offending_import_is_detected(self):
        fake = os.path.join(self.tmp.name, 'audit', 'rogue.py')
        os.makedirs(os.path.dirname(fake), exist_ok=True)
        with open(fake, 'w', encoding='utf-8') as fh:
            fh.write('from lib import _llm\n')
        with mock.patch.object(self.policy.glob, 'glob', return_value=[fake]), \
                mock.patch.object(self.policy, 'PY_ROOT', self.tmp.name):
            offenders = self.policy.offenders()
        self.assertEqual(offenders[0]['layer'], 'audit')
        self.assertIn('rogue.py', offenders[0]['file'])

    def test_an_allowed_import_is_not_reported(self):
        fake = os.path.join(self.tmp.name, 'core', 'allowed.py')
        os.makedirs(os.path.dirname(fake), exist_ok=True)
        with open(fake, 'w', encoding='utf-8') as fh:
            fh.write('from lib import _llm\n')
        with mock.patch.object(self.policy.glob, 'glob', return_value=[fake]), \
                mock.patch.object(self.policy, 'PY_ROOT', self.tmp.name):
            self.assertEqual(self.policy.offenders(), [])

    def test_pycache_paths_are_skipped(self):
        fake = os.path.join(self.tmp.name, '__pycache__', 'x.py')
        with mock.patch.object(self.policy.glob, 'glob', return_value=[fake]), \
                mock.patch.object(self.policy, 'PY_ROOT', self.tmp.name):
            self.assertEqual(self.policy.offenders(), [])

    def test_json_output_reports_offenders(self):
        with mock.patch.object(self.policy, 'offenders',
                               return_value=[{'file': 'audit/x.py', 'layer': 'audit'}]), \
                redirect_stdout(io.StringIO()) as out:
            code = self.policy.main(['--json'])
        self.assertEqual(code, 1)
        self.assertIn('offenders', out.getvalue())

    def test_human_output_reports_pass(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.policy.main([])
        self.assertEqual(code, 0)
        self.assertIn('✅', buffer.getvalue())

    def test_json_output_lists_scenarios(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.policy.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, 0)
        self.assertIn('llm_scenarios', payload['policy'])

if __name__ == '__main__':
    unittest.main()
