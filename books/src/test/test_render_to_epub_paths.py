#!/usr/bin/env python3
"""to_epub: pandoc present (stubbed) and pandoc missing."""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest

import _fixture

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))
PY_ROOT = _fixture.TOOLS_DIR

FAKE_PANDOC = """#!/bin/sh
if [ "$1" = "--version" ]; then
  echo "pandoc 3.1.0"
  exit 0
fi
out=""
prev=""
for arg in "$@"; do
  if [ "$prev" = "-o" ]; then out="$arg"; fi
  prev="$arg"
done
[ -n "$out" ] && printf '%%PDF-1.4 fake epub\\n' > "$out"
exit 0
"""


class ToEpubPathsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.bin_dir = os.path.join(self.tmp.name, 'bin')
        os.makedirs(self.bin_dir, exist_ok=True)
        pandoc = os.path.join(self.bin_dir, 'pandoc')
        with open(pandoc, 'w', encoding='utf-8') as fh:
            fh.write(FAKE_PANDOC)
        os.chmod(pandoc, os.stat(pandoc).st_mode | stat.S_IEXEC)

    def run_epub(self, *, with_pandoc: bool):
        env = dict(os.environ)
        env['BOOK_ROOT'] = self.root
        env['PATH'] = self.bin_dir if with_pandoc else '/usr/bin:/bin'
        return subprocess.run([sys.executable, os.path.join(PY_ROOT, 'render', 'to_epub.py')],
                              capture_output=True, text=True, env=env, timeout=180, check=False)

    def test_epub_is_built_when_pandoc_exists(self):
        result = self.run_epub(with_pandoc=True)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-600:])
        self.assertIn('pandoc detected', result.stdout)

    def test_missing_pandoc_explains_the_install_steps(self):
        result = self.run_epub(with_pandoc=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn('pandoc', (result.stdout + result.stderr).lower())


if __name__ == '__main__':
    unittest.main()
