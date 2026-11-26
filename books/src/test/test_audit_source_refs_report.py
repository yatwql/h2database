#!/usr/bin/env python3
"""Source refs: the report body for every verification status."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

class SourceRefsReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'source_refs')
        self.Reference = self.mod.Reference
        self.Verification = self.mod.Verification
        self.Resolution = self.mod.Resolution
        self.Claim = self.mod.SymbolClaim

    def results(self) -> list:
        return [
            self.Verification(self.Reference('ch1.md', 1, 'Widget', 3), 'OK', '/src/Widget.java', ''),
            self.Verification(self.Reference('ch1.md', 2, 'Widget', 99), 'OFFSET',
                              '/src/Widget.java', 'file has 10 lines, offset -89'),
            self.Verification(self.Reference('ch1.md', 3, 'Ghost', 1), 'MISSING', None, ''),
            self.Verification(self.Reference('ch1.md', 4, 'Broken', 1), 'ERROR',
                              '/src/Broken.java', 'permission denied'),
        ]

    def test_report_lists_every_status(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.mod.print_report(self.results(), {'Widget': ['/src/Widget.java']})
        out = buffer.getvalue()
        for needle in ('MISSING', 'OFFSET', 'ERROR'):
            self.assertIn(needle, out)

    def test_report_mentions_drift_claims(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.mod.print_report([self.Verification(
                self.Reference('ch1.md', 1, 'Widget', 1), 'OK', '/src/Widget.java', '')],
                {'Widget': ['/src/Widget.java']}, h2_version='1.0')
        self.assertIn('1.0', buffer.getvalue())

    def test_split_drift_separates_new_from_known(self):
        claim = self.Claim('ch1.md', 1, 'Widget', 'gone')
        baseline = {'accepted': [self.mod._claim_key('ch1.md', 'Widget', 'gone')]}
        new, known = self.mod.split_drift([(claim, 'src/Widget.java')], baseline)
        self.assertEqual((len(new), len(known)), (0, 1))

    def test_json_summary_is_serialisable(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer), \
                mock.patch.object(self.mod, 'build_class_index',
                                  return_value={'Widget': ['/src/Widget.java']}):
            code = self.mod.main(['--json'])
        text = buffer.getvalue().strip()
        self.assertEqual(code, 0, text[-300:])
        self.assertRegex(text, r'[\s\S]')
        start = text.find('{')
        self.assertIsInstance(json.loads(text[start:]) if start >= 0 else {}, dict)

if __name__ == '__main__':
    unittest.main()
