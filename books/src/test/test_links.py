#!/usr/bin/env python3
"""Tests for the shared markdown helpers and the link/anchor audit."""
import importlib
import os
import sys
import tempfile
import unittest
from typing import ClassVar

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'sources'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

_mdutil = importlib.import_module('lib._mdutil')
_audit_links = importlib.import_module('_audit_links')


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_mdutil.slugify('第3章 包结构'), '第3章-包结构')

    def test_strips_punctuation(self):
        self.assertEqual(_mdutil.slugify('6.1 B-Tree：页面分裂'), '61-b-tree页面分裂')

    def test_lowercases_ascii(self):
        self.assertEqual(_mdutil.slugify('MVStore 架构'), 'mvstore-架构')


class TestHeadingScan(unittest.TestCase):
    LINES: ClassVar[list[str]] = [
        '# 第3章 包结构',
        '',
        '```text',
        '# 代码块里的不算',
        '```',
        '## 3.1 包结构',
    ]

    def test_fenced_headings_ignored(self):
        slugs = _mdutil.heading_slugs(self.LINES)
        self.assertIn('第3章-包结构', slugs)
        self.assertIn('31-包结构', slugs)
        self.assertNotIn('代码块里的不算', slugs)

    def test_iter_headings_levels(self):
        headings = _mdutil.iter_headings(self.LINES)
        self.assertEqual([lvl for lvl, _t, _s in headings], [1, 2])


class TestExternalDetection(unittest.TestCase):
    def test_external(self):
        for target in ('https://example.com', 'http://a.b', 'mailto:x@y.z'):
            self.assertTrue(_mdutil.is_external(target), target)

    def test_internal(self):
        for target in ('ch3-packages.md', '#anchor', 'back/glossary.md#term'):
            self.assertFalse(_mdutil.is_external(target), target)


class TestLinkExtraction(unittest.TestCase):
    def test_inline_and_image(self):
        links = _mdutil.iter_links('见 [图注](ch3.md) 与 ![图](img/a.png)')
        self.assertEqual([t for _l, t in links], ['ch3.md', 'img/a.png'])


class TestAuditLinks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def write(self, name: str, text: str) -> str:
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

    def audit(self, path: str) -> list:
        return _audit_links.audit_file(path, {})

    def test_valid_file_link(self):
        self.write('back/glossary.md', '# 术语表\n\n## A\n')
        page = self.write('ch3.md', '见 [术语表](back/glossary.md)\n')
        self.assertEqual(self.audit(page), [])

    def test_missing_file_detected(self):
        page = self.write('ch3.md', '见 [缺失](back/nope.md)\n')
        kinds = [v[2] for v in self.audit(page)]
        self.assertEqual(kinds, ['BROKEN_FILE'])

    def test_broken_anchor_detected(self):
        self.write('back/glossary.md', '# 术语表\n\n## A\n')
        page = self.write('ch3.md', '见 [术语表](back/glossary.md#nope)\n')
        kinds = [v[2] for v in self.audit(page)]
        self.assertEqual(kinds, ['BROKEN_ANCHOR'])

    def test_same_file_anchor_ok(self):
        page = self.write('ch3.md', '## 3.1 包结构\n\n见 [本节](#31-包结构)\n')
        self.assertEqual(self.audit(page), [])

    def test_same_file_anchor_broken(self):
        page = self.write('ch3.md', '## 3.1 包结构\n\n见 [别处](#99-不存在)\n')
        kinds = [v[2] for v in self.audit(page)]
        self.assertEqual(kinds, ['BROKEN_ANCHOR'])

    def test_external_links_ignored(self):
        page = self.write('ch3.md', '[H2](https://h2database.com)\n')
        self.assertEqual(self.audit(page), [])

    def test_links_inside_code_fence_ignored(self):
        page = self.write('ch3.md', '```text\n[缺失](nope.md)\n```\n')
        self.assertEqual(self.audit(page), [])

    def test_line_numbers_reported(self):
        page = self.write('ch3.md', '第一行\n\n见 [缺失](nope.md)\n')
        violations = self.audit(page)
        self.assertEqual(violations[0][1], 3)


if __name__ == '__main__':
    unittest.main()
