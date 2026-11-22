#!/usr/bin/env python3
"""The configuration is one object per book, not one process-wide singleton.

These cases are the contract the multi-book layout relies on: two books in the
same process never see each other's paths, and the module-level helpers follow
whichever book is active for the duration of a ``with use(...)`` block.
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import tempfile
import unittest

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()
_config = importlib.import_module('lib._config')


def make_book(root: str, title: str, merged: str, state: str) -> None:
    """Write the smallest book that Config can load."""
    book_dir = os.path.join(root, 'data', 'config', 'book')
    os.makedirs(book_dir, exist_ok=True)
    os.makedirs(os.path.join(root, 'data', 'config'), exist_ok=True)
    with open(os.path.join(book_dir, 'book.toml'), 'w', encoding='utf-8') as fh:
        fh.write(f'''[book]
title = "{title}"
version = "1.0"
merged_name = "{merged}"

[paths]
manuscript = "data/manuscript"
dist = "dist"
docs = "docs"
tmp = "data/tmp"
state = "{state}"

[chapters]
files = ["ch1.md"]

[chapters.packages]
"ch1.md" = ["org.example"]
''')
    with open(os.path.join(root, 'data', 'config', 'base.json'), 'w', encoding='utf-8') as fh:
        json.dump({'paths': {}, 'sources': {'languages': ['java'],
                                            'suffixes': {'java': '.java'}}}, fh)
    with open(os.path.join(root, 'data', 'config', 'style.json'), 'w', encoding='utf-8') as fh:
        json.dump({'thresholds': {}}, fh)


class TwoBooksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.one = os.path.join(self.tmp, 'one')
        self.two = os.path.join(self.tmp, 'two')
        for root, title, merged, state in ((self.one, '第一本', 'alpha', 'data/state'),
                                           (self.two, '第二本', 'beta', 'data/state-b')):
            make_book(root, title, merged, state)

    def test_two_books_keep_their_own_values(self):
        first, second = _config.Config(self.one), _config.Config(self.two)
        self.assertEqual(first.title, '第一本')
        self.assertEqual(second.title, '第二本')
        self.assertEqual(first.state_dir(), os.path.join(self.one, 'data', 'state'))
        self.assertEqual(second.state_dir(), os.path.join(self.two, 'data/state-b'))
        self.assertTrue(first.merged_md().endswith('alpha.md'))
        self.assertTrue(second.merged_md().endswith('beta.md'))

    def test_a_book_reads_only_its_own_files(self):
        first = _config.Config(self.one)
        self.assertEqual(first.chapter_names(), ['ch1.md'])
        self.assertEqual(first.manuscript('ch1.md'),
                         os.path.join(self.one, 'data', 'manuscript', 'ch1.md'))
        self.assertEqual(first.chapter_packages(), {'ch1.md': ['org.example']})

    def test_module_helpers_follow_the_active_book(self):
        second = _config.Config(self.two)
        with _config.use(second) as active:
            self.assertIs(active, second)
            self.assertEqual(_config.BOOK_ROOT, self.two)
            self.assertEqual(_config.TITLE, '第二本')
            self.assertEqual(_config.state_path('outline.json'),
                             os.path.join(self.two, 'data/state-b', 'outline.json'))
            self.assertEqual(_config.chapter_names(), ['ch1.md'])
        self.assertEqual(_config.BOOK_ROOT, _config.current().root)
        self.assertNotEqual(_config.BOOK_ROOT, self.two)

    def test_the_previous_book_returns_even_when_the_block_raises(self):
        before = _config.current()
        with self.assertRaises(RuntimeError), _config.use(_config.Config(self.two)):
            raise RuntimeError('boom')
        self.assertIs(_config.current(), before)

    def test_nested_blocks_restore_in_order(self):
        one, two = _config.Config(self.one), _config.Config(self.two)
        with _config.use(one):
            with _config.use(two):
                self.assertEqual(_config.TITLE, '第二本')
            self.assertEqual(_config.TITLE, '第一本')

    def test_an_unknown_module_attribute_still_fails(self):
        name = 'NO_SUCH_SETTING'
        self.assertNotIn(name, dir(_config))
        with self.assertRaises(AttributeError):
            getattr(_config, name)

    def test_a_missing_book_file_is_a_config_error(self):
        with self.assertRaises(_config.ConfigError):
            _config.Config(os.path.join(self.tmp, 'nowhere'))

    def test_the_default_book_matches_its_module_attributes(self):
        active = _config.current()
        self.assertEqual(_config.BOOK_ROOT, active.root)
        self.assertEqual(_config.MANUSCRIPT_DIR, active.manuscript_dir)
        self.assertEqual(_config.THRESHOLDS, active.thresholds)
        self.assertEqual(_config.chapter_names(), active.chapter_names())


if __name__ == '__main__':
    unittest.main()
