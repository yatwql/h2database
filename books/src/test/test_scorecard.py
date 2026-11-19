#!/usr/bin/env python3
"""Tests for the release scorecard dimensions (subprocess-free)."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:infra', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

class ScorecardDimensionsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.card = _fixture.load_module(self.root, 'scorecard')

    # -- 功能 ------------------------------------------------------------
    def test_feature_score_counts_present_channels(self):
        score, notes = self.card.feature_score()
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertEqual(score, 100, notes)

    def test_feature_score_reports_missing_channels(self):
        with mock.patch.object(self.card.os.path, 'isfile', return_value=False), \
                mock.patch.object(self.card.glob, 'glob', return_value=[]):
            score, notes = self.card.feature_score()
        self.assertEqual(score, 0)
        self.assertTrue(any('missing' in note for note in notes))

    # -- 稳定 ------------------------------------------------------------
    def test_stability_score_with_a_green_suite(self):
        with mock.patch.object(self.card, '_run', return_value=(0, 'Ran 250 tests in 9s')):
            self.assertEqual(self.card.stability_score(), (100, []))

    def test_stability_score_flags_a_failing_or_small_suite(self):
        with mock.patch.object(self.card, '_run', return_value=(1, 'Ran 5 tests')):
            score, notes = self.card.stability_score()
        self.assertEqual(score, 40)
        self.assertIn('test suite failing', notes)
        self.assertTrue(any('only 5 tests' in note for note in notes))

    def test_stability_score_without_a_test_count(self):
        with mock.patch.object(self.card, '_run', return_value=(0, 'no output')):
            score, notes = self.card.stability_score()
        self.assertEqual(score, 70)
        self.assertTrue(notes)

    # -- 交互 ------------------------------------------------------------
    def test_interaction_score_with_every_manual_present(self):
        with mock.patch.object(self.card.os.path, 'isfile', return_value=True), \
                mock.patch.object(self.card._fsutil, 'read_text',
                                  return_value=' '.join(self.card.DIMENSIONS and [
                                      'how-to-new-book.md', 'how-to-config.md',
                                      'how-to-use-cli.md', 'how-to-use-tui.md',
                                      'how-to-use-web.md', 'faq.md'])):
            score, notes = self.card.interaction_score()
        self.assertEqual((score, notes), (100, []))

    def test_interaction_score_reports_missing_docs(self):
        with mock.patch.object(self.card.os.path, 'isfile', return_value=False), \
                mock.patch.object(self.card._fsutil, 'read_text', return_value=''):
            score, notes = self.card.interaction_score()
        self.assertEqual(score, 0)
        self.assertIn('manual pages missing', notes)
        self.assertIn('README does not link every manual', notes)

    # -- 代码 ------------------------------------------------------------
    def test_code_score_is_full_when_lint_and_gates_pass(self):
        with mock.patch.object(self.card, '_run', return_value=(0, '')):
            self.assertEqual(self.card.code_score(), (100, []))

    def test_code_score_reports_lint_and_gate_failures(self):
        with mock.patch.object(self.card, '_run', return_value=(1, 'boom')):
            score, notes = self.card.code_score()
        self.assertEqual(score, 20)
        self.assertIn('ruff findings', notes)
        self.assertIn('architecture/contract gates failing', notes)

    # -- 文档 ------------------------------------------------------------
    def test_json_metric_reads_a_numeric_field(self):
        with mock.patch.object(self.card, '_run',
                               return_value=(0, json.dumps({'composite': 91.5}))):
            self.assertEqual(self.card._json_metric('prose_quality.py', 'composite'), 91.5)

    def test_json_metric_tolerates_bad_payloads(self):
        for payload in ('not json', json.dumps({'composite': 'high'})):
            with self.subTest(payload=payload), \
                    mock.patch.object(self.card, '_run', return_value=(0, payload)):
                self.assertEqual(self.card._json_metric('prose_quality.py', 'composite'), 0.0)

    def test_json_metric_without_the_script(self):
        with mock.patch.object(self.card.os.path, 'isfile', return_value=False):
            self.assertEqual(self.card._json_metric('missing.py', 'x'), 0.0)

    def test_prose_score_uses_the_composite(self):
        with mock.patch.object(self.card, '_run',
                               return_value=(0, json.dumps({'composite': 88}))):
            self.assertEqual(self.card.prose_score(), (88, []))
        with mock.patch.object(self.card, '_run',
                               return_value=(0, json.dumps({'composite': 61}))):
            score, notes = self.card.prose_score()
        self.assertEqual(score, 61)
        self.assertTrue(notes)

    def test_prose_score_without_a_report(self):
        with mock.patch.object(self.card, '_run', return_value=(0, 'oops')):
            self.assertEqual(self.card.prose_score(), (0, ['prose report unavailable']))

    def test_content_score_penalises_problems(self):
        payload = {'problems': ['a', 'b', 'c', 'd']}
        with mock.patch.object(self.card, '_run', return_value=(0, json.dumps(payload))):
            score, notes = self.card.content_score()
        self.assertEqual(score, 52)
        self.assertEqual(len(notes), 3)

    def test_content_score_without_a_report(self):
        with mock.patch.object(self.card, '_run', return_value=(1, 'oops')):
            self.assertEqual(self.card.content_score(), (20, ['book quality gate failing']))

    # -- CLI -------------------------------------------------------------
    def test_main_json_lists_every_dimension(self):
        buffer = io.StringIO()
        with mock.patch.object(self.card, '_run', return_value=(0, 'Ran 250 tests')), \
                mock.patch.object(self.card._fsutil, 'read_text', return_value=''), \
                redirect_stdout(buffer):
            code = self.card.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(len(payload['dimensions']), len(self.card.DIMENSIONS))
        self.assertIn('total', payload)

    def test_main_prints_a_human_scorecard(self):
        buffer = io.StringIO()
        with mock.patch.object(self.card, '_run', return_value=(0, 'Ran 250 tests')), \
                mock.patch.object(self.card._fsutil, 'read_text', return_value=''), \
                redirect_stdout(buffer):
            self.card.main([])
        self.assertIn('发布质量评分', buffer.getvalue())

if __name__ == '__main__':
    unittest.main()
