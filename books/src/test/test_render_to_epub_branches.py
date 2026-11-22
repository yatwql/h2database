#!/usr/bin/env python3
"""to_epub in-process: the fallbacks and failures around the pandoc call.

The happy path is covered next door; what is left here is the set of paths a
delivery engineer actually hits: pandoc missing, pandoc crashing, pandoc
producing nothing, and a cover page that carries none of the metadata the
script looks for.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ('layer:render', 'tier:fast')

_fixture.ensure_tools_path()

REAL_RUN = subprocess.run
REAL_EXISTS = os.path.exists

COVER_FULL = (
    '# 测试之书\n\n## 副标题\n\n版本 v0.1 · 2026-01-01 · 100 行\n\n'
    '**作者：其·龙**\n'
)


def pandoc_stub(*, path: str = '/usr/bin/pandoc', writes: bool = True,
                returncode: int = 0, stdout: str = 'pandoc 3.1.0\n',
                probe_stdout: str = 'pandoc 3.1.0\n', stderr: str = ''):
    """Stand in for pandoc only; merge.py still runs for real."""

    def run(command, **kwargs):
        if command and str(command[0]) == path:
            if '-o' not in command:
                return subprocess.CompletedProcess(command, 0, stdout=probe_stdout, stderr='')
        else:
            return REAL_RUN(command, **kwargs)
        if writes and returncode == 0:
            out = command[command.index('-o') + 1]
            os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
            with open(out, 'w', encoding='utf-8') as fh:
                fh.write('fake epub\n')
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)

    return run


class ToEpubBranchesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.cover = os.path.join(self.root, 'data', 'manuscript', 'cover.md')
        self.merged = os.path.join(self.root, 'dist', 'test-book.md')
        self.epub = os.path.join(self.root, 'dist', 'test-book.epub')
        self.write_cover(COVER_FULL)

    def write_cover(self, text: str) -> None:
        with open(self.cover, 'w', encoding='utf-8') as fh:
            fh.write(text)

    def write_merged(self, text: str = '# 测试之书\n\n正文。\n') -> None:
        os.makedirs(os.path.dirname(self.merged), exist_ok=True)
        with open(self.merged, 'w', encoding='utf-8') as fh:
            fh.write(text)

    def run_epub(self, *, which: str | None = '/usr/bin/pandoc',
                 pandoc_run=None, exists=None):
        patches = [
            mock.patch.object(shutil, 'which', return_value=which),
            mock.patch.object(subprocess, 'run', side_effect=pandoc_run or pandoc_stub()),
        ]
        if exists is not None:
            patches.append(mock.patch.object(os.path, 'exists', side_effect=exists))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        return _fixture.run_inproc(self.root, 'to_epub.py')

    def test_missing_pandoc_explains_how_to_install_it(self):
        code, out = self.run_epub(which=None)
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('pandoc not found', out)
        self.assertIn('winget install', out)

    def test_version_probe_failure_is_skipped_not_fatal(self):
        def run(command, **kwargs):
            if '--version' in command:
                raise OSError('probe exploded')
            return REAL_RUN(command, **kwargs)

        # the stub path does not exist, so the conversion raises FileNotFoundError
        code, out = self.run_epub(which='/nonexistent/pandoc', pandoc_run=run)
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('version probe skipped: probe exploded', out)
        self.assertIn('disappeared between detection and invocation', out)

    def test_absent_merge_script_is_tolerated(self):
        self.write_merged()

        def exists(path):
            return False if str(path).endswith('merge.py') else REAL_EXISTS(path)

        code, out = self.run_epub(exists=exists)
        self.assertEqual(code, 0, out[-600:])
        self.assertTrue(os.path.isfile(self.epub))
        self.assertIn('Step 1', out)

    def test_missing_merged_markdown_is_reported(self):
        def exists(path):
            return False if str(path) == self.merged else REAL_EXISTS(path)

        code, out = self.run_epub(exists=exists)
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('Merged Markdown not found', out)
        self.assertFalse(os.path.exists(self.epub))

    def test_cover_without_metadata_falls_back_to_the_config(self):
        self.write_cover('无标题页：这一页没有任何脚本要抓的字段。\n')
        code, out = self.run_epub()
        self.assertEqual(code, 0, out[-600:])
        self.assertTrue(os.path.isfile(self.epub))
        self.assertIn('Version: v', out)

    def test_cover_version_mismatch_warns_but_still_builds(self):
        self.write_cover('# 测试之书\n\n## 副标题\n\n版本 v9.9 · 2026-01-01\n\n**作者：其·龙**\n')
        code, out = self.run_epub()
        self.assertEqual(code, 0, out[-600:])
        self.assertIn('cover says v9.9', out)
        self.assertTrue(os.path.isfile(self.epub))

    def test_silent_merge_and_missing_cover_fall_back_to_the_config(self):
        self.write_merged()
        os.remove(self.cover)

        def run(command, **kwargs):
            if str(command[0]) == '/usr/bin/pandoc':
                return pandoc_stub()(command, **kwargs)
            return subprocess.CompletedProcess(command, 0, stdout='', stderr='')

        code, out = self.run_epub(pandoc_run=run)
        self.assertEqual(code, 0, out[-600:])
        self.assertTrue(os.path.isfile(self.epub))
        self.assertIn('Title:', out)
        self.assertIn('Author:', out)

    def test_merge_failure_aborts_before_pandoc(self):
        def run(command, **kwargs):
            if str(command[0]) != '/usr/bin/pandoc':
                return subprocess.CompletedProcess(command, 1, stdout='', stderr='merge boom')
            return pandoc_stub()(command, **kwargs)

        code, out = self.run_epub(pandoc_run=run)
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('merge.py FAILED', out)
        self.assertIn('merge boom', out)
        self.assertFalse(os.path.exists(self.epub))

    def test_quiet_probe_and_quiet_conversion_stay_silent(self):
        def run(command, **kwargs):
            if str(command[0]) == '/usr/bin/pandoc':
                return pandoc_stub(stdout='', probe_stdout='')(command, **kwargs)
            return REAL_RUN(command, **kwargs)

        code, out = self.run_epub(pandoc_run=run)
        self.assertEqual(code, 0, out[-600:])
        self.assertIn('=== Step 0: pandoc detected', out)
        self.assertTrue(os.path.isfile(self.epub))

    def test_pandoc_failure_prints_both_streams(self):
        code, out = self.run_epub(
            pandoc_run=pandoc_stub(writes=False, returncode=43,
                                   stdout='half written\n', stderr='boom\n'))
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('pandoc FAILED', out)
        self.assertIn('half written', out)
        self.assertIn('boom', out)

    def test_pandoc_failure_with_empty_streams_reports_only_the_verdict(self):
        code, out = self.run_epub(pandoc_run=pandoc_stub(writes=False, returncode=2,
                                                         stdout='', stderr=''))
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('pandoc FAILED', out)

    def test_pandoc_success_without_output_is_a_failure(self):
        code, out = self.run_epub(pandoc_run=pandoc_stub(writes=False))
        self.assertEqual(code, 1, out[-400:])
        self.assertIn('EPUB not produced', out)

    def test_pandoc_warnings_and_notes_are_surfaced(self):
        code, out = self.run_epub(
            pandoc_run=pandoc_stub(stdout='note: merged 12 files\n',
                                   stderr='warn: a heading was empty\n'))
        self.assertEqual(code, 0, out[-600:])
        self.assertIn('[pandoc warn] warn: a heading was empty', out)
        self.assertIn('note: merged 12 files', out)


if __name__ == '__main__':
    unittest.main()
