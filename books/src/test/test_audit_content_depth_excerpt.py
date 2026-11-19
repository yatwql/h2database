#!/usr/bin/env python3
"""Content depth: code excerpts must still match the source they cite."""
from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

_fixture.ensure_tools_path()


class ExcerptFreshnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.depth = _fixture.load_module(self.root, 'content_depth')
        self.source_root = os.path.join(self.root, 'h2', 'src', 'main')
        os.makedirs(os.path.join(self.source_root, 'org', 'example'), exist_ok=True)
        self.chapter = os.path.join(self.root, 'data', 'manuscript', 'ch1-test.md')

    def write_source(self, rel: str, body: str) -> None:
        path = os.path.join(self.source_root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(body)

    def append(self, text: str) -> None:
        with open(self.chapter, encoding='utf-8') as fh:
            body = fh.read()
        with open(self.chapter, 'w', encoding='utf-8') as fh:
            fh.write(body + '\n' + text + '\n')

    def check(self) -> list[dict]:
        self.depth._config.source_tree = lambda _key: self.source_root
        return self.depth.check_excerpts([self.chapter])

    def test_matching_excerpt_is_accepted(self):
        self.write_source('org/example/Widget.java',
                          'class Widget {\n    void run() {}\n}\n')
        self.append('// Widget.java:2\n```java\nvoid run() {}\n```')
        self.assertEqual(self.check(), [])

    def test_drifted_excerpt_is_reported(self):
        self.write_source('org/example/Widget.java',
                          'class Widget {\n    void stop() {}\n}\n')
        self.append('// Widget.java:2\n```java\nvoid run() {}\n```')
        findings = self.check()
        self.assertTrue(findings)
        self.assertIn('drifted', findings[0]['detail'])

    def test_missing_source_file_is_reported(self):
        self.append('// Ghost.java:1\n```java\nvoid x() {}\n```')
        findings = self.check()
        self.assertTrue(findings)
        self.assertIn('not found', findings[0]['detail'])

    def test_basename_match_finds_the_file_in_another_package(self):
        self.write_source('org/other/Widget.java', 'class Widget {\n    void run() {}\n}\n')
        self.append('// Widget.java:2\n```java\nvoid run() {}\n```')
        self.assertEqual(self.check(), [])

    def test_excerpt_without_a_header_is_ignored(self):
        self.append('```java\nvoid run() {}\n```')
        self.assertEqual(self.check(), [])


if __name__ == '__main__':
    unittest.main()
