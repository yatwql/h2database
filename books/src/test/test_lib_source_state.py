#!/usr/bin/env python3
"""Source-change reporting: did the analyzed tree move, and what moved in it."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:lib", "tier:fast")

_fixture.ensure_tools_path()


def inventory(packages: dict, lines: int, files: int) -> dict:
    return {'totals': {'packages': len(packages), 'files': files, 'lines': lines},
            'packages': {name: {'lines': lines // max(1, len(packages)), 'files': 1}
                         for name in packages}}


class DiffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.state = _fixture.load_module(self.root, "_source_state")

    def test_packages_that_appeared_and_went_are_named(self):
        old = inventory({'a': 1, 'b': 1}, 100, 2)
        new = inventory({'b': 1, 'c': 1}, 120, 2)
        moved = self.state.diff(old, new)
        self.assertEqual(moved['added'], ['c'])
        self.assertEqual(moved['removed'], ['a'])
        self.assertEqual((moved['packages'], moved['files'], moved['lines']), (0, 0, 20))

    def test_the_summary_says_how_much_moved(self):
        moved = self.state.diff(inventory({'a': 1}, 100, 1), inventory({'a': 1}, 90, 1))
        text = self.state.summary(moved)
        self.assertIn('包 0', text)
        self.assertIn('行 -10', text)

    def test_a_long_list_of_removed_packages_is_abbreviated(self):
        old = inventory({name: 1 for name in 'abcd'}, 40, 4)
        new = inventory({}, 0, 0)
        text = self.state.summary(self.state.diff(old, new))
        self.assertIn('移除包 a, b, c 等 4 个', text)

    def test_an_inventory_that_cannot_be_read_loads_as_empty(self):
        broken = os.path.join(self.tmp.name, 'broken.json')
        with open(broken, 'w', encoding='utf-8') as handle:
            handle.write('{not json')
        self.assertEqual(self.state.load(broken), {})
        self.assertEqual(self.state.load(os.path.join(self.tmp.name, 'absent.json')), {})

    def test_a_long_list_of_new_packages_is_abbreviated(self):
        old = inventory({}, 0, 0)
        new = inventory({name: 1 for name in 'abcd'}, 40, 4)
        text = self.state.summary(self.state.diff(old, new))
        self.assertIn('等 4 个', text)


class ChangeLineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.state = _fixture.load_module(self.root, "_source_state")
        self.current = self.state.inventory_path()
        self.previous = self.state.inventory_path(previous=True)
        os.makedirs(os.path.dirname(self.current), exist_ok=True)

    def write(self, path: str, payload: dict) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

    def test_the_first_run_has_nothing_to_compare_with(self):
        line, changed = self.state.change_line(self.current, self.previous)
        self.assertIn("首次 ingest", line)
        self.assertTrue(changed)

    def test_an_identical_inventory_reads_as_unchanged(self):
        self.write(self.previous, inventory({'a': 1}, 10, 1))
        self.write(self.current, inventory({'a': 1}, 10, 1))
        line, changed = self.state.change_line(self.current, self.previous)
        self.assertIn("与上次一致", line)
        self.assertFalse(changed)

    def test_a_moved_tree_reports_what_moved_and_when(self):
        self.write(self.previous, inventory({'a': 1}, 10, 1))
        self.write(self.current, inventory({'a': 1, 'b': 1}, 40, 2))
        line, changed = self.state.change_line(self.current, self.previous)
        self.assertTrue(changed)
        self.assertIn("已变化", line)
        self.assertIn("b", line)
        self.assertIn("上次分析", line)

    def test_an_unreadable_previous_record_counts_as_changed(self):
        self.write(self.current, inventory({'a': 1}, 10, 1))
        self.write(self.previous, inventory({'a': 1}, 10, 1))
        real = self.state._fsutil.read_text

        def read(path):
            if path == self.previous:
                raise OSError("denied")
            return real(path)

        with mock.patch.object(self.state._fsutil, "read_text", side_effect=read):
            line, changed = self.state.change_line(self.current, self.previous)
        self.assertTrue(changed)
        self.assertIn("不可读", line)


if __name__ == "__main__":
    unittest.main()
