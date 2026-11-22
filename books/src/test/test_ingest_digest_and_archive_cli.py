#!/usr/bin/env python3
"""The inventory merge and the docs-archive CLI: the two paths nothing drove."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stdout

import _fixture

TAGS = ('layer:ingest', 'tier:fast')

_fixture.ensure_tools_path()

RELEASED_CHANGELOG = """# 变更日志
> 版本：v0.1
---

## [0.1] - 2026-01-01

### 变更
- 第一件事
"""
LIVE_CHANGELOG = """# 变更日志
> 版本：v0.2
---

## [0.2] - 开发中（未发布）

### 变更
- 下一件事
"""


def inventory(label_of_root: str, packages: dict, languages=('java',)) -> dict:
    totals = {'packages': len(packages), 'files': 0, 'lines': 0}
    for info in packages.values():
        totals['files'] += info.get('files', 0)
        totals['lines'] += info.get('lines', 0)
    return {'root': label_of_root, 'languages': list(languages), 'totals': totals,
            'by_language': {}, 'packages': packages}


class MergeRootsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.digest = _fixture.load_module(self.root, 'digest')

    def test_two_trees_keep_both_packages_under_their_label(self):
        merged = self.digest.merge_roots([
            ('main', inventory('main', {'org.a': {'files': 2, 'lines': 10}})),
            ('test', inventory('test', {'org.a': {'files': 1, 'lines': 5}},
                               languages=('java', 'python'))),
        ])
        self.assertEqual(sorted(merged['packages']), ['main:org.a', 'test:org.a'])
        self.assertEqual(merged['packages']['test:org.a']['root'], 'test')
        self.assertEqual(merged['totals']['files'], 3)
        self.assertEqual(merged['totals']['lines'], 15)
        self.assertEqual(merged['languages'], ['java', 'python'])
        self.assertEqual(sorted(merged['roots']), ['main', 'test'])
        self.assertEqual(merged['by_root']['test']['lines'], 5)

    def test_main_merges_when_the_policy_declares_two_roots(self):
        calls = []

        def fake_digest(root, language=None):
            calls.append(root)
            return inventory(root, {f'org.{os.path.basename(root)}': {'files': 1, 'lines': 1}})

        def fake_roots():
            return [{'label': 'main', 'path': 'src/main'},
                    {'label': 'test', 'path': 'src/test'}]

        book = unittest.mock.MagicMock()
        book.source_roots.return_value = fake_roots()

        buffer = io.StringIO()
        with unittest.mock.patch.object(self.digest, 'digest', side_effect=fake_digest), \
                unittest.mock.patch.object(self.digest._config, 'source_tree',
                                           side_effect=lambda label: f'/src/{label}'), \
                unittest.mock.patch.object(self.digest._config, 'current',
                                           return_value=book), \
                redirect_stdout(buffer):
            code = self.digest.main(['--out', os.path.join(self.root, 'inv.json')])
        self.assertEqual(code, 0, buffer.getvalue()[-400:])
        self.assertEqual(len(calls), 2)
        with open(os.path.join(self.root, 'inv.json'), encoding='utf-8') as fh:
            written = json.load(fh)
        self.assertEqual(sorted(written['packages']), ['main:org.main', 'test:org.test'])

    def test_json_mode_prints_only_the_summary(self):
        buffer = io.StringIO()
        with unittest.mock.patch.object(self.digest, 'digest',
                                        return_value=inventory('main', {})), \
                redirect_stdout(buffer):
            code = self.digest.main(['--json', '--root', '/src/main'])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(sorted(payload), ['by_language', 'languages', 'root', 'totals'])


class DocsArchiveCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.archive = _fixture.load_module(self.root, 'docs_archive')
        self.docs = os.path.join(self.root, 'docs')
        os.makedirs(os.path.join(self.docs, 'managements'), exist_ok=True)

    def write_ledgers(self, changelog: str) -> None:
        for name, text in (('changelog', changelog),
                           ('plan', '# 实施与维护计划\n\n## 概述\n\n在办 0 项。\n'),
                           ('review-findings', '# 自我审查问题记录\n\n## 当前待处理问题\n')):
            with open(os.path.join(self.docs, 'managements', f'{name}.md'),
                      'w', encoding='utf-8') as fh:
                fh.write(text)

    def test_dry_run_describes_the_moves_without_writing(self):
        self.write_ledgers(RELEASED_CHANGELOG)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.archive.main(['--version', '0.1', '--dry-run',
                                      '--date', '2026-01-01', '--docs', self.docs])
        self.assertEqual(code, 0, buffer.getvalue()[-400:])
        self.assertIn('would ', buffer.getvalue())
        self.assertFalse(os.path.isdir(os.path.join(self.docs, 'archive', 'v0.1')))

    def test_an_unknown_version_is_reported_and_nothing_moves(self):
        self.write_ledgers(LIVE_CHANGELOG)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.archive.main(['--version', '9.9', '--docs', self.docs])
        self.assertEqual(code, 2)
        self.assertIn('error:', buffer.getvalue())

    def test_a_missing_docs_tree_is_an_error_not_a_traceback(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.archive.main(['--version', '0.1',
                                      '--docs', os.path.join(self.root, 'nope')])
        self.assertEqual(code, 2)
        self.assertIn('error:', buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
