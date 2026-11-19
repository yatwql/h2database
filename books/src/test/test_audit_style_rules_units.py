#!/usr/bin/env python3
"""Style rules gate: terminology, spacing, headings, list punctuation."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))


class StyleRulesUnitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, 'style_rules')

    def doc(self, text: str) -> str:
        path = os.path.join(self.tmp.name, 'doc.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    def findings(self, text: str, rules: dict | None = None) -> list[dict]:
        settings = rules if rules is not None else {}
        with mock.patch.object(self.mod, 'RULES', settings):
            return self.mod.check_file(self.doc(text))

    def test_clean_document_has_no_findings(self):
        rules = {'terminology': [], 'banned_link_text': [], 'heading': {},
                 'cjk_latin_spacing': True}
        self.assertEqual(self.findings('# 标题\n\n正文一段，中文与 English 之间留空格。\n',
                                       rules), [])

    def test_cjk_latin_spacing_is_reported(self):
        findings = self.findings('# 标题\n\n使用 KVStore存储 的实现。\n',
                                 {'cjk_latin_spacing': True})
        self.assertEqual(findings[0]['kind'], 'CJK_SPACE')

    def test_terminology_synonyms_are_reported(self):
        rules = {'terminology': [['缓冲池', '缓冲区域']]}
        findings = self.findings('# 标题\n\n缓冲池与缓冲区域并存。\n', rules)
        self.assertEqual(findings[0]['kind'], 'TERM')

    def test_banned_link_text_is_reported(self):
        rules = {'banned_link_text': ['点这里']}
        findings = self.findings('# 标题\n\n见[点这里](../x.md)。\n', rules)
        self.assertEqual(findings[0]['kind'], 'LINK')

    def test_heading_rule_checks_trailing_punctuation(self):
        rules = {'heading': {'no_trailing_punctuation': True}}
        findings = self.findings('## 小节标题。\n', rules)
        self.assertEqual(findings[0]['kind'], 'HEADING')

    def test_findings_have_a_stable_key(self):
        rules = {'terminology': [['缓冲池', '缓冲区域']]}
        findings = self.findings('# 标题\n\n缓冲池与缓冲区域并存。\n', rules)
        key = self.mod._key(findings[0])
        self.assertIn('TERM', key)

    def test_baseline_round_trip(self):
        path = os.path.join(self.tmp.name, 'baseline.json')
        with mock.patch.object(self.mod, 'BASELINE_PATH', path):
            self.assertEqual(self.mod.load_baseline(), set())
            self.mod.save_baseline([{'file': 'a.md', 'line': 1, 'kind': 'TERM',
                                     'detail': 'mixed spellings'}])
            self.assertTrue(self.mod.load_baseline())

    def test_main_passes_on_the_real_tree(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main([])
        self.assertIn(code, (0, 1))
        self.assertTrue(buffer.getvalue())

    def test_json_output_reports_findings(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(['--json'])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertIn('findings', payload)


if __name__ == '__main__':
    unittest.main()
