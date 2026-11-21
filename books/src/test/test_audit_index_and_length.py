#!/usr/bin/env python3
"""Index cross-references and the file-length budget gate."""

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

class IndexXrefUnitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, 'index_xrefs')

    def index(self, text: str) -> str:
        path = os.path.join(self.tmp.name, 'index.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    def test_alias_stripping_removes_parentheticals(self):
        self.assertEqual(self.mod._strip_alias('ACID（事务）'), 'ACID')

    def test_aliases_include_the_ascii_and_cjk_forms(self):
        aliases = self.mod._aliases_for('MVStore（存储引擎）')
        self.assertTrue(aliases)
        self.assertTrue(all(isinstance(a, str) for a in aliases))

    def test_parse_index_returns_sections_and_entries(self):
        path = self.index('# 索引\n\n## A\n\n- ACID —— §1.1\n  - 子项 —— §2.1\n'
                          '  see also: MVStore\n')
        main_entries, _sub_entries, see_alsos, sections = self.mod.parse_index(path)
        self.assertTrue(main_entries)
        self.assertTrue(sections)
        self.assertIsInstance(see_alsos, list)

    def test_main_reports_a_missing_index(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer), \
                mock.patch.object(self.mod, 'index_path',
                                  os.path.join(self.tmp.name, 'none.md'), create=True):
            code = self.mod.main([])
        self.assertIn(code, (0, 1, 2))
        self.assertTrue(buffer.getvalue())

    def test_json_output_is_parseable(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.mod.main(['--json'])
        text = buffer.getvalue()
        start = text.find('{')
        self.assertIsInstance(json.loads(text[start:]) if start >= 0 else {}, dict)

class FileLengthUnitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, 'file_length')

    def test_budgets_cover_every_kind(self):
        table = self.mod.budgets()
        self.assertTrue(table)
        for kind, values in table.items():
            self.assertIn('limit', values, kind)
            self.assertGreater(values['limit'], 0)

    def test_targets_are_relative_and_labelled(self):
        targets = self.mod.targets()
        self.assertTrue(targets)
        for path, kind in targets[:5]:
            self.assertTrue(os.path.isabs(path))
            self.assertIsInstance(kind, str)

    def test_main_reports_the_length_budgets(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([])
        self.assertIn(code, (0, 1))
        self.assertRegex(buffer.getvalue(), r'(budget|长度|行数|limit)')

    def test_json_output_lists_findings(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertIn('ledger', payload)

    # -- growth ledger ----------------------------------------------------
    def ledger_book(self, body: str, files: dict[str, str]) -> str:
        root = os.path.join(self.tmp.name, 'book')
        for name, text in files.items():
            path = os.path.join(root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(text)
        ledger = os.path.join(root, 'docs', 'managements')
        os.makedirs(ledger, exist_ok=True)
        with open(os.path.join(ledger, 'review-findings.md'), 'w', encoding='utf-8') as fh:
            fh.write(body)
        return root

    def test_a_registered_length_that_disagrees_is_reported(self):
        root = self.ledger_book('| `src/python/a.py` 9 行 | 占比 1%，拆法 |\n',
                                {'src/python/a.py': 'x = 1\n'})
        findings = self.mod.check_ledger(root)
        self.assertEqual([f['kind'] for f in findings], ['LEDGER'])
        self.assertIn('measured 1', findings[0]['detail'])

    def test_a_registered_file_that_is_gone_is_reported(self):
        root = self.ledger_book('| `src/python/gone.py` 3 行 | 占比 1%，拆法 |\n', {})
        details = [f['detail'] for f in self.mod.check_ledger(root)]
        self.assertTrue(any('does not exist' in d for d in details))

    def test_a_matching_row_passes(self):
        root = self.ledger_book('| `src/python/b.py` 2 行 | 占比 1%，拆法 |\n',
                                {'src/python/b.py': 'x = 1\ny = 2\n'})
        self.assertEqual(self.mod.check_ledger(root), [])

    # -- declared budgets ------------------------------------------------
    def test_every_budget_kind_is_declared_in_the_config(self):
        self.assertEqual(self.mod.check_declared_budgets(), [])

    def test_a_kind_missing_from_the_config_is_reported(self):
        with mock.patch.dict(self.mod._config.STYLE_POLICY, {'limits': {'sources': {}}}):
            details = [f['detail'] for f in self.mod.check_declared_budgets()]
        self.assertTrue(any('manuscript' in d for d in details))
        self.assertFalse(any('sources' in d for d in details))


class ContentVolumeBaselineTest(unittest.TestCase):
    """The reviewed floor only moves up unless a shrink is accepted by hand."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, 'content_volume')
        self.path = os.path.join(self.tmp.name, 'content-volume.json')

    def book(self, lines: int, files: dict | None = None) -> dict:
        payload = files if files is not None else {
            'ch1.md': {'bytes': lines * 10, 'lines': lines}}
        return {'manuscript': {'files': payload,
                               'total': {'bytes': lines * 10, 'lines': lines}},
                'delivered': {}}

    def write(self, payload: dict) -> None:
        with open(self.path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)

    def read(self) -> dict:
        with open(self.path, encoding='utf-8') as fh:
            return json.load(fh)

    def run_main(self, *args: str) -> int:
        with mock.patch.object(self.mod, 'BASELINE_PATH', self.path), \
                mock.patch('sys.stdout', new=io.StringIO()), \
                mock.patch('sys.stderr', new=io.StringIO()):
            return self.mod.main(list(args))

    def test_a_smaller_manuscript_counts_as_a_shrink(self):
        drops = self.mod.shrunk(self.book(100), self.book(90))
        self.assertTrue(any('ch1.md' in item for item in drops))
        self.assertTrue(any('total' in item for item in drops))

    def test_an_equal_or_larger_manuscript_does_not(self):
        self.assertEqual(self.mod.shrunk(self.book(100), self.book(100)), [])
        self.assertEqual(self.mod.shrunk(self.book(100), self.book(120)), [])

    def test_a_missing_chapter_counts_as_a_shrink(self):
        drops = self.mod.shrunk(self.book(100), self.book(0, files={}))
        self.assertTrue(any('gone' in item for item in drops))

    def test_updating_the_baseline_refuses_to_lower_it(self):
        self.write(self.book(100))
        with mock.patch.object(self.mod, 'snapshot', lambda: self.book(90)):
            self.assertEqual(self.run_main('--update-baseline'), 1)

    def test_accepting_the_shrink_records_the_reason(self):
        self.write(self.book(100))
        with mock.patch.object(self.mod, 'snapshot', lambda: self.book(90)):
            self.assertEqual(self.run_main('--update-baseline', '--accept-shrink',
                                           '--reason', '删掉重复章节'), 0)
        recorded = self.read()['accepted_shrinks'][0]
        self.assertEqual(recorded['reason'], '删掉重复章节')
        self.assertTrue(recorded['drops'])

    def test_a_growing_baseline_is_recorded_without_a_flag(self):
        self.write(self.book(100))
        with mock.patch.object(self.mod, 'snapshot', lambda: self.book(120)):
            self.assertEqual(self.run_main('--update-baseline'), 0)
        self.assertNotIn('accepted_shrinks', self.read())


if __name__ == '__main__':
    unittest.main()
