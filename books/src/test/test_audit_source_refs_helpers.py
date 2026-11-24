#!/usr/bin/env python3
"""Unit tests for the helper functions behind the audits.

These target the pure logic (counting, parsing, clustering, PDF checks) that the
end-to-end tests exercise only indirectly.
"""

import importlib.util
import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:audit', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

HAS_PYPDF = importlib.util.find_spec('pypdf') is not None

class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def module(self, name: str):
        return _fixture.load_module(self.root, name)

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

class TestSourceFreshnessHelpers(FixtureCase):
    def test_resolve_and_verify(self):
        sfc = self.module('source_refs')
        with tempfile.TemporaryDirectory() as tmp:
            java = os.path.join(tmp, 'MVStore.java')
            with open(java, 'w', encoding='utf-8') as fh:
                fh.write('class MVStore {\n  void open() {}\n}\n')
            index = {'MVStore': [java]}
            ref = sfc.Reference('ch1.md', 3, 'MVStore', 2)
            resolved = sfc.resolve_references([ref], index)
            self.assertEqual(resolved[0].status, 'FOUND')
            checks = sfc.verify_line_numbers(resolved)
            self.assertEqual(checks[0].status, 'OK')

    def test_verify_line_numbers_flags_offset(self):
        sfc = self.module('source_refs')
        with tempfile.TemporaryDirectory() as tmp:
            java = os.path.join(tmp, 'A.java')
            with open(java, 'w', encoding='utf-8') as fh:
                fh.write('class A {}\n')
            index = {'A': [java]}
            resolved = sfc.resolve_references([sfc.Reference('ch.md', 1, 'A', 99)], index)
            checks = sfc.verify_line_numbers(resolved)
            self.assertEqual(checks[0].status, 'OFFSET')

    def test_missing_class_reported(self):
        sfc = self.module('source_refs')
        resolved = sfc.resolve_references(
            [sfc.Reference('ch.md', 1, 'NoSuchClass', 1)], {})
        self.assertEqual(resolved[0].status, 'MISSING')

    def test_ambiguous_class_reported(self):
        sfc = self.module('source_refs')
        resolved = sfc.resolve_references(
            [sfc.Reference('ch.md', 1, 'Dup', 1)], {'Dup': ['a.java', 'b.java']})
        self.assertEqual(resolved[0].status, 'AMBIGUOUS')

    def test_claim_key_is_stable(self):
        sfc = self.module('source_refs')
        a = sfc._claim_key('ch1.md', 'MVMap', 'open')
        b = sfc._claim_key('ch1.md', 'MVMap', 'open')
        self.assertEqual(a, b)
        self.assertNotEqual(a, sfc._claim_key('ch2.md', 'MVMap', 'open'))

if __name__ == '__main__':
    unittest.main()


class PrefixFallbackTest(unittest.TestCase):
    """An unconfigured package prefix is named as unknown, not left empty."""

    def setUp(self):
        self.mod = _fixture.load_module(_fixture.build_book(tempfile.mkdtemp()), 'source_refs')

    def test_a_missing_prefix_reads_as_unknown(self):
        with mock.patch.dict(self.mod._config.SOURCES, {}, clear=True):
            self.assertEqual(self.mod.package_prefix(), 'unknown')

    def test_a_configured_prefix_is_returned(self):
        with mock.patch.dict(self.mod._config.SOURCES, {'package_prefix': 'org.x'}):
            self.assertEqual(self.mod.package_prefix(), 'org.x')
