#!/usr/bin/env python3
"""Version consistency: doc headers, the merged manifest and unset versions."""

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

class VersionConsistencyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'version_consistency')

    def doc(self, text: str) -> None:
        path = os.path.join(self.root, 'docs', 'managements', 'sample.md')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)

    def merged(self, manifest: str) -> None:
        path = os.path.join(self.root, 'dist', 'test-book.md')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(manifest + '\n\n# 第1章 测试\n')

    def run_main(self, *args: str):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(list(args))
        return code, buffer.getvalue()

    def test_a_matching_header_passes(self):
        version = self.mod._config.versions()['doc']
        self.doc(f'> 版本：v{version}\n')
        code, out = self.run_main()
        self.assertEqual(code, 0, out)

    def test_a_mismatched_header_fails(self):
        self.doc('> 版本：v0.0\n')
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn('v0.0', out)

    def test_a_stale_merged_manifest_fails(self):
        versions = self.mod._config.versions()
        self.merged(f'<!-- versions: tool=0.0 source={versions["source"]} doc={versions["doc"]} -->')
        code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn('manifest', out)

    def test_a_current_merged_manifest_passes(self):
        v = self.mod._config.versions()
        self.merged(f'<!-- versions: tool={v["tool"]} source={v["source"]} doc={v["doc"]} -->')
        code, out = self.run_main()
        self.assertEqual(code, 0, out)

    def test_unset_tool_version_is_a_problem(self):
        with mock.patch.object(self.mod._config, 'versions',
                               return_value={'tool': 'unknown', 'source': '1', 'doc': '1'}):
            code, out = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn('tool version is not set', out)

    def test_unknown_source_version_is_a_warning(self):
        with mock.patch.object(self.mod._config, 'versions',
                               return_value={'tool': '1', 'source': 'unknown', 'doc': '1'}):
            code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn('warn', out)

    def test_an_external_source_version_is_only_a_warning(self):
        # the analysed source is an input, not part of this repository
        with mock.patch.object(self.mod._config, 'versions',
                               return_value={'tool': '1', 'source': 'unknown', 'doc': '1'}):
            self.merged('<!-- versions: tool=1 source=unknown doc=1 -->')
            code, out = self.run_main()
        self.assertEqual(code, 0, out)
        self.assertIn('source version', out)

    def test_json_output_reports_every_section(self):
        code, out = self.run_main('--json')
        payload = json.loads(out)
        self.assertIn(code, (0, 1))
        for key in ('versions', 'problems', 'warnings'):
            self.assertIn(key, payload)

if __name__ == '__main__':
    unittest.main()
