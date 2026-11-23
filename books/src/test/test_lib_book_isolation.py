#!/usr/bin/env python3
"""Two books with identically named files: nothing leaks between them.

Every book has `data/manuscript/ch1-test.md`, `data/config/base.json` and
`dist/`; the names are the same on purpose. Isolation has to come from the book
root, never from the file name — this is the case that would break if a path
were resolved against the checkout, or a baseline were keyed by bare filename.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

CHAPTER = 'data/manuscript/ch1-test.md'


def digest(path: str) -> str:
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class SameNameIsolationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.first = _fixture.build_book(os.path.join(self.tmp.name, 'alpha'))
        self.second = _fixture.build_book(os.path.join(self.tmp.name, 'beta'))
        # running a delivery script points the process at that book; put the
        # selection back or the next suite inherits a directory this test deletes
        previous_env = os.environ.get('BOOK_ROOT')
        previous_cfg = _fixture.load_module(self.first, 'make')._config.current()
        self.addCleanup(lambda: __import__('lib._config', fromlist=['reset']).reset(previous_cfg))
        if previous_env is None:
            self.addCleanup(os.environ.pop, 'BOOK_ROOT', None)
        else:
            self.addCleanup(os.environ.__setitem__, 'BOOK_ROOT', previous_env)
        # same relative path, different text: a leak would be visible as a hash
        self.write(self.second, CHAPTER, '# 第1章 另一本书的正文\n\n完全不同的一段。\n')

    def write(self, root: str, rel: str, text: str) -> None:
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)

    def module(self, root: str, name: str):
        """Load a helper module, never a script that runs on import."""
        return _fixture.load_module(root, name)

    def config(self, root: str):
        """The book's configuration, without executing any delivery script."""
        _fixture.refresh_config(root)
        return __import__('lib._config', fromlist=['Config']).Config(root)

    def test_the_same_relative_path_resolves_inside_each_book(self):
        first_cfg = self.config(self.first)
        second_cfg = self.config(self.second)
        self.assertNotEqual(first_cfg.manuscript_dir, second_cfg.manuscript_dir)
        for cfg, root in ((first_cfg, self.first), (second_cfg, self.second)):
            self.assertTrue(cfg.manuscript_dir.startswith(os.path.abspath(root)))
            self.assertTrue(cfg.dist_dir.startswith(os.path.abspath(root)))

    def test_running_one_book_leaves_the_other_untouched(self):
        before_first = digest(os.path.join(self.first, CHAPTER))
        before_second = digest(os.path.join(self.second, CHAPTER))
        code, out = _fixture.run_inproc(self.first, 'merge.py')
        self.assertEqual(code, 0, out[-400:])
        self.assertTrue(os.path.isfile(os.path.join(self.first, 'dist', 'test-book.md')))
        self.assertFalse(os.path.exists(os.path.join(self.second, 'dist', 'test-book.md')),
                         'the merge of one book produced an artifact in the other')
        self.assertEqual(digest(os.path.join(self.first, CHAPTER)), before_first)
        self.assertEqual(digest(os.path.join(self.second, CHAPTER)), before_second)

    def test_a_baseline_written_for_one_book_is_not_visible_to_the_other(self):
        volume = self.module(self.first, 'content_volume')
        first_baseline = volume.baseline_path()
        os.makedirs(os.path.dirname(first_baseline), exist_ok=True)
        with open(first_baseline, 'w', encoding='utf-8') as fh:
            fh.write('{"files": {}}\n')

        other = self.module(self.second, 'content_volume')
        second_baseline = other.baseline_path()
        self.assertNotEqual(os.path.abspath(first_baseline), os.path.abspath(second_baseline))
        self.assertFalse(os.path.exists(second_baseline),
                         'one book reads the baseline of the other')

    def test_the_config_files_are_read_from_the_book_that_owns_them(self):
        self.write(self.second, 'data/config/base.json',
                   '{"logging": {"level": "DEBUG"}}')
        first = self.config(self.first)
        second = self.config(self.second)
        self.assertNotEqual(first.policy.get('logging', {}).get('level'),
                            second.policy.get('logging', {}).get('level'))


if __name__ == '__main__':
    unittest.main()
