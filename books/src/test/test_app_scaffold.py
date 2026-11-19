#!/usr/bin/env python3
"""The scaffold generator: the files it writes and its CLI output."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

TAGS = ('layer:app', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

class ScaffoldGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        # scaffold copies these two documents into the new book
        tmpl = os.path.join(self.root, 'data', 'tmpl', 'templates.toml')
        os.makedirs(os.path.dirname(tmpl), exist_ok=True)
        if not os.path.exists(tmpl):
            with open(tmpl, 'w', encoding='utf-8') as fh:
                fh.write('[narrative]\ntemplate = "{placeholder}"\n')
        self.module = _fixture.load_module(self.root, 'scaffold')

    def test_scaffold_creates_document_side_files(self):
        target = os.path.join(self.tmp.name, 'newbook')
        created = self.module.scaffold(target, '新书', 'zh', False)
        self.assertTrue(created)
        book_toml = os.path.join(target, 'data', 'tmpl', 'book.toml')
        self.assertTrue(os.path.exists(book_toml))
        with open(book_toml, encoding='utf-8') as fh:
            self.assertIn('新书', fh.read())
        self.assertTrue(os.path.exists(os.path.join(target, 'data', 'language', 'zh.json')))
        self.assertTrue(os.path.exists(os.path.join(target, 'data', 'config', 'base.json')))

    def test_style_is_derived_per_language(self):
        cjk = self.module.style_for('zh')
        latin = self.module.style_for('en')
        self.assertEqual(cjk['prose']['avg_sentence_good'], 28)
        self.assertEqual(latin['prose']['avg_sentence_good'], 18)
        self.assertEqual(cjk['style_rules']['terminology'], [])
        self.assertEqual(latin['captions']['leading_verbs'], [])
        self.assertTrue(cjk['prose']['avg_sentence_good'] > latin['prose']['avg_sentence_good'])

    def test_scaffold_writes_the_derived_style(self):
        target = os.path.join(self.tmp.name, 'translated')
        self.module.scaffold(target, 'Translated', 'en', False)
        style_path = os.path.join(target, 'data', 'config', 'style.json')
        with open(style_path, encoding='utf-8') as fh:
            written = json.load(fh)
        self.assertEqual(written['prose']['avg_sentence_bad'], 30)
        self.assertEqual(written['style_rules']['terminology'], [])
        self.assertIn('en', written['_note'])

    def test_scaffold_is_idempotent(self):
        target = os.path.join(self.tmp.name, 'again')
        self.module.scaffold(target, '书', 'zh', False)
        self.assertEqual(self.module.scaffold(target, '书', 'zh', False), [])

    def test_scaffold_can_copy_manuscript(self):
        target = os.path.join(self.tmp.name, 'copy')
        created = self.module.scaffold(target, '书', 'zh', True)
        self.assertTrue(any(name.endswith('ch1-test.md') for name in created))

    def test_main_reports_nothing_created(self):
        target = os.path.join(self.tmp.name, 'twice')
        self.module.scaffold(target, '书', 'zh', False)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.module.main([target])
        self.assertEqual(code, 0)
        self.assertIn('nothing created', buffer.getvalue())

    def test_main_prints_next_step(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.module.main([os.path.join(self.tmp.name, 'fresh'),
                                     '--title', '新标题'])
        self.assertEqual(code, 0)
        self.assertIn('bookctl analyze', buffer.getvalue())

if __name__ == '__main__':
    unittest.main()
