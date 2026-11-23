#!/usr/bin/env python3
"""readability: box closure, caption quality, fences and the HTML check.

Each check appends to a module-level list, so a case clears it first and then
asserts the wording — that is what makes the report trustworthy.
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

TOOLS_DIR = _fixture.TOOLS_DIR
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)


class ReadabilityRulesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'readability')
        self.mod.warnings.clear()
        self.mod.failures.clear()
        self.addCleanup(self.mod.warnings.clear)
        self.addCleanup(self.mod.failures.clear)

    # -- box closure -----------------------------------------------------
    def test_a_balanced_box_draws_no_warning(self):
        self.mod.check_box_closure(['┌──┐', '│  │', '└──┘'], 5, 'x.md')
        self.assertEqual(self.mod.warnings, [])

    def test_each_unpaired_corner_is_named(self):
        self.mod.check_box_closure(['┌──┐', '│  │', '└──┤', '┬──┴', '┌──┐'], 5, 'x.md')
        text = '\n'.join(self.mod.warnings)
        self.assertIn('└', text)          # └ != ┘
        self.assertIn('├', text)          # ├ != ┤
        self.assertTrue(self.mod.warnings)

    def test_a_block_without_box_characters_is_ignored(self):
        self.mod.check_box_closure(['plain text', 'more text'], 5, 'x.md')
        self.assertEqual(self.mod.warnings, [])

    # -- caption quality -------------------------------------------------
    def test_a_short_caption_is_reported(self):
        self.mod.check_caption_quality('x.md', ['**图 1-1: 架构**'])
        self.assertTrue(any('caption too short' in w for w in self.mod.warnings))

    def test_a_caption_without_a_verb_is_reported(self):
        self.mod.check_caption_quality('x.md', ['**图 1-2: 三个组件的名字**'])
        self.assertTrue(any('caption may lack verb' in w for w in self.mod.warnings))

    def test_a_good_caption_is_silent(self):
        self.mod.check_caption_quality('x.md', ['**图 1-3: 写入流程与目录布局的关系**'])
        self.assertEqual(self.mod.warnings, [])

    def test_caption_checks_only_run_when_asked(self):
        path = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('\n**图 9-9: 架构**\n')
        self.mod.warnings.clear()
        setattr(self.mod, 'RUN_FIGURE_CHECKS', False)
        self.mod.main([])
        self.assertFalse(any('caption too short' in w for w in self.mod.warnings))
        self.mod.warnings.clear()
        setattr(self.mod, 'RUN_FIGURE_CHECKS', True)
        self.mod.main(['--figures'])
        self.assertTrue(any('caption too short' in w for w in self.mod.warnings))

    # -- fences and the html check ---------------------------------------
    def test_an_unclosed_fence_is_a_failure(self):
        failures = self.mod._scan_fences('x.md', ['```text', 'a', 'b'])
        self.assertTrue(any('unclosed fence' in f for f in failures))

    def test_a_caption_inside_a_fence_is_a_failure(self):
        failures = self.mod._scan_fences('x.md', ['```text', '**图 1-1: 架构**', '```'])
        self.assertTrue(any('caption inside fence' in f for f in failures))

    def test_a_wider_than_allowed_diagram_is_a_warning(self):
        wide = '┌' + '─' * 130 + '┐'
        self.mod._scan_fences('x.md', ['```text', wide, '└' + '─' * 130 + '┘', '```'])
        self.assertTrue(any('diagram width' in w for w in self.mod.warnings))

    def test_diagram_lines_outside_pre_are_reported(self):
        html = os.path.join(self.root, 'dist', 'test-book.html')
        os.makedirs(os.path.dirname(html), exist_ok=True)
        with open(html, 'w', encoding='utf-8') as fh:
            fh.write('<p>┌──┐</p>\n<p>│  │</p>\n<p>└──┘</p>\n')
        self.mod.failures.clear()
        self.mod._check_html()
        self.assertTrue(any('outside <pre>' in f for f in self.mod.failures))

    def test_without_html_the_check_is_skipped(self):
        self.mod.failures.clear()
        self.mod._check_html()
        self.assertEqual(self.mod.failures, [])

    # -- main ------------------------------------------------------------
    def test_json_mode_emits_both_lists(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(['--json'])
        self.assertEqual(code, 0, buffer.getvalue()[-300:])
        self.assertIn('"failures"', buffer.getvalue())
        self.assertIn('"warnings"', buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
