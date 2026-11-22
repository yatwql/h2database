#!/usr/bin/env python3
"""Chapter renumbering: the mapping and the reference rewrite it drives."""
from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest

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

    def test_without_an_edition_there_is_nothing_to_renumber(self):
        with self.assertRaises(SystemExit):
            self.mod.apply()

    def test_a_dropped_chapter_shifts_the_numbers_after_it(self):
        base = {'ch1-test.md': [1], 'ch2-test.md': [2]}
        target = {'ch1-test.md': [1]}
        self.assertEqual(self.mod.mapping_of(base, target), {})

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
