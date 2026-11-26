#!/usr/bin/env python3
"""Tests for the markdown parsers the audits rely on.

Fixtures are inline strings written to a temporary file so the tests never
depend on the current manuscript contents.
"""

import importlib
import unittest

import _fixture
from _cases import TempFile

TAGS = ('layer:manuscript', 'tier:fast')

_fixture.ensure_tools_path()

_audit_index_xrefs = importlib.import_module('index_xrefs')

INDEX_FIXTURE = """# 索引

## A

- ACID —— §10.5
  - 与 MVCC 的关系 —— §9.6
  see also: MVCC, Undo Log

## B

- B-Tree —— §6.2
"""


class TestIndexParser(unittest.TestCase):
    def test_main_entries_parsed(self):
        with TempFile(INDEX_FIXTURE) as path:
            main, _sub, _sa, sections = _audit_index_xrefs.parse_index(path)
        self.assertTrue(sections)
        joined = ' '.join(main)
        self.assertIn('acid', joined.lower())

    def test_see_also_parsed(self):
        with TempFile(INDEX_FIXTURE) as path:
            _main, _sub, see_alsos, _sections = _audit_index_xrefs.parse_index(path)
        targets = [t for sa in see_alsos for t in sa['targets']]
        self.assertIn('MVCC', targets)

if __name__ == '__main__':
    unittest.main()
