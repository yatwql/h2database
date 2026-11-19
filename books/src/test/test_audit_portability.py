#!/usr/bin/env python3
"""Portability gate: encoding-explicit IO and an ASCII-locale probe."""
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


class EncodingScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(
            os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR)), 'portability')

    def write(self, name: str, body: str) -> str:
        path = os.path.join(self.tmp.name, name)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(body)
        return path

    def test_text_open_without_encoding_is_reported(self):
        path = self.write('a.py', 'open("x.md", "r")\n')
        self.assertEqual(len(self.mod.opens_without_encoding(path)), 1)

    def test_text_open_with_encoding_is_accepted(self):
        path = self.write('b.py', 'open("x.md", "r", encoding="utf-8")\n')
        self.assertEqual(self.mod.opens_without_encoding(path), [])

    def test_binary_open_is_accepted(self):
        path = self.write('c.py', 'open("x.bin", "rb")\n')
        self.assertEqual(self.mod.opens_without_encoding(path), [])

    def test_open_without_a_mode_is_accepted(self):
        path = self.write('d.py', 'open("x.md")\n')
        self.assertEqual(self.mod.opens_without_encoding(path), [])

    def test_variable_mode_is_accepted(self):
        path = self.write('e.py', 'mode = "r"\nopen("x.md", mode)\n')
        self.assertEqual(self.mod.opens_without_encoding(path), [])

    def test_syntax_errors_are_ignored(self):
        path = self.write('f.py', 'def broken(:\n')
        self.assertEqual(self.mod.opens_without_encoding(path), [])

    def test_encoding_problems_carry_a_location(self):
        path = self.write('g.py', 'open("x.md", "w")\n')
        with mock.patch.object(self.mod, 'python_files', return_value=[path]):
            problems = self.mod.encoding_problems()
        self.assertEqual(problems[0]['check'], 'ENCODING')
        self.assertIn('g.py', problems[0]['file'])


class LocaleProbeTest(unittest.TestCase):
    def setUp(self):
        self.mod = _fixture.load_module(
            os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR)), 'portability')

    def test_a_failing_probe_is_reported(self):
        failed = mock.Mock(returncode=1, stdout='', stderr='UnicodeEncodeError: boom')
        with mock.patch.object(self.mod.subprocess, 'run', return_value=failed):
            problems = self.mod.locale_probe()
        self.assertTrue(problems)
        self.assertEqual(problems[0]['check'], 'LOCALE')
        self.assertIn('exit 1', problems[0]['detail'])

    def test_a_clean_run_reports_nothing(self):
        ok = mock.Mock(returncode=0, stdout='ok', stderr='')
        with mock.patch.object(self.mod.subprocess, 'run', return_value=ok):
            self.assertEqual(self.mod.locale_probe(), [])

    def test_a_probe_that_cannot_run_is_reported(self):
        with mock.patch.object(self.mod.subprocess, 'run',
                               side_effect=OSError('no python')):
            problems = self.mod.locale_probe()
        self.assertIn('probe failed to run', problems[0]['detail'])


class PortabilityCliTest(unittest.TestCase):
    def setUp(self):
        self.mod = _fixture.load_module(
            os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR)), 'portability')

    def test_json_reports_the_problem_count(self):
        buffer = io.StringIO()
        with mock.patch.object(self.mod, 'scan', return_value=[]), redirect_stdout(buffer):
            code = self.mod.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertEqual((code, payload['count']), (0, 0))

    def test_human_output_lists_each_check(self):
        problem = {'check': 'ENCODING', 'file': 'x.py', 'line': 3, 'detail': 'no encoding'}
        buffer = io.StringIO()
        with mock.patch.object(self.mod, 'scan', return_value=[problem]), \
                redirect_stdout(buffer):
            code = self.mod.main([])
        self.assertEqual(code, 1)
        self.assertIn('[ENCODING]', buffer.getvalue())

    def test_the_real_tree_is_portable(self):
        code, out = _fixture.run_inproc(
            os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR)), 'portability.py')
        self.assertEqual(code, 0, out[-600:])


if __name__ == '__main__':
    unittest.main()
