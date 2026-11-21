#!/usr/bin/env python3
"""Fact-block refresh: only the marked blocks move, prose stays byte-identical."""

from __future__ import annotations

import argparse
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

TAGS = ('layer:ingest', 'tier:fast')

_fixture.ensure_tools_path()

def package(lines: int, classes: int = 2) -> dict:
    """One package entry shaped like the source inventory."""
    return {
        'lines': lines, 'files': 3, 'summary': '示例包',
        'depends_on': {'org.example.core': 4},
        'key_classes': [
            {'name': f'Widget{index}', 'lines': max(1, lines // (index + 2)),
             'public_methods': index + 1, 'summary': '示例类型',
             'rel': f'org/example/Widget{index}.java',
             'api': ['run'], 'api_lines': {'run': 10 + index}}
            for index in range(classes)
        ],
    }


class RefreshBlocksTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, 'chapters')
        self.factblocks = _fixture.load_module(self.root, 'factblocks')

    def chapter(self, lines: int) -> dict:
        return {'file': 'ch1-test.md', 'source_lines': lines,
                'packages': {'org.example': package(lines)}}

    def test_the_renderer_marks_every_recomputable_block(self):
        text = self.chapters.render_chapter(self.chapter(120))
        self.assertIn('<!-- generated:packages -->', text)
        self.assertIn('<!-- generated:api -->', text)
        self.assertIn('<!-- /generated -->', text)

    def test_refresh_swaps_only_the_marked_blocks(self):
        old = self.chapters.render_chapter(self.chapter(120))
        new = self.chapters.render_chapter(self.chapter(480))
        result = self.factblocks.refresh_blocks(old, new)
        self.assertIsNotNone(result)
        refreshed, removed, added = result
        self.assertGreater(removed + added, 0)

        self.assertTrue(self.factblocks.generated_blocks(old))
        old_lines = old.split('\n')
        spans = []
        name = None
        start = 0
        for index, line in enumerate(old_lines):
            opening = self.factblocks.GENERATED_OPEN_RE.match(line.strip())
            if opening and name is None:
                name, start = opening.group(1), index
                continue
            if self.factblocks.GENERATED_CLOSE_RE.match(line.strip()) and name is not None:
                spans.append((start, index))
                name = None
        refreshed_lines = refreshed.split('\n')
        changed = [index for index, before in enumerate(old_lines)
                   if before != refreshed_lines[index]]
        for index in changed:
            self.assertTrue(any(start <= index <= end for start, end in spans),
                            f'line {index} changed outside a marked block: {old_lines[index]}')

    def test_prose_outside_the_markers_survives_verbatim(self):
        old = self.chapters.render_chapter(self.chapter(120))
        prose = '这是作者自己写的一段正文，刷新事实块时一个字都不该动。'
        injected = old.replace('## 1.1 模块版图', prose + '\n\n## 1.1 模块版图', 1)
        refreshed, _removed, _added = self.factblocks.refresh_blocks(
            injected, self.chapters.render_chapter(self.chapter(480)))
        self.assertIn(prose, refreshed)

    def test_a_file_without_markers_reports_nothing_to_refresh(self):
        self.assertIsNone(
            self.factblocks.refresh_blocks('# 第1章 手写章节\n\n全是人写的正文。\n', ''))

    def test_unchanged_facts_produce_an_identical_file(self):
        text = self.chapters.render_chapter(self.chapter(120))
        refreshed, removed, added = self.factblocks.refresh_blocks(text, text)
        self.assertEqual((refreshed, removed, added), (text, 0, 0))


class ForceAndRefreshRunTest(unittest.TestCase):
    """The two write paths as the CLI drives them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, 'chapters')
        self.args = argparse.Namespace(only=None, dry_run=False,
                                       force=False, refresh_facts=False, llm=False)
        self.chapter = {'file': 'ch1-test.md', 'source_lines': 120,
                        'packages': {'org.example': package(120)}}

    def path(self) -> str:
        return os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')

    def test_force_backs_the_old_file_up_and_reports_the_cost(self):
        self.args.force = True
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = self.chapters._emit_chapter(self.chapter, self.args, 'STAMP')
        self.assertEqual(status, 'written')
        self.assertIn('-', buffer.getvalue())
        backup = os.path.join(self.root, 'data', 'tmp', 'generated-backup', 'STAMP',
                              'ch1-test.md')
        self.assertTrue(os.path.isfile(backup))

    def test_refresh_leaves_an_unmarked_file_alone_and_says_why(self):
        self.args.refresh_facts = True
        before = '# 第1章 示例总览\n\n作者手写正文。\n'
        with open(self.path(), 'w', encoding='utf-8') as fh:
            fh.write(before)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = self.chapters._emit_chapter(self.chapter, self.args, 'STAMP')
        self.assertEqual(status, 'skip')
        self.assertIn('无标记块', buffer.getvalue())
        with open(self.path(), encoding='utf-8') as fh:
            self.assertEqual(fh.read(), before)

    def test_refresh_rewrites_a_marked_file_in_place(self):
        self.args.refresh_facts = True
        with open(self.path(), 'w', encoding='utf-8') as fh:
            fh.write(self.chapters.render_chapter(self.chapter))
        self.chapter['source_lines'] = 900
        self.chapter['packages'] = {'org.example': package(900)}
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            status = self.chapters._emit_chapter(self.chapter, self.args, 'STAMP')
        self.assertEqual(status, 'refresh')
        with open(self.path(), encoding='utf-8') as fh:
            self.assertIn('| `org.example` | 3 | 900 |', fh.read())

    def test_the_run_summary_names_refreshed_and_skipped_chapters(self):
        state = os.path.join(self.root, 'data', 'state')
        os.makedirs(state, exist_ok=True)
        with open(os.path.join(state, 'source-inventory.json'), 'w', encoding='utf-8') as fh:
            json.dump({'packages': {}}, fh)
        with open(os.path.join(state, 'outline.json'), 'w', encoding='utf-8') as fh:
            json.dump({'chapters': [self.chapter]}, fh)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.chapters.main(['--refresh-facts'])
        self.assertEqual(code, 0)
        self.assertIn('刷新 0 章 / 跳过 1 章（无标记块）', buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
