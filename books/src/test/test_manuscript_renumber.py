#!/usr/bin/env python3
"""Chapter renumbering: the mapping and the reference rewrite it drives."""
from __future__ import annotations

import importlib
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:manuscript', 'tier:fast')

_fixture.ensure_tools_path()


class RewriteTest(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module('renumber')

    def test_a_reference_follows_the_mapping(self):
        text = '详见第9章《查询优化器》与第12章的内容。'
        self.assertEqual(self.mod.rewrite_refs(text, {9: 7, 12: 9}),
                         '详见第7章《查询优化器》与第9章的内容。')

    def test_a_chapter_outside_the_mapping_is_left_alone(self):
        text = '详见第3章《存储引擎》。'
        self.assertEqual(self.mod.rewrite_refs(text, {9: 7}), text)

    def test_an_empty_mapping_changes_nothing(self):
        text = '详见第9章《查询优化器》。'
        self.assertEqual(self.mod.rewrite_refs(text, {}), text)

    def test_a_malformed_capture_does_not_raise(self):
        self.assertEqual(self.mod._as_int('x'), 0)


class MappingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = _fixture.build_book(self.tmp)
        self.mod = _fixture.load_module(self.root, 'renumber')
        self.config = _fixture.load_module(self.root, '_config')

    def declare(self, table: str) -> None:
        """Add edition tables; a top-level key goes before the first table header."""
        path = os.path.join(self.root, 'data', 'book', 'book.toml')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        head, _, body = table.partition('[editions]')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(head.strip() + '\n' + text + '\n[editions]' + body)

    def declare_edition(self, numbering: str) -> None:
        """Declare an edition whose numbering differs from the book's."""
        path = os.path.join(self.root, 'data', 'book', 'book.toml')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('default_edition = "abridged"\n' + text + '''
[editions]
main = "主版本"

[editions.abridged]
display = "删节版"

[editions.abridged.chapters]
files = ["cover.md", "ch1-test.md", "ch2-test.md"]
[editions.abridged.chapters.numbering]
"ch1-test.md" = [1]
"ch2-test.md" = [3]
''')

    def chapter(self, name: str, text: str) -> str:
        # an edition reads its own manuscript subdirectory
        path = os.path.join(self.root, 'data', 'manuscript', 'abridged', name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    def test_apply_writes_the_mapping_and_rewrites_references(self):
        self.declare_edition('')
        chapter = self.chapter('ch2-test.md', '# 第2章 核心模块\n\n详见第2章《核心模块》。\n')
        cfg = self.config.Config(self.root, 'abridged')
        with self.mod._config.use(cfg):
            report = self.mod.apply()
            self.assertEqual(report['mapping'], {2: 3})
            self.assertEqual(report['files'], 1)
            self.assertTrue(os.path.isfile(self.mod.mapping_path()))
            with open(self.mod.mapping_path(), encoding='utf-8') as fh:
                self.assertEqual(json.load(fh), {'2': 3})
            with open(chapter, encoding='utf-8') as fh:
                self.assertIn('详见第3章', fh.read())

    def test_a_dry_run_reports_without_touching_files(self):
        self.declare_edition('')
        chapter = self.chapter('ch2-test.md', '# 第2章 核心模块\n\n详见第2章《核心模块》。\n')
        cfg = self.config.Config(self.root, 'abridged')
        with self.mod._config.use(cfg):
            report = self.mod.apply(dry_run=True)
            self.assertTrue(report['dry_run'])
            self.assertFalse(os.path.isfile(self.mod.mapping_path()))
            with open(chapter, encoding='utf-8') as fh:
                self.assertIn('详见第2章', fh.read())

    def test_main_requires_an_action(self):
        with self.assertRaises(SystemExit):
            self.mod.main([])

    def test_main_writes_only_the_mapping(self):
        self.declare_edition('')
        cfg = self.config.Config(self.root, 'abridged')
        with self.mod._config.use(cfg):
            self.assertEqual(self.mod.main(['--write']), 0)
            self.assertTrue(os.path.isfile(self.mod.mapping_path()))

    def test_main_can_apply_and_report_json(self):
        self.declare_edition('')
        cfg = self.config.Config(self.root, 'abridged')
        with self.mod._config.use(cfg), mock.patch('sys.stdout'):
            self.assertEqual(self.mod.main(['--apply', '--json']), 0)


    def test_without_an_edition_there_is_nothing_to_renumber(self):
        with self.assertRaises(SystemExit):
            self.mod.apply()

    def test_a_dropped_chapter_shifts_the_numbers_after_it(self):
        base = {'ch1-test.md': [1], 'ch2-test.md': [2]}
        target = {'ch1-test.md': [1]}
        self.assertEqual(self.mod.mapping_of(base, target), {})

    def test_a_non_numeric_numbering_value_is_ignored(self):
        base = {'ch1-test.md': [1], 'ch2-test.md': [2]}
        target = {'ch1-test.md': ['I'], 'ch2-test.md': [3]}
        self.assertEqual(self.mod.mapping_of(base, target), {2: 3})

    def test_main_reports_a_book_without_editions(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(['--write'])
        self.assertEqual(code, 2)
        self.assertIn('edition', buffer.getvalue())

    def test_a_kept_chapter_that_moves_is_recorded(self):
        base = {'ch1-test.md': [1], 'ch2-test.md': [2], 'ch3-test.md': [3]}
        target = {'ch1-test.md': [1], 'ch3-test.md': [2]}
        self.assertEqual(self.mod.mapping_of(base, target), {3: 2})

    def test_the_mapping_is_written_under_the_edition_state(self):
        self.declare('''
[editions]
main = "主版本"
''')
        cfg = self.config.Config(self.root, 'main')
        with self.mod._config.use(cfg):
            self.assertTrue(self.mod.mapping_path().endswith(
                os.path.join('state', 'main', 'renumber.json')))


if __name__ == '__main__':
    unittest.main()
