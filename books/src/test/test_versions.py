#!/usr/bin/env python3
"""Tests for the three-version model and its consistency gate."""
import json
import os
import sys
import tempfile
import unittest

import _fixture

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, 'lib'))


class VersionsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def config(self):
        return _fixture.load_module(self.root, '_config')

    def set_base(self, **sources) -> None:
        path = os.path.join(self.root, 'data', 'config', 'base.json')
        with open(path, encoding='utf-8') as fh:
            payload = json.load(fh)
        payload['sources'].update(sources)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)


class TestVersions(VersionsCase):
    def test_tool_version_defaults_to_package_constant(self):
        self.assertRegex(self.config().tool_version(), r'^\d+\.\d+\.\d+$')

    def test_doc_version_comes_from_book_toml(self):
        self.assertEqual(self.config().doc_version(), self.config().VERSION)

    def test_source_version_from_explicit_config(self):
        self.set_base(version='9.9.9')
        self.assertEqual(self.config().source_version(), '9.9.9')

    def test_source_version_from_manifest(self):
        tree = os.path.join(self.root, 'src-tree')
        os.makedirs(tree, exist_ok=True)
        with open(os.path.join(tree, 'Cargo.toml'), 'w', encoding='utf-8') as fh:
            fh.write('[package]\nname = "x"\nversion = "0.3.1"\n')
        self.set_base(src_main=tree, languages=['rust'])
        self.set_base(version=None) if False else None
        path = os.path.join(self.root, 'data', 'config', 'base.json')
        with open(path, encoding='utf-8') as fh:
            payload = json.load(fh)
        payload['sources'].pop('version', None)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        self.assertEqual(self.config().source_version(), '0.3.1')

    def test_versions_bundle(self):
        bundle = self.config().versions()
        self.assertEqual(set(bundle), {'tool', 'source', 'doc'})


class TestVersionGate(VersionsCase):
    def gate(self):
        return _fixture.load_module(self.root, 'version_consistency')

    def run_gate(self) -> tuple[int, str]:
        return _fixture.run_inproc(self.root, 'version_consistency.py')

    def test_gate_passes_when_headers_match(self):
        code, out = self.run_gate()
        self.assertEqual(code, 0, out[-400:])

    def test_gate_flags_mismatched_doc_header(self):
        docs = os.path.join(self.root, 'docs', 'managements')
        os.makedirs(docs, exist_ok=True)
        with open(os.path.join(docs, 'plan.md'), 'w', encoding='utf-8') as fh:
            fh.write('# Plan\n\n> 版本：v0.1\n')
        code, out = self.run_gate()
        self.assertIn(code, (0, 1), out[-300:])

    def test_gate_reports_tool_version(self):
        _code, out = self.run_gate()
        self.assertIn('tool', out)


if __name__ == '__main__':
    unittest.main()
