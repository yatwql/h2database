#!/usr/bin/env python3
"""content_volume: what it reads, what it refuses, and how it reports.

The gate compares a manuscript against a reviewed floor. The interesting paths
are the refusals — a baseline from another source, a thinner delivered PDF, an
EPUB that shrank — because those are what the floor exists for.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


def manuscript(total_bytes: int = 1000, lines: int = 100, name: str = 'ch1-test.md') -> dict:
    return {'files': {name: {'bytes': total_bytes, 'lines': lines}},
            'total': {'bytes': total_bytes, 'lines': lines}}


class ContentVolumeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'content_volume')

    def run_main(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = self.mod.main(list(args))
        return code, out.getvalue(), err.getvalue()

    # -- artifacts -------------------------------------------------------
    def test_artifacts_reads_the_pdf_page_count_and_the_epub_size(self):
        import importlib.util
        if importlib.util.find_spec('pypdf') is None:
            self.skipTest('pypdf not installed')
        from pypdf import PdfWriter

        pdf = os.path.join(self.root, 'dist', 'test-book.pdf')
        epub = os.path.join(self.root, 'dist', 'test-book.epub')
        os.makedirs(os.path.dirname(pdf), exist_ok=True)
        writer = PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=595, height=842)
        with open(pdf, 'wb') as fh:
            writer.write(fh)
        with open(epub, 'wb') as fh:
            fh.write(b'x' * 128)
        artifacts = self.mod.delivered_snapshot()
        self.assertEqual(artifacts['pdf_pages'], 3)
        self.assertEqual(artifacts['pdf_bytes'], os.path.getsize(pdf))
        self.assertEqual(artifacts['epub_bytes'], 128)

    def test_an_unreadable_pdf_is_not_this_gate_s_finding(self):
        pdf = os.path.join(self.root, 'dist', 'test-book.pdf')
        os.makedirs(os.path.dirname(pdf), exist_ok=True)
        with open(pdf, 'wb') as fh:
            fh.write(b'not a pdf')
        self.assertNotIn('pdf_pages', self.mod.delivered_snapshot())

    # -- baseline --------------------------------------------------------
    def test_an_absent_baseline_reads_as_empty(self):
        self.assertEqual(self.mod.load_baseline(os.path.join(self.tmp.name, 'nope.json')), {})

    def test_an_unparsable_baseline_says_so_and_reads_as_empty(self):
        path = os.path.join(self.tmp.name, 'broken.json')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('{broken')
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(self.mod.load_baseline(path), {})
        self.assertIn('无法解析', err.getvalue())

    # -- compare ---------------------------------------------------------
    def test_a_baseline_from_another_source_is_refused(self):
        baseline = {'reviewed': {'source': {'inventory_sha256': 'aaa'}},
                    'manuscript': manuscript()}
        with mock.patch.object(self.mod, 'source_fingerprint',
                               return_value={'inventory_sha256': 'bbb'}):
            problems = self.mod.compare(baseline, {'manuscript': manuscript(),
                                                   'delivered': {}})
        self.assertTrue(any('另一个源' in problem for problem in problems), problems)

    def test_a_file_that_left_the_manuscript_is_reported(self):
        baseline = {'manuscript': manuscript()}
        current = {'manuscript': manuscript(name='ch2-test.md'), 'delivered': {}}
        problems = self.mod.compare(baseline, current)
        self.assertTrue(any('gone from the manuscript' in problem for problem in problems))

    def test_a_thinner_total_is_reported_against_the_floor(self):
        baseline = {'manuscript': manuscript(1000)}
        current = {'manuscript': manuscript(500), 'delivered': {}}
        problems = self.mod.compare(baseline, current)
        self.assertTrue(any('manuscript total' in problem for problem in problems), problems)

    def test_a_shrunken_delivered_pdf_and_epub_are_reported(self):
        baseline = {'manuscript': manuscript(),
                    'delivered': {'pdf_pages': 100, 'epub_bytes': 10000}}
        current = {'manuscript': manuscript(),
                   'delivered': {'pdf_pages': 50, 'epub_bytes': 100}}
        problems = self.mod.compare(baseline, current)
        self.assertTrue(any('delivered PDF' in problem for problem in problems), problems)
        self.assertTrue(any('delivered EPUB' in problem for problem in problems), problems)

    def test_a_healthier_manuscript_has_no_problems(self):
        baseline = {'manuscript': manuscript(1000),
                    'delivered': {'pdf_pages': 10, 'epub_bytes': 1000}}
        current = {'manuscript': manuscript(1200),
                   'delivered': {'pdf_pages': 12, 'epub_bytes': 1200}}
        self.assertEqual(self.mod.compare(baseline, current), [])

    # -- helpers the mutations exposed ------------------------------------
    def test_a_failing_git_command_yields_no_text(self):
        done = mock.Mock(returncode=1, stdout=' M dirty\n', stderr='')
        with mock.patch.object(self.mod.subprocess, 'run', return_value=done):
            self.assertEqual(self.mod._git('status', '--porcelain'), '')

    def test_a_snapshot_label_must_match_exactly_one_ledger(self):
        folder = os.path.join(self.root, 'data', 'baselines')
        os.makedirs(folder, exist_ok=True)
        for name in ('snapshot-2026-01-01-a.json', 'snapshot-2026-02-02-a.json'):
            with open(os.path.join(folder, name), 'w', encoding='utf-8') as fh:
                fh.write('{"files": {}}')
        # no exact snapshot-a.json, and the dated ledgers tie: refuse to guess
        self.assertIsNone(self.mod.from_snapshot('a'))

    def test_a_dated_ledger_resolves_by_its_bare_label(self):
        folder = os.path.join(self.root, 'data', 'baselines')
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, 'snapshot-2026-01-01-a.json'), 'w',
                  encoding='utf-8') as fh:
            json.dump({'files': {'ch1-test.md': {'bytes': 10, 'lines': 1}}}, fh)
        payload = self.mod.from_snapshot('a')
        self.assertEqual(payload['source']['snapshot'], 'a')
        self.assertEqual(payload['manuscript']['total']['bytes'], 10)

    def test_a_baseline_is_ignored_when_the_profile_is_not_cold_start(self):
        baseline_path = os.path.join(self.tmp.name, 'baseline.json')
        with open(baseline_path, 'w', encoding='utf-8') as fh:
            json.dump({'manuscript': manuscript(100000)}, fh)
        with mock.patch.object(self.mod, 'PROFILE', 'baseline'):
            code, out, _err = self.run_main('--baseline', baseline_path)
        self.assertEqual(code, 1, out[-300:])
        self.assertNotIn('cold-start', out)

    # -- asymmetric inputs the mutations exposed --------------------------
    def test_a_baseline_with_pdf_pages_but_no_current_pdf_is_fine(self):
        baseline = {'manuscript': manuscript(),
                    'delivered': {'pdf_pages': 100, 'epub_bytes': 1000}}
        current = {'manuscript': manuscript(), 'delivered': {'epub_bytes': 1000}}
        problems = self.mod.compare(baseline, current)
        self.assertFalse(any('delivered PDF' in problem for problem in problems), problems)

    def test_the_manuscript_file_list_drops_missing_entries(self):
        missing = os.path.join(self.root, 'data', 'manuscript', 'gone.md')
        with mock.patch.object(self.mod._config, 'chapter_files', return_value=['gone.md']), \
                mock.patch.object(self.mod._config, 'front_matter', return_value=[]), \
                mock.patch.object(self.mod._config, 'back_matter', return_value=[]):
            files = self.mod.manuscript_files()
        self.assertEqual(files, [])
        self.assertNotIn(missing, files)

    def test_a_baseline_with_a_delivered_size_but_no_current_one_is_fine(self):
        baseline = {'manuscript': manuscript(),
                    'delivered': {'pdf_pages': 10, 'epub_bytes': 1000}}
        current = {'manuscript': manuscript(), 'delivered': {'pdf_pages': 10}}
        problems = self.mod.compare(baseline, current)
        self.assertFalse(any('EPUB' in problem for problem in problems), problems)

    def test_an_accepted_shrink_is_recorded_instead_of_refused(self):
        thin = {'manuscript': manuscript(500), 'delivered': {}}
        thick = {'manuscript': manuscript(5000), 'delivered': {}}
        target = os.path.join(self.tmp.name, 'reviewed.json')
        clean = {'dirty': '', 'commit': 'abc1234', 'committed_at': '2026-01-01T00:00:00+08:00',
                 'author': 'reviewer'}
        with mock.patch.object(self.mod, 'provenance', return_value=clean), \
                mock.patch.object(self.mod, 'load_baseline', return_value=thick), \
                mock.patch.object(self.mod, 'baseline_path', return_value=target):
            refused = self.mod.update_baseline(thin)
            accepted = self.mod.update_baseline(thin, True, '删节版', '阿龙')
        self.assertEqual((refused, accepted), (1, 0))
        with open(target, encoding='utf-8') as fh:
            payload = json.load(fh)
        self.assertTrue(payload['accepted_shrinks'])
        self.assertEqual(payload['reviewed']['by'], '阿龙')

    # -- main ------------------------------------------------------------
    def test_without_a_baseline_the_gate_says_how_to_establish_one(self):
        code, out, _err = self.run_main()
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('--update-baseline', out)

    def test_json_mode_reports_the_problems_and_fails(self):
        baseline_path = os.path.join(self.tmp.name, 'baseline.json')
        with open(baseline_path, 'w', encoding='utf-8') as fh:
            json.dump({'manuscript': manuscript(100000)}, fh)
        code, out, _err = self.run_main('--baseline', baseline_path, '--json')
        payload = json.loads(out[out.index('{'):])
        self.assertEqual(code, 1, out[-300:])
        self.assertGreaterEqual(payload['count'], 1)

    def test_a_cold_start_book_ignores_its_baseline(self):
        baseline_path = os.path.join(self.tmp.name, 'baseline.json')
        with open(baseline_path, 'w', encoding='utf-8') as fh:
            json.dump({'manuscript': manuscript(100000)}, fh)
        with mock.patch.object(self.mod, 'PROFILE', 'cold-start'):
            code, out, _err = self.run_main('--baseline', baseline_path)
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('cold-start', out)


if __name__ == '__main__':
    unittest.main()
