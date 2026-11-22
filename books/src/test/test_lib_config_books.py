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
import pathlib
import shutil
import tempfile
import unittest

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()
_config = importlib.import_module('lib._config')


def make_book(root: str, title: str, merged: str, state: str) -> None:
    """Write the smallest book that Config can load."""
    book_dir = os.path.join(root, 'data', 'book')
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

    def test_an_explicit_book_beats_the_environment(self):
        with _config.use(_config.Config(self.one)):
            os.environ['BOOK_ROOT'] = self.two
            try:
                self.assertEqual(_config.resolve_book_root(self.one), self.one)
                self.assertEqual(_config.resolve_book_root(None), os.path.abspath(self.two))
            finally:
                os.environ.pop('BOOK_ROOT', None)

    def test_looking_up_finds_the_nearest_book(self):
        nested = os.path.join(self.one, 'data', 'manuscript', 'ch1')
        os.makedirs(nested, exist_ok=True)
        self.assertEqual(_config.find_book_root(nested), self.one)

    def test_where_there_is_no_book_the_lookup_returns_nothing(self):
        self.assertEqual(_config.find_book_root(self.tmp), '')

    def test_candidates_include_the_active_book_and_its_siblings(self):
        roots = _config.candidate_books(self.one, start=self.tmp)
        self.assertEqual(roots[0], self.one)
        self.assertIn(os.path.abspath(self.two), roots)

    def test_a_path_that_escapes_the_book_root_is_refused(self):
        book = os.path.join(self.one, 'data', 'book', 'book.toml')
        text = pathlib.Path(book).read_text(encoding='utf-8')
        pathlib.Path(book).write_text(
            text.replace('manuscript = "data/manuscript"', 'manuscript = "../outside"'),
            encoding='utf-8')
        with self.assertRaises(_config.ConfigError):
            _config.Config(self.one)

    def declare_editions(self, root: str, editions: str, default: str = '') -> None:
        """Add an [editions] table to a fixture book."""
        path = os.path.join(root, 'data', 'book', 'book.toml')
        text = pathlib.Path(path).read_text(encoding='utf-8')
        block = editions if not default else f'default_edition = "{default}"\n{editions}'
        pathlib.Path(path).write_text(text + '\n' + block, encoding='utf-8')

    def test_a_book_without_editions_keeps_todays_layout(self):
        cfg = _config.Config(self.one)
        self.assertEqual(cfg.edition, '')
        self.assertTrue(cfg.manuscript_dir.endswith(os.path.join('data', 'manuscript')))
        self.assertTrue(cfg.state_dir().endswith(os.path.join('data', 'state')))
        self.assertTrue(cfg.merged_md().endswith('alpha.md'))

    def test_a_single_edition_is_selected_implicitly(self):
        self.declare_editions(self.one, '[editions]\nmain = "主版本"\n')
        cfg = _config.Config(self.one)
        self.assertEqual(cfg.edition, 'main')
        self.assertTrue(cfg.manuscript_dir.endswith(os.path.join('manuscript', 'main')))
        self.assertTrue(cfg.state_dir().endswith(os.path.join('state', 'main')))
        self.assertTrue(cfg.baseline_dir().endswith(os.path.join('baselines', 'main')))
        self.assertTrue(cfg.merged_md().endswith('alpha-main.md'))

    def test_several_editions_require_a_default(self):
        self.declare_editions(self.one, '[editions]\nmain = "主版本"\nabridged = "删节版"\n')
        with self.assertRaises(_config.ConfigError):
            _config.Config(self.one)
        self.assertEqual(_config.Config(self.one, 'abridged').edition, 'abridged')

    def test_an_undeclared_edition_is_refused(self):
        self.declare_editions(self.one, '[editions]\nmain = "主版本"\n')
        with self.assertRaises(_config.ConfigError):
            _config.Config(self.one, 'nope')

    def test_the_environment_selects_the_edition(self):
        self.declare_editions(self.one, '[editions]\nmain = "主版本"\n')
        os.environ['BOOK_EDITION'] = 'main'
        try:
            self.assertEqual(_config.Config(self.one).edition, 'main')
        finally:
            os.environ.pop('BOOK_EDITION', None)

    def test_the_default_book_matches_its_module_attributes(self):
        active = _config.current()
        self.assertEqual(_config.BOOK_ROOT, active.root)
        self.assertEqual(_config.MANUSCRIPT_DIR, active.manuscript_dir)
        self.assertEqual(_config.THRESHOLDS, active.thresholds)
        self.assertEqual(_config.chapter_names(), active.chapter_names())


if __name__ == '__main__':
    unittest.main()
