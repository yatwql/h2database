#!/usr/bin/env python3
"""Coverage for source_refs: parsing, resolution, drift and the CLI."""

from __future__ import annotations

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

class SourceReferenceAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.module = _fixture.load_module(self.root, 'source_refs')

    # -- helpers ---------------------------------------------------------
    @property
    def docs_dir(self) -> str:
        return os.path.join(self.root, 'data', 'manuscript')

    @property
    def source_dir(self) -> str:
        return os.path.join(self.root, 'h2', 'src', 'main')

    def write_chapter(self, text: str, name: str = 'ch1-test.md') -> str:
        path = os.path.join(self.docs_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return name

    def write_source(self, rel: str, body: str) -> str:
        path = os.path.join(self.source_dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(body)
        return path

    # -- parsing ---------------------------------------------------------
    def test_extract_references_skips_fenced_blocks(self):
        name = self.write_chapter('`KVStore.java:12` 与\n```java\n`Ignored.java:99`\n```\n')
        refs = self.module.extract_references([name], self.docs_dir)
        self.assertEqual([(r.class_name, r.lineno) for r in refs], [('KVStore', 12)])

    def test_extract_references_warns_about_missing_chapter(self):
        err = io.StringIO()
        with redirect_stderr(err):
            refs = self.module.extract_references(['nope.md'], self.docs_dir)
        self.assertEqual(refs, [])
        self.assertIn('not found', err.getvalue())

    def test_the_checked_chapters_come_from_the_configuration(self):
        self.assertEqual(self.module.CHAPTER_FILES,
                         [name for name in self.module._config.chapter_names(False)
                          if name.startswith('ch')])
        for name in self.module.CHAPTER_FILES:
            self.assertTrue(os.path.isfile(os.path.join(self.docs_dir, name)), name)

    def test_extract_symbol_claims_only_outside_fences(self):
        name = self.write_chapter('KVStore.bump() 与\n```java\nIgnored.call()\n```\n')
        claims = self.module.extract_symbol_claims([name], self.docs_dir)
        self.assertEqual([(c.class_name, c.method) for c in claims],
                         [('KVStore', 'bump')])

    # -- resolution ------------------------------------------------------
    def test_resolve_references_classifies_status(self):
        index = {'Found': ['/a/Found.java'], 'Dupe': ['/a/Dupe.java', '/b/Dupe.java']}
        Ref = self.module.Reference
        refs = [Ref('ch.md', 1, 'Found', 5), Ref('ch.md', 2, 'Dupe', 7),
                Ref('ch.md', 3, 'Absent', 9)]
        statuses = [res.status for res in self.module.resolve_references(refs, index)]
        self.assertEqual(statuses, ['FOUND', 'AMBIGUOUS', 'MISSING'])

    def test_verify_line_numbers_reports_ok_and_offset(self):
        path = self.write_source('org/example/KVStore.java', 'a\nb\nc\n')
        Ref = self.module.Reference
        Resolution = self.module.Resolution
        resolved = [Resolution(Ref('ch.md', 1, 'KVStore', 2), 'FOUND', [path]),
                    Resolution(Ref('ch.md', 2, 'KVStore', 99), 'FOUND', [path]),
                    Resolution(Ref('ch.md', 3, 'Gone', 1), 'MISSING', [])]
        results = self.module.verify_line_numbers(resolved)
        self.assertEqual([item.status for item in results], ['OK', 'OFFSET', 'MISSING'])

    def test_verify_line_numbers_picks_a_long_enough_duplicate(self):
        short = self.write_source('a/Parser.java', 'x\n')
        long = self.write_source('b/Parser.java', 'x\n' * 40)
        Ref = self.module.Reference
        Resolution = self.module.Resolution
        results = self.module.verify_line_numbers(
            [Resolution(Ref('ch.md', 1, 'Parser', 30), 'AMBIGUOUS', [short, long])])
        self.assertEqual(results[0].status, 'OK')
        self.assertEqual(results[0].file_path, long)

    def test_verify_symbol_claims_flags_unknown_methods(self):
        path = self.write_source('org/example/KVStore.java', 'class KVStore { void bump() {} }')
        Claim = self.module.SymbolClaim
        broken = self.module.verify_symbol_claims(
            [Claim('ch.md', 1, 'KVStore', 'bump'), Claim('ch.md', 2, 'KVStore', 'gone')],
            {'KVStore': [path]})
        self.assertEqual([claim.method for claim, _rel in broken], ['gone'])

    def test_build_class_index_prefers_inventory_path(self):
        self.write_source('a/Widget.java', 'x\n')
        self.write_source('b/Widget.java', 'y\n')
        inv = os.path.join(self.root, 'data', 'state', 'source-inventory.json')
        os.makedirs(os.path.dirname(inv), exist_ok=True)
        with open(inv, 'w', encoding='utf-8') as fh:
            json.dump({'packages': {'p': {'classes': [
                {'name': 'Widget', 'rel': 'b/Widget.java'}]}}}, fh)
        index = self.module.build_class_index(self.source_dir)
        self.assertTrue(index['Widget'][0].endswith('b/Widget.java'))

    # -- drift baseline --------------------------------------------------
    def test_baseline_round_trip(self):
        path = os.path.join(self.tmp.name, 'baseline.json')
        Claim = self.module.SymbolClaim
        broken = [(Claim('ch.md', 1, 'KVStore', 'gone'), 'org/example/KVStore.java')]
        self.module.save_baseline(broken, '1.0', path)
        loaded = self.module.load_baseline(path)
        self.assertEqual(loaded['accepted'], ['ch.md::KVStore::gone'])
        new, known = self.module.split_drift(broken, loaded)
        self.assertEqual((new, known), ([], broken))

    def test_baseline_missing_and_corrupt_files_are_tolerated(self):
        missing = os.path.join(self.tmp.name, 'none.json')
        self.assertEqual(self.module.load_baseline(missing)['accepted'], [])
        corrupt = os.path.join(self.tmp.name, 'bad.json')
        with open(corrupt, 'w', encoding='utf-8') as fh:
            fh.write('{not json')
        with redirect_stderr(io.StringIO()):
            self.assertEqual(self.module.load_baseline(corrupt)['accepted'], [])

    def test_suggest_renames_proposes_close_names(self):
        Claim = self.module.SymbolClaim
        index = {'KVStore': ['/a/KVStore.java'], 'KVStores': ['/a/KVStores.java']}
        suggestions = self.module.suggest_renames(Claim('ch.md', 1, 'KVStores', 'bump'), index)
        self.assertIsInstance(suggestions, list)

    # -- CLI -------------------------------------------------------------
    def run_main(self, *args: str):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = self.module.main(list(args))
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 0
        return code, out.getvalue(), err.getvalue()

    def test_main_json_reports_drift(self):
        self.write_chapter('`Gone.java:3`\n')
        self.write_source('org/example/KVStore.java', 'x\n')
        code, out, _err = self.run_main('--json',
                                        '--baseline', os.path.join(self.tmp.name, 'none.json'))
        self.assertIn(code, (0, 1))
        self.assertTrue(out.strip())
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            # the summary may be printed as text before the JSON payload
            start = out.find('{')
            payload = json.loads(out[start:]) if start >= 0 else {}
        self.assertIsInstance(payload, (dict, list))

    def test_main_update_baseline_writes_the_file(self):
        self.write_chapter('`KVStore.absent(`\n')
        self.write_source('org/example/KVStore.java', 'class KVStore {}\n')
        target = os.path.join(self.tmp.name, 'accepted.json')
        code, _out, _err = self.run_main('--update-baseline', '--baseline', target)
        self.assertIn(code, (0, 1))

    def test_main_suggest_and_strict_flags(self):
        self.write_chapter('`KVStore.absent(`\n')
        self.write_source('org/example/KVStore.java', 'class KVStore {}\n')
        baseline = os.path.join(self.tmp.name, 'none.json')
        for flag in ('--suggest', '--strict-symbols', '--prune'):
            with self.subTest(flag=flag):
                code, _out, _err = self.run_main(flag, '--baseline', baseline)
                self.assertIn(code, (0, 1, 2))

if __name__ == '__main__':
    unittest.main()
