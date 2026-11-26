#!/usr/bin/env python3
"""A toolchain failure carries its message and its exit code together."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
if os.path.join(TOOLS_DIR, 'lib') not in sys.path:
    sys.path.insert(0, os.path.join(TOOLS_DIR, 'lib'))


class ToolErrorTest(unittest.TestCase):
    def setUp(self):
        _fixture.load_module(_fixture.build_book(tempfile.mkdtemp()), 'make')
        self.ctx = __import__('lib._errors', fromlist=['ToolError', 'run'])
        self.ToolError = self.ctx.ToolError

    def test_the_message_and_the_status_travel_together(self):
        exc = self.ToolError('error: cannot read /x', code=2)
        self.assertEqual(str(exc), 'error: cannot read /x')
        self.assertEqual(exc.message, 'error: cannot read /x')
        self.assertEqual(exc.exit_code, 2)
        self.assertEqual(exc.code, 'error: cannot read /x')  # sys.exit(str) semantics
        self.assertIsInstance(exc, SystemExit)

    def test_the_default_status_is_one(self):
        self.assertEqual(self.ToolError('boom').exit_code, 1)

    def test_run_converts_the_pair(self):
        def main(argv):
            raise self.ToolError('error: cannot read /x', code=3)

        err = io.StringIO()
        with redirect_stderr(err):
            code = self.ctx.run(main, ['--json'])
        self.assertEqual(code, 3)
        self.assertIn('error: cannot read /x', err.getvalue())

    def test_run_returns_the_entry_points_own_code(self):
        self.assertEqual(self.ctx.run(lambda argv: 0, []), 0)
        self.assertEqual(self.ctx.run(lambda: 7), 7)
        self.assertEqual(self.ctx.run(lambda: None), 0)


class FsutilRaisesTest(unittest.TestCase):
    def setUp(self):
        _fixture.load_module(_fixture.build_book(tempfile.mkdtemp()), 'make')
        self.mod = __import__('lib._fsutil', fromlist=['read_text', 'load_json'])
        self.ToolError = __import__('lib._errors', fromlist=['ToolError']).ToolError

    def test_a_missing_file_raises_the_domain_error_not_a_bare_exit(self):
        with self.assertRaises(self.ToolError) as caught:
            self.mod.read_text(os.path.join(tempfile.mkdtemp(), 'nope.md'))
        self.assertIn('error: cannot read', str(caught.exception))

    def test_invalid_json_names_the_file(self):
        path = os.path.join(tempfile.mkdtemp(), 'broken.json')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('{not json')
        with self.assertRaises(self.ToolError) as caught:
            self.mod.load_json(path)
        self.assertIn('error: invalid JSON', str(caught.exception))


class EntryPointConversionTest(unittest.TestCase):
    """The message a reader sees and the code a script reacts to come from one place."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def test_a_missing_input_exits_one_with_the_reason_on_stderr(self):
        # pdf_from_html needs the merged HTML; without it the failure must stay a
        # message and a status rather than a traceback.
        failed = _fixture.run(self.root, 'pdf_from_html.py')
        self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
        self.assertIn('cannot read', failed.stderr)
        self.assertNotIn('Traceback', failed.stderr)

    def test_an_in_process_entry_point_reports_the_same_pair(self):
        code, out = _fixture.run_inproc(self.root, 'pdf_from_html.py')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('cannot read', out)


if __name__ == '__main__':
    unittest.main()
