#!/usr/bin/env python3
"""The failure matrix: every entry refuses the same way, with a reason.

A refusal has two halves — the message a person reads and the code a script
reacts to. This table lists the refusals a wrong invocation must produce; a new
entry point or a new guard is only done when it appears here too.
"""

from __future__ import annotations

import importlib
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import _fixture

TAGS = ('layer:infra', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class FailureMatrixTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.empty = os.path.join(self.tmp.name, 'not-a-book')
        os.makedirs(self.empty, exist_ok=True)
        self.cli = _fixture.load_module(self.root, 'cli')
        self.make = _fixture.load_module(self.root, 'make')
        self.tui = _fixture.load_module(self.root, 'tui')
        # the entries write BOOK_ROOT/BOOK_EDITION for their children; put the
        # selection back so the next suite does not inherit a deleted directory
        previous = {key: os.environ.get(key) for key in ('BOOK_ROOT', 'BOOK_EDITION')}
        active = self.make._config.current()
        self.addCleanup(self.make._config.reset, active)
        for key, value in previous.items():
            if value is None:
                self.addCleanup(os.environ.pop, key, None)
            else:
                self.addCleanup(os.environ.__setitem__, key, value)

    def invoke(self, module, argv: list[str]) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        code = 0
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = module.main(argv)
        except SystemExit as exc:      # argparse refusals
            code = exc.code if isinstance(exc.code, int) else 1
        return code, out.getvalue() + err.getvalue()

    # -- the matrix ------------------------------------------------------
    def matrix(self) -> tuple[tuple[str, object, list[str], int, str], ...]:
        return (
            ('make: missing book', self.make, ['check', '--book', self.empty],
             2, 'book.toml'),
            ('make: undeclared edition', self.make,
             ['check', '--book', self.root, '--edition', 'nope'], 2, '未声明'),
            ('make: unknown step', self.make, ['check', '--only', 'nope'], 2, 'nope'),
            ('cli: missing book', self.cli, ['status', '--book', self.empty],
             2, 'book.toml'),
            ('cli: unknown action', self.cli, ['no-such-action'], 2, 'invalid choice'),
            ('cli: force on a non-analyze action', self.cli,
             ['status', '--force'], 2, '--force'),
            ('cli: both flags', self.cli,
             ['analyze', '--force', '--refresh-facts'], 2, '不能同时使用'),
            ('cli: settings set without a value', self.cli,
             ['settings', 'set', 'title'], 2, 'usage'),
            ('tui: unknown book', self.tui, ['--once', 'status', '--book', self.empty],
             2, 'book.toml'),
        )

    def test_every_refusal_reports_its_reason_and_status(self):
        for name, module, argv, expected_code, fragment in self.matrix():
            with self.subTest(case=name):
                code, text = self.invoke(module, argv)
                self.assertEqual(code, expected_code, f'{name}: {text[-300:]}')
                self.assertIn(fragment, text, name)
                self.assertNotIn('Traceback', text, name)

    # -- the carrier -----------------------------------------------------
    def test_a_tool_error_carries_both_halves(self):
        _fixture.refresh_config(self.root)
        spec = importlib.import_module('lib._errors')
        error = spec.ToolError('boom', code=3)
        self.assertEqual(str(error), 'boom')
        self.assertEqual(error.exit_code, 3)

        def failing(argv):
            raise error
        self.assertEqual(spec.run(failing, []), 3)

    def test_a_script_that_fails_prints_one_line_and_no_traceback(self):
        result = _fixture.run(self.root, 'pdf_from_html.py')
        self.assertEqual(result.returncode, 1)
        self.assertIn('error: cannot read', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(len([line for line in result.stderr.splitlines() if line.strip()]), 1)


if __name__ == '__main__':
    unittest.main()
