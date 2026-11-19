#!/usr/bin/env python3
"""Outline: inventory -> chapter plan, conflicts, missing packages and CLI."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

import _fixture

_fixture.ensure_tools_path()


class OutlineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.mod = _fixture.load_module(self.root, 'outline')

    def inventory(self, payload: dict) -> None:
        data = {'root': 'h2/src/main', 'totals': {'lines': 200, 'packages': 2}, **payload}
        path = os.path.join(self.root, 'data', 'state', 'source-inventory.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(data, fh)

    def packages(self) -> dict:
        return {
            'org.example': {'lines': 120, 'files': 3, 'summary': '示例',
                            'depends_on': {}, 'classes': [
                                {'name': 'Widget', 'lines': 40, 'public_methods': 2,
                                 'summary': '组件', 'rel': 'org/example/Widget.java',
                                 'api': ['run']}]},
            'org.example.core': {'lines': 80, 'files': 2, 'summary': '核心',
                                 'depends_on': {}, 'classes': []},
        }

    def test_outline_maps_packages_to_chapters(self):
        self.inventory({'packages': self.packages()})
        outline = self.mod.build_outline()
        self.assertTrue(outline['chapters'])
        mapped = {ch['file']: ch['packages'] for ch in outline['chapters']}
        self.assertIn('ch1-test.md', mapped)

    def test_missing_package_is_recorded(self):
        payload = self.packages()
        payload.pop('org.example.core')
        self.inventory({'packages': payload})
        outline = self.mod.build_outline()
        missing = [ch['missing_packages'] for ch in outline['chapters'] if ch['missing_packages']]
        self.assertTrue(missing)

    def test_ownership_conflicts_are_reported(self):
        self.inventory({'packages': self.packages()})
        with mock.patch.object(self.mod._config, 'chapter_packages',
                                        return_value={'ch1-test.md': ['org.example'],
                                                      'ch2-test.md': ['org.example']}):
            outline = self.mod.build_outline()
        self.assertTrue(outline['ownership_conflicts'])

    def test_invalid_inventory_json_is_reported(self):
        path = os.path.join(self.root, 'data', 'state', 'source-inventory.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('{not json')
        with self.assertRaises(SystemExit):
            self.mod.build_outline()

    def test_main_without_an_inventory_returns_two(self):
        path = os.path.join(self.root, 'data', 'state', 'source-inventory.json')
        if os.path.exists(path):
            os.remove(path)
        code, out = _fixture.run_inproc(self.root, 'outline.py')
        self.assertEqual(code, 2, out[-300:])
        self.assertIn('digest.py', out)

    def test_main_writes_the_outline(self):
        self.inventory({'packages': self.packages()})
        code, out = _fixture.run_inproc(self.root, 'outline.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertTrue(os.path.isfile(os.path.join(self.root, 'data', 'state', 'outline.json')))

    def test_json_mode_prints_instead_of_writing(self):
        self.inventory({'packages': self.packages()})
        code, out = _fixture.run_inproc(self.root, 'outline.py', '--json')
        self.assertEqual(code, 0)
        self.assertIn('chapters', json.loads(out[out.index('{'):]))


if __name__ == '__main__':
    unittest.main()
