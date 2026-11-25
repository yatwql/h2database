#!/usr/bin/env python3
"""Chapter-fragment cache: only changed chapters re-render, bytes never change."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:render', 'tier:fast')

_fixture.ensure_tools_path()


class ChunkAndKeyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.cache = _fixture.load_module(self.root, 'html_cache')

    def test_chunks_split_at_top_level_headings(self):
        chunks = self.cache.chunk_lines(['# 第1章', 'text', '## 1.1', '# 第2章', 'more'])
        self.assertEqual([chunk[0] for chunk in chunks], ['# 第1章', '# 第2章'])

    def test_a_heading_inside_a_fence_does_not_split(self):
        chunks = self.cache.chunk_lines(
            ['# 第1章', '```java', '# not a heading', '```', '# 第2章', 'text'])
        self.assertEqual(len(chunks), 2)
        self.assertIn('# not a heading', chunks[0])

    def test_an_unclosed_fence_keeps_the_rest_in_one_chunk(self):
        chunks = self.cache.chunk_lines(['# 第1章', '```', '# 第2章', 'text'])
        self.assertEqual(len(chunks), 1)

    def test_empty_input_yields_no_chunk(self):
        self.assertEqual(self.cache.chunk_lines([]), [])

    def test_the_key_follows_content_and_renderer(self):
        first = self.cache.key_for(['a'], 'v1')
        self.assertNotEqual(first, self.cache.key_for(['b'], 'v1'))
        self.assertNotEqual(first, self.cache.key_for(['a'], 'v2'))
        self.assertEqual(first, self.cache.key_for(['a'], 'v1'))

    def test_store_load_and_prune_round_trip(self):
        self.cache.store('keep', {'html': '<p>x</p>', 'fences': 0, 'unclosed': False})
        self.cache.store('drop', {'html': '<p>y</p>', 'fences': 0, 'unclosed': False})
        self.assertEqual(self.cache.load('keep')['html'], '<p>x</p>')
        self.assertEqual(self.cache.prune({'keep'}), 1)
        self.assertIsNone(self.cache.load('drop'))

    def test_a_corrupt_entry_is_a_miss(self):
        self.cache.store('bad', {'html': 'x'})
        path = os.path.join(self.cache.cache_root(), 'bad.json')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('{not json')
        self.assertIsNone(self.cache.load('bad'))


class FragmentReuseTest(unittest.TestCase):
    """The renderer reuses fragments and still writes byte-identical HTML."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def build(self, *extra: str) -> str:
        code, out = _fixture.run_inproc(self.root, 'render/merge.py')
        self.assertEqual(code, 0, out[-400:])
        code, out = _fixture.run_inproc(self.root, 'render/to_html.py', *extra)
        self.assertEqual(code, 0, out[-400:])
        return out

    def html(self) -> bytes:
        path = os.path.join(self.root, 'dist', 'test-book.html')
        with open(path, 'rb') as fh:
            return fh.read()

    def counts(self, out: str) -> tuple[int, int]:
        line = [ln for ln in out.splitlines() if 'Chapter fragments' in ln][-1]
        parts = line.split('Chapter fragments: ')[1].split()
        return int(parts[0]), int(parts[3])

    def test_the_second_build_reuses_every_fragment(self):
        first = self.build()
        self.assertEqual(self.counts(first)[0], 0)
        self.assertGreater(self.counts(first)[1], 0)
        cached_bytes = self.html()

        second = self.build()
        self.assertEqual(self.counts(second)[1], 0)
        self.assertEqual(self.html(), cached_bytes)

    def test_full_rebuild_matches_the_cached_output(self):
        self.build()
        cached_bytes = self.html()
        out = self.build('--full')
        self.assertEqual(self.counts(out)[0], 0)
        self.assertEqual(self.html(), cached_bytes)

    def test_one_changed_chapter_renders_one_fragment(self):
        self.build()
        before = self.html()
        path = os.path.join(self.root, 'data', 'manuscript', 'ch2-test.md')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text + '\n新增的一段正文。\n')

        out = self.build()
        self.assertEqual(self.counts(out)[1], 1)
        self.assertGreater(self.counts(out)[0], 0)
        self.assertNotEqual(self.html(), before)

    def test_the_cache_lives_under_the_gitignored_cache_directory(self):
        self.build()
        folder = os.path.join(self.root, 'data', 'cache', 'html-cache')
        entries = [name for name in os.listdir(folder) if name.endswith('.json')]
        self.assertTrue(entries)
        with open(os.path.join(folder, entries[0]), encoding='utf-8') as fh:
            self.assertIn('html', json.load(fh))


if __name__ == '__main__':
    unittest.main()


class CacheFailureTest(unittest.TestCase):
    """A cache that cannot be read, written or pruned must not fail a render."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.cache = _fixture.load_module(self.root, 'html_cache')

    def test_a_definition_without_readable_source_hashes_a_stable_fallback(self):
        self.assertEqual(self.cache.fingerprint(len), self.cache.fingerprint(sorted))
        self.assertRegex(self.cache.fingerprint(len), r'^[0-9a-f]{16}$')

    def test_an_unreadable_entry_reads_as_a_miss(self):
        folder = self.cache.cache_root()
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, 'deadbeef.json')
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write('{not json')
        self.assertIsNone(self.cache.load('deadbeef'))

    def test_a_writable_failure_is_not_fatal(self):
        with mock.patch.object(self.cache.os, 'makedirs', side_effect=OSError('ro')):
            self.assertIsNone(self.cache.store('key', {'html': '<p>x</p>'}))
            self.assertIsNone(self.cache.load('key'))

    def test_pruning_survives_an_unreadable_directory(self):
        with mock.patch.object(self.cache.os, 'listdir', side_effect=OSError('ro')):
            self.assertEqual(self.cache.prune(set()), 0)

    def test_pruning_survives_a_file_it_cannot_remove(self):
        folder = self.cache.cache_root()
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, 'stale.json'), 'w', encoding='utf-8') as handle:
            handle.write('{}')
        with mock.patch.object(self.cache.os, 'remove', side_effect=OSError('ro')):
            self.assertEqual(self.cache.prune(set()), 0)
