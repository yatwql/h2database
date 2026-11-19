#!/usr/bin/env python3
"""Genericity regression: stage 1 must work on a non-H2 source tree.

The fixture book is pointed at a miniature Java project; digest, outline and
chapter rendering must run with no code changes and no H2-specific data.
"""
import json
import os
import sys
import tempfile
import unittest

import _fixture

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
    sys.path.insert(0, os.path.join(TOOLS_DIR, _sub))

MINI_TREE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'fixtures', 'mini-java')


class TestGenericSourceTree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        base_path = os.path.join(self.root, 'data', 'config', 'base.json')
        with open(base_path, encoding='utf-8') as fh:
            base = json.load(fh)
        base['sources']['src_main'] = MINI_TREE
        base['sources']['package_prefix'] = 'org.example'
        base['sources']['languages'] = ['java']
        with open(base_path, 'w', encoding='utf-8') as fh:
            json.dump(base, fh, ensure_ascii=False, indent=2)

    def run_script(self, script, *args):
        return _fixture.run_inproc(self.root, script, *args)

    def read(self, *parts):
        with open(os.path.join(self.root, *parts), encoding='utf-8') as fh:
            return fh.read()

    def test_stage1_on_mini_tree(self):
        code, out = self.run_script('digest.py')
        self.assertEqual(code, 0, out[-400:])
        inventory = json.loads(self.read('data', 'state', 'source-inventory.json'))
        self.assertIn('org.example', inventory['packages'])
        package = inventory['packages']['org.example']
        self.assertGreaterEqual(package['files'], 1)
        self.assertIn('Widget', [u['name'] for u in package['classes']])

        code, out = self.run_script('outline.py')
        self.assertEqual(code, 0, out[-400:])
        outline = json.loads(self.read('data', 'state', 'outline.json'))
        self.assertFalse(any(ch['missing_packages'] for ch in outline['chapters']))

        code, out = self.run_script('chapters.py')
        self.assertEqual(code, 0, out[-400:])
        chapter = self.read('data', 'manuscript', 'ch1-test.md')
        self.assertIn('org.example', chapter)
        self.assertIn('Widget', chapter)
        self.assertNotIn('org.h2', chapter)


if __name__ == '__main__':
    unittest.main()
