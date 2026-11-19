#!/usr/bin/env python3
"""Script contract: docstring, entry point, guard and --json rules."""
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


class ScriptContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.contract = _fixture.load_module(BOOK_ROOT, 'script_contract')

    def write(self, body: str, name: str = 'demo.py') -> str:
        path = os.path.join(self.tmp.name, name)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(body)
        return path

    def problems(self, body: str) -> list[str]:
        return self.contract.check(self.write(body))

    def test_missing_docstring_is_reported(self):
        self.assertTrue(any('docstring' in p for p in self.problems('import os\n')))

    def test_main_without_a_guard_is_reported(self):
        body = '"""d"""\ndef main():\n    return 0\n'
        self.assertTrue(any('__main__ guard' in p for p in self.problems(body)))

    def test_module_without_an_entry_point_is_reported(self):
        self.assertTrue(any('neither main()' in p for p in self.problems('"""d"""\nX = 1\n')))

    def test_script_style_module_passes(self):
        self.assertEqual(self.problems('"""d"""\nprint("hi")\n'), [])

    def test_main_with_guard_passes(self):
        body = ('"""d"""\ndef main(argv=None):\n    return 0\n\n'
                "if __name__ == '__main__':\n    main()\n")
        self.assertEqual(self.problems(body), [])

    def test_library_modules_are_exempt(self):
        with mock.patch.object(self.contract, '_config') as config:
            config.BOOK_ROOT = BOOK_ROOT
            listed = self.contract.scripts()
        self.assertFalse([p for p in listed if '/lib/' in p])
        self.assertFalse([p for p in listed if p.endswith('core/actions.py')])

    def test_main_passes_on_the_real_tree(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.contract.main([])
        self.assertIn(code, (0, 1))
        self.assertTrue(buffer.getvalue())

    def test_json_output_lists_problems(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.contract.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertIn('problems', payload)


if __name__ == '__main__':
    unittest.main()
