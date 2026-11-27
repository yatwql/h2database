#!/usr/bin/env python3
"""Baseline plumbing: path resolution, tolerant loading, save and split."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()


class BaselineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        # the module resolves its paths through the active book, so bind that to
        # the fixture and reload so `lib._baseline` sees the same `lib._config`
        previous_env = os.environ.get('BOOK_ROOT')
        _fixture.refresh_config(self.root)
        if previous_env is None:
            self.addCleanup(os.environ.pop, 'BOOK_ROOT', None)
        else:
            self.addCleanup(os.environ.__setitem__, 'BOOK_ROOT', previous_env)
        self.mod = importlib.reload(importlib.import_module('lib._baseline'))

    def test_a_configured_baseline_wins_over_the_default_name(self):
        path = self.mod.path_for('source_symbol')
        self.assertIn('source-symbol-baseline.json', path.replace('_', '-'))

    def test_an_unconfigured_gate_is_named_after_the_gate(self):
        self.assertTrue(self.mod.path_for('whatever').endswith('whatever.json'))

    def test_the_envelope_says_the_shape_and_falls_back_when_it_does_not(self):
        self.assertEqual(self.mod.kind_of({"kind": "records"}), "records")
        self.assertEqual(self.mod.kind_of({"accepted": []}), "accepted")
        self.assertEqual(self.mod.kind_of({"files": {}}), "counts")
        self.assertEqual(self.mod.kind_of({}), "records")

    def test_saving_stamps_the_envelope(self):
        target = os.path.join(self.tmp.name, "gate.json")
        self.mod.save_at(target, {"accepted": ["a"]}, gate="gate", kind="accepted",
                         keyed_by="path::rule")
        payload = self.mod.load_at(target)
        self.assertEqual(payload["schema"], 1)
        self.assertEqual(payload["gate"], "gate")
        self.assertEqual(payload["kind"], "accepted")
        self.assertEqual(payload["keyed_by"], "path::rule")
        self.assertEqual(payload["accepted"], ["a"])

    def test_a_missing_baseline_loads_as_empty(self):
        self.assertEqual(self.mod.load('whatever'), set())

    def test_a_broken_baseline_does_not_crash_the_gate(self):
        path = self.mod.path_for('whatever')
        # the path is resolved through the active book: if the fixture did not bind,
        # this case would write junk into the repository's own baselines
        self.assertTrue(path.startswith(self.root), path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('{not json')
        self.assertEqual(self.mod.load('whatever'), set())

    def test_save_and_load_round_trip(self):
        self.assertTrue(self.mod.path_for('whatever').startswith(self.root))
        saved = self.mod.save('whatever', {'b', 'a'}, note='reviewed')
        self.assertEqual(self.mod.load('whatever'), {'a', 'b'})
        with open(saved, encoding='utf-8') as fh:
            payload = json.load(fh)
        self.assertEqual(payload['note'], 'reviewed')
        self.assertEqual(payload['accepted'], ['a', 'b'])

    def test_split_separates_new_from_stale(self):
        self.mod.save('whatever', {'old'}, note='x')
        new, stale = self.mod.split('whatever', {'old', 'fresh'})
        self.assertEqual(new, {'fresh'})
        self.assertEqual(stale, set())
        new, stale = self.mod.split('whatever', set())
        self.assertEqual((new, stale), (set(), {'old'}))



class BaselinePayloadTest(unittest.TestCase):
    """A payload may carry more than keys; the review stamp is added, not asked for."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = importlib.reload(importlib.import_module("lib._baseline"))

    def path(self, name: str = "payload.json") -> str:
        return os.path.join(self.tmp.name, name)

    def test_extras_survive_the_round_trip(self):
        path = self.path()
        self.assertEqual(self.mod.load_at(path), {})
        self.mod.save_at(path, {"source_version": "2.5.259", "accepted": ["b", "a"]},
                         note="drift")
        payload = self.mod.load_at(path)
        self.assertEqual(payload["source_version"], "2.5.259")
        self.assertEqual(payload["accepted"], ["b", "a"])   # the gate owns the order
        self.assertEqual(payload["note"], "drift")
        self.assertRegex(payload["updated"], r"^\d{4}-\d{2}-\d{2}$")

    def test_a_payload_without_keys_still_records_its_note(self):
        path = self.path("note.json")
        self.mod.save_at(path, {"steps": {"lint": 0.4}})
        payload = self.mod.load_at(path)
        self.assertEqual(payload["steps"], {"lint": 0.4})
        self.assertIn("accepted", self.mod.DEFAULT_NOTE)

    def test_a_non_object_baseline_reads_as_empty(self):
        path = self.path("list.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("[1, 2]")
        self.assertEqual(self.mod.load_at(path), {})


if __name__ == '__main__':
    unittest.main()
