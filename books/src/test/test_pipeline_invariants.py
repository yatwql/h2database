#!/usr/bin/env python3
"""Invariants: parsing is stable, numbering is idempotent, output is deterministic.

Coverage says a line ran; these say the behaviour is a function of the input.
Each case states one invariant that must hold for *every* input, not just for
the fixture the other suites happen to use.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest

import _fixture

TAGS = ('layer:pipeline', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


def digest(path: str) -> str:
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class IndexParseInvariants(unittest.TestCase):
    """`parse_index` must be lossless for the parts the gate judges."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'index_xrefs')
        self.path = os.path.join(self.root, 'data', 'manuscript', 'back', 'index.md')
        with open(self.path, 'w', encoding='utf-8') as fh:
            fh.write('# 索引\n\n## A\n\n- ACID —— §1.1\n  - 原子性 —— §1.1\n'
                     '  see also: MVStore\n\n## M\n\n- MVStore —— §2.1\n'
                     '  see also: ACID, 隔离性\n')

    def test_reparsing_reports_the_same_terms_and_chapters(self):
        first = self.mod.parse_index(self.path)
        second = self.mod.parse_index(self.path)
        self.assertEqual(first, second)          # deterministic
        mains, subs, see_alsos, sections = first
        self.assertEqual(sorted(mains), ['ACID', 'MVStore'])
        self.assertEqual(mains['ACID']['chapters'], [1])
        self.assertEqual([sub['term'] for sub in subs], ['原子性'])
        self.assertEqual(sections, [('A', 3), ('M', 9)])
        self.assertEqual(len(see_alsos), 2)

    def test_a_term_seen_twice_keeps_the_last_position(self):
        with open(self.path, 'a', encoding='utf-8') as fh:
            fh.write('\n- ACID —— §9.9\n')
        mains, _subs, _see, _sections = self.mod.parse_index(self.path)
        self.assertEqual(mains['ACID']['chapters'], [9])


class RenumberInvariants(unittest.TestCase):
    """`renumber --write` stores a mapping; running it again changes nothing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        book = os.path.join(self.root, 'data', 'book', 'book.toml')
        with open(book, encoding='utf-8') as fh:
            original = fh.read()
        with open(book, 'w', encoding='utf-8') as fh:
            fh.write('default_edition = "main"\n' + original
                     + '\n[editions]\n\n[editions.main]\ndisplay = "主版本"\n'
                     + '\n[editions.main.chapters.numbering]\n"ch2-test.md" = [7]\n')
        edition_dir = os.path.join(self.root, 'data', 'manuscript', 'main')
        os.makedirs(edition_dir, exist_ok=True)
        for name in ('ch1-test.md', 'ch2-test.md'):
            source = os.path.join(self.root, 'data', 'manuscript', name)
            with open(source, encoding='utf-8') as fh:
                text = fh.read()
            with open(os.path.join(edition_dir, name), 'w', encoding='utf-8') as fh:
                fh.write(text)
        os.environ['BOOK_EDITION'] = 'main'
        self.addCleanup(os.environ.pop, 'BOOK_EDITION', None)

    def test_the_stored_mapping_is_stable_across_runs(self):
        mapping = os.path.join(self.root, 'data', 'state', 'main', 'renumber.json')
        first_code, first_out = _fixture.run_inproc(self.root, 'renumber.py', '--write')
        self.assertEqual(first_code, 0, first_out[-300:])
        with open(mapping, encoding='utf-8') as fh:
            first = json.load(fh)
        second_code, second_out = _fixture.run_inproc(self.root, 'renumber.py', '--write')
        self.assertEqual(second_code, 0, second_out[-300:])
        with open(mapping, encoding='utf-8') as fh:
            second = json.load(fh)
        self.assertEqual(first, second)
        self.assertTrue(first, 'the mapping must not be empty')

    def test_rewriting_references_twice_changes_nothing_more(self):
        chapter = os.path.join(self.root, 'data', 'manuscript', 'main', 'ch2-test.md')
        with open(chapter, 'a', encoding='utf-8') as fh:
            fh.write('\n详见第7章《测试章节》。\n')
        _fixture.run_inproc(self.root, 'renumber.py', '--apply')
        first = digest(chapter)
        _fixture.run_inproc(self.root, 'renumber.py', '--apply')
        self.assertEqual(digest(chapter), first)


class MergeInvariants(unittest.TestCase):
    """Merging twice yields the same bytes: the pipeline is reproducible."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.merged = os.path.join(self.root, 'dist', 'test-book.md')

    def test_two_merges_produce_identical_files(self):
        first_code, first_out = _fixture.run_inproc(self.root, 'merge.py')
        self.assertEqual(first_code, 0, first_out[-300:])
        first = digest(self.merged)
        second_code, second_out = _fixture.run_inproc(self.root, 'merge.py')
        self.assertEqual(second_code, 0, second_out[-300:])
        self.assertEqual(digest(self.merged), first)

    def test_the_merged_file_holds_every_chapter_once(self):
        _fixture.run_inproc(self.root, 'merge.py')
        with open(self.merged, encoding='utf-8') as fh:
            text = fh.read()
        for marker in ('# 第1章', '# 第2章'):
            self.assertEqual(text.count(marker), 1, marker)


if __name__ == '__main__':
    unittest.main()
