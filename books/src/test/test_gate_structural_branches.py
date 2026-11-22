#!/usr/bin/env python3
"""Branches of the structure and source-reference gates that a healthy book skips.

These are configuration-shaped branches (an empty coverage table, a broken
chapter file, an unreadable baseline), so each case builds the fixture book it
needs instead of mutating a shared one.
"""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:infra', 'tier:fast')

_fixture.ensure_tools_path()


class StructureBranchesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def book(self, **extra) -> str:
        return _fixture.build_book(self.tmp.name, extra=extra)

    def run_gate(self, root: str, *args: str) -> tuple[int, str]:
        return _fixture.run_inproc(root, 'structure.py', *args)

    def test_a_book_without_a_coverage_table_falls_back_to_reading_order(self):
        root = self.book(**{'data/tmpl/book.toml': _fixture.BOOK_TOML.replace(
            '[chapters.coverage]\n"ch1-test.md" = [1]\n"ch2-test.md" = [2]\n',
            '[chapters.coverage]\n')})
        code, out = self.run_gate(root)
        self.assertIn(code, (0, 1), out[-400:])
        self.assertIn('ch1', out)

    def test_no_configured_required_sections_is_reported_as_such(self):
        root = self.book(**{'data/tmpl/book.toml': _fixture.BOOK_TOML.replace(
            'per_chapter = ["本章小结", "延伸思考"]', 'per_chapter = []')})
        code, out = self.run_gate(root)
        self.assertIn(code, (0, 1), out[-400:])
        self.assertIn('no required sections configured', out)

    def test_a_chapter_that_cannot_be_read_is_a_finding_not_a_crash(self):
        root = self.book()
        target = os.path.join(root, 'data', 'manuscript', 'ch2-test.md')
        os.remove(target)
        os.makedirs(target)          # a directory where a file is expected
        code, out = self.run_gate(root)
        self.assertEqual(code, 1)
        self.assertIn('cannot read', out)
        self.assertNotIn('Traceback', out)

    def test_a_missing_index_is_reported_by_the_index_section(self):
        root = self.book()
        target = os.path.join(root, 'data', 'manuscript', 'back', 'index.md')
        os.remove(target)
        code, out = self.run_gate(root)
        self.assertEqual(code, 1)
        self.assertIn('Index file not found', out)


class SourceRefsBranchesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.baseline = os.path.join(self.root, 'data', 'baselines',
                                     'source-symbol-baseline.json')
        # a tiny source tree inside this book: the fixture's default points outside
        # the temporary root, which would mean writing into the shared parent
        config = copy.deepcopy(_fixture.BASE_JSON)
        config['sources']['src_main'] = 'src/main'
        os.makedirs(os.path.join(self.root, 'data', 'config'), exist_ok=True)
        with open(os.path.join(self.root, 'data', 'config', 'base.json'),
                  'w', encoding='utf-8') as fh:
            json.dump(config, fh, ensure_ascii=False, indent=2)
        source = os.path.join(self.root, 'src', 'main', 'org', 'example')
        os.makedirs(source, exist_ok=True)
        with open(os.path.join(source, 'Widget0.java'), 'w', encoding='utf-8') as fh:
            fh.write('package org.example;\n\npublic class Widget0 {\n'
                     '    public void run() {\n    }\n}\n')

    def write_baseline(self, accepted: list[str]) -> None:
        os.makedirs(os.path.dirname(self.baseline), exist_ok=True)
        with open(self.baseline, 'w', encoding='utf-8') as fh:
            json.dump({'accepted': accepted}, fh)

    def test_prune_drops_entries_that_resolve_again(self):
        self.write_baseline(['ch1-test.md::Nope::missing'])
        code, out = _fixture.run_inproc(self.root, 'source_refs.py', '--prune')
        self.assertEqual(code, 0, out[-400:])
        with open(self.baseline, encoding='utf-8') as fh:
            self.assertNotIn('Nope::missing', json.load(fh).get('accepted', []))

    def test_a_broken_baseline_is_treated_as_empty(self):
        os.makedirs(os.path.dirname(self.baseline), exist_ok=True)
        with open(self.baseline, 'w', encoding='utf-8') as fh:
            fh.write('{not json')
        code, out = _fixture.run_inproc(self.root, 'source_refs.py')
        self.assertEqual(code, 0, out[-400:])
        self.assertIn('Resolved:', out)   # the run completed despite the bad file
        self.assertNotIn('Traceback', out)

    def test_json_mode_reports_the_counts(self):
        _code, out = _fixture.run_inproc(self.root, 'source_refs.py', '--json')
        payload = json.loads(out[out.rindex('{'):])  # the report is the final block
        self.assertIn('references', payload)
        self.assertIn('missing', payload)


if __name__ == '__main__':
    unittest.main()
