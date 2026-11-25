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

TAGS = ('layer:audit', 'tier:fast')

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

    def test_the_guard_is_recognised_in_either_quote_style(self):
        body = ('"""d"""\ndef main(argv=None):\n    return 0\n\n'
                'if __name__ == "__main__":\n    main()\n')
        self.assertEqual(self.problems(body), [])

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
        self.assertEqual(code, 0, buffer.getvalue()[-300:])
        self.assertRegex(buffer.getvalue(), r'✅|OK|通过|PASS')
        self.assertTrue(buffer.getvalue())

    def test_json_output_lists_problems(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.contract.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertIn('problems', payload)

class DispatcherHelpTest(unittest.TestCase):
    """The wrapper's help comment names real actions."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.contract = _fixture.load_module(BOOK_ROOT, 'script_contract')

    def wrapper(self, body: str) -> str:
        path = os.path.join(self.tmp.name, 'bookctl')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(body)
        return path

    def test_an_action_the_cli_does_not_accept_is_reported(self):
        path = self.wrapper('#   books/scripts/bookctl llm "q"\n')
        with mock.patch.object(self.contract, 'DISPATCHER', path):
            problems = self.contract.check_dispatcher_help()
        self.assertEqual(len(problems), 1)
        self.assertIn('llm', problems[0])

    def test_a_real_action_passes(self):
        path = self.wrapper('#   books/scripts/bookctl llm-ask "q"\n')
        with mock.patch.object(self.contract, 'DISPATCHER', path):
            self.assertEqual(self.contract.check_dispatcher_help(), [])

    def test_wrapper_verbs_are_accepted(self):
        path = self.wrapper('#   books/scripts/bookctl make check\n'
                            '#   books/scripts/bookctl new ../x\n')
        with mock.patch.object(self.contract, 'DISPATCHER', path):
            self.assertEqual(self.contract.check_dispatcher_help(), [])

class ScriptContractSurfacesTest(unittest.TestCase):
    """A script that does not parse, and the CLI's two verdicts."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.contract = _fixture.load_module(BOOK_ROOT, "script_contract")

    def write(self, body: str, name: str = "demo.py") -> str:
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
        return path

    def test_a_script_that_does_not_parse_is_reported_with_its_position(self):
        broken = self.write('"""d"""\ndef main(:\n')
        buffer = io.StringIO()
        with mock.patch.object(self.contract, "scripts", return_value=[broken]), \
                mock.patch.object(self.contract, "check_dispatcher_help", return_value=[]), \
                redirect_stdout(buffer):
            self.assertEqual(self.contract.main([]), 1)
        self.assertIn("demo.py", buffer.getvalue())

    def test_main_prints_each_problem_and_exits_one(self):
        buffer = io.StringIO()
        with mock.patch.object(self.contract, "scripts", return_value=[]), \
                mock.patch.object(self.contract, "check_dispatcher_help",
                                  return_value=["缺 docstring"]), \
                redirect_stdout(buffer):
            self.assertEqual(self.contract.main([]), 1)
        self.assertIn("缺 docstring", buffer.getvalue())

    def test_the_gate_runs_as_a_script(self):
        code, out = _fixture.run_inproc(BOOK_ROOT, "script_contract.py", "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["count"], 0)


if __name__ == '__main__':
    unittest.main()
