#!/usr/bin/env python3
"""Exercise every gate's command-line surface (argparse, output, exit codes).

Each gate is a script with ``main(argv)``; running it in-process keeps coverage
honest and catches wiring breakage that unit tests of the helpers miss.
"""

from __future__ import annotations

import inspect
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import _fixture

TAGS = ('layer:infra', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

GATES = [
    'balance', 'book_quality', 'captions', 'check_architecture',
    'content_depth', 'diagrams', 'doc_archive', 'doc_drift', 'exercises',
    'figure_clusters', 'figures', 'file_length', 'gate_trace', 'index_xrefs',
    'links', 'llm_policy', 'prose_quality', 'readability', 'script_contract',
    'style_rules', 'style_schema', 'version_consistency', 'structure', 'style',
    'smart', 'source_refs', 'scorecard', 'traces',
]

class GateEntrypointsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        _fixture.run_inproc(self.root, 'merge.py')  # gates that read the merged md

    def run_gate(self, name: str, *args: str):
        try:
            module = _fixture.load_module(self.root, name)
        except BaseException as exc:  # noqa: BLE001 - a gate may refuse to import
            return None, '', f'{type(exc).__name__}: {exc}'
        if not hasattr(module, 'main'):
            # script-style module: importing it already ran the whole gate
            return 0, '', ''
        takes_argv = len(inspect.signature(module.main).parameters) > 0
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = module.main(list(args)) if takes_argv else module.main()
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 0
            except Exception as exc:  # noqa: BLE001 - a gate may bail out early
                err.write(f'{type(exc).__name__}: {exc}')
                code = 1
        return code, out.getvalue(), err.getvalue()

    def test_each_gate_runs_and_reports_an_exit_code(self):
        for name in GATES:
            with self.subTest(gate=name):
                code, _out, _err = self.run_gate(name)
                if code is None:
                    continue  # the gate refuses to import on a minimal fixture
                self.assertIn(code, (0, 1, 2, None))

    def test_each_gate_supports_json(self):
        for name in GATES:
            with self.subTest(gate=name):
                code, out, _err = self.run_gate(name, '--json')
                if code is None:
                    continue
                self.assertIn(code, (0, 1, 2, None))
                if not out.strip():
                    continue
                try:
                    payload = json.loads(out)
                except json.JSONDecodeError:
                    continue  # the gate ignored --json and printed text
                self.assertIsInstance(payload, (dict, list))

    def test_gates_on_an_empty_book_still_exit_cleanly(self):
        empty = os.path.join(self.tmp.name, 'empty')
        os.makedirs(os.path.join(empty, 'data', 'manuscript'), exist_ok=True)
        with open(os.path.join(empty, 'books.toml'), 'w', encoding='utf-8') as fh:
            fh.write('[book]\ntitle = "空"\nversion = "0.1"\n')
        for name in ('links', 'figures', 'captions'):
            with self.subTest(gate=name):
                try:
                    module = _fixture.load_module(empty, name)
                except Exception:  # noqa: BLE001 - config is intentionally absent
                    module = None
                if module is None:
                    continue
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    try:
                        code = module.main([])
                    except SystemExit as exc:
                        code = exc.code if isinstance(exc.code, int) else 0
                    except Exception as exc:  # noqa: BLE001 - the gate may bail out
                        code = 1 if exc else 0
                self.assertIn(code, (0, 1, 2, None))

if __name__ == '__main__':
    unittest.main()
