#!/usr/bin/env python3
"""Cross-platform parity: every shell wrapper has a PowerShell twin.

The toolchain is developed on Linux and used on Windows, so a missing `.ps1`
means a workflow that silently only exists on one side. These checks are static
(running PowerShell on Linux is not available), which is why they are cheap.
"""

from __future__ import annotations

import os
import re
import unittest

import _fixture

TAGS = ('layer:infra', 'tier:fast')

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))
SCRIPTS = os.path.join(BOOK_ROOT, 'scripts')
PY_ROOT = _fixture.TOOLS_DIR

def read_text(path: str) -> str:
    with open(path, encoding='utf-8') as fh:
        return fh.read()

def pathlib_text(name: str) -> str:
    return read_text(os.path.join(SCRIPTS, name))

class WrapperParityTest(unittest.TestCase):
    def shells(self) -> list[str]:
        """Shell wrappers, including the extensionless dispatcher `bookctl`."""
        names = [n for n in os.listdir(SCRIPTS) if n.endswith('.sh')]
        if os.path.isfile(os.path.join(SCRIPTS, 'bookctl')):
            names.append('bookctl.sh')
        return sorted(names)

    def powershells(self) -> list[str]:
        return sorted(n for n in os.listdir(SCRIPTS) if n.endswith('.ps1'))

    def stem(self, name: str) -> str:
        return name.rsplit('.', 1)[0]

    def test_every_shell_wrapper_has_a_powershell_twin(self):
        ps = {self.stem(n) for n in self.powershells()}
        missing = [n for n in self.shells() if self.stem(n) not in ps]
        self.assertEqual(missing, [], f'shell wrappers without a .ps1 twin: {missing}')

    def test_every_powershell_wrapper_has_a_shell_twin(self):
        sh = {self.stem(n) for n in self.shells()}
        missing = [n for n in self.powershells() if self.stem(n) not in sh]
        self.assertEqual(missing, [], f'PowerShell wrappers without a .sh twin: {missing}')

    def test_wrappers_target_the_same_entry_points(self):
        entries = ('check_runner.py', 'release.py', 'scaffold.py', 'cli.py', 'make.py',
                   'order_dependence.py', 'perf_baseline.py', 'failure_extract.py')
        real = [n for n in self.shells() if n != 'bookctl.sh'] + self.powershells()
        for name in real:
            with self.subTest(script=name):
                text = pathlib_text(name)
                if self.stem(name) in ('bookctl', 'launch', 'bootstrap'):
                    continue  # dispatchers and environment setup forward verbatim
                self.assertTrue(any(entry in text for entry in entries)
                                or 'check.sh' in text or 'check.ps1' in text,
                                f'{name} does not name a python entry point')

    def test_wrappers_forward_arguments(self):
        for name in ('check-fast.sh', 'check-full.sh', 'check-release.sh'):
            with self.subTest(script=name):
                self.assertIn('"$@"', pathlib_text(name))

    def test_powershell_wrappers_forward_arguments(self):
        for name in ('check.ps1', 'release.ps1', 'new-book.ps1'):
            with self.subTest(script=name):
                self.assertRegex(pathlib_text(name), r'(@args|@Extra|@Rest)')

class HookPortabilityTest(unittest.TestCase):
    """Hooks are POSIX shell; Windows users get the same tiers via scripts/."""

    def test_hooks_are_posix_shell_with_a_windows_fallback_documented(self):
        hooks = os.path.join(os.path.dirname(BOOK_ROOT), '.githooks')
        for name in ('pre-commit', 'pre-push'):
            with self.subTest(hook=name):
                path = os.path.join(hooks, name)
                text = read_text(path)
                self.assertTrue(text.startswith('#!/usr/bin/env bash'))
                self.assertIn('--no-verify', text)

    def test_installers_exist_for_both_platforms(self):
        for name in ('install-hooks.sh', 'install-hooks.ps1'):
            with self.subTest(installer=name):
                self.assertTrue(os.path.isfile(os.path.join(SCRIPTS, name)))

    def test_python_entry_points_do_not_shell_out_with_posix_only_commands(self):
        pattern = re.compile(r"subprocess\.\w+\(\s*\[\s*'(which|grep|sed|awk)'")
        offenders = []
        for base, _dirs, files in os.walk(PY_ROOT):
            if '__pycache__' in base:
                continue
            for name in files:
                if not name.endswith('.py'):
                    continue
                path = os.path.join(base, name)
                with open(path, encoding='utf-8') as fh:
                    if pattern.search(fh.read()):
                        offenders.append(os.path.relpath(path, PY_ROOT))
        self.assertEqual(offenders, [], f'POSIX-only shell calls: {offenders}')

if __name__ == '__main__':
    unittest.main()
