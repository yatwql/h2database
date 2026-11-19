#!/usr/bin/env python3
"""Launch every entry point the way a user does: as a separate process.

An import-order regression inside a channel (path setup after the project
imports, for instance) is invisible to in-process tests but breaks `bookctl`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

import _fixture

TAGS = ('layer:infra', 'tier:fast')

_fixture.ensure_tools_path()

PY_ROOT = _fixture.TOOLS_DIR
BOOK_ROOT = os.path.dirname(PY_ROOT)
REPO_ROOT = os.path.dirname(BOOK_ROOT)

def run(script: str, *args: str, stdin: str | None = None):
    return subprocess.run([sys.executable, os.path.join(PY_ROOT, script), *args],
                          capture_output=True, text=True, cwd=REPO_ROOT,
                          input=stdin, check=False, timeout=120)

class ChannelLaunchTest(unittest.TestCase):
    def test_cli_status_runs_standalone(self):
        result = run('app/cli.py', 'status')
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertIn('bookwright', result.stdout)

    def test_tui_once_runs_standalone(self):
        result = run('app/tui.py', '--once', 'status')
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertIn('book', result.stdout)

    def test_tui_interactive_quits_on_q(self):
        result = run('app/tui.py', stdin='q')
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertNotIn('Traceback', result.stderr)

    def test_web_entry_reports_its_usage(self):
        result = run('app/web.py', '--help')
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertIn('--port', result.stdout)

    def test_make_entry_reports_its_usage(self):
        result = run('make.py', '--help')
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertIn('check', result.stdout)

    def test_launcher_script_reaches_the_menu(self):
        launcher = os.path.join(BOOK_ROOT, 'scripts', 'launch.sh')
        if not os.path.exists(launcher):
            self.skipTest('launch.sh not present')
        result = subprocess.run(['bash', launcher], capture_output=True, text=True,
                                cwd=BOOK_ROOT, input='q', check=False, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr[-500:])
        self.assertNotIn('ModuleNotFoundError', result.stderr)

if __name__ == '__main__':
    unittest.main()
