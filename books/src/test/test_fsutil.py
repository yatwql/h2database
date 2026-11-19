#!/usr/bin/env python3
"""Tests for books/tools/_fsutil.py (filesystem helpers with clean exits)."""
import importlib
import os
import sys
import tempfile
import unittest

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

_fsutil = importlib.import_module('lib._fsutil')


class TestReadHelpers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, 'sample.md')

    def test_write_then_read_text(self):
        _fsutil.write_text(self.path, '第一章\n正文\n')
        self.assertEqual(_fsutil.read_text(self.path), '第一章\n正文\n')

    def test_read_lines_keeps_newlines(self):
        _fsutil.write_text(self.path, 'a\nb\n')
        self.assertEqual(_fsutil.read_lines(self.path), ['a\n', 'b\n'])

    def test_read_text_missing_file_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            _fsutil.read_text(os.path.join(self.tmp.name, 'nope.md'))
        self.assertIn('cannot read', str(ctx.exception.code))

    def test_read_lines_missing_file_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            _fsutil.read_lines(os.path.join(self.tmp.name, 'nope.md'))
        self.assertIn('cannot read', str(ctx.exception.code))

    def test_write_text_utf8_roundtrip(self):
        _fsutil.write_text(self.path, '图 A-1：测试')
        with open(self.path, 'rb') as fh:
            self.assertIn('图 A-1'.encode(), fh.read())


class TestJsonHelpers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, 'data.json')

    def test_dump_then_load(self):
        payload = {'count': 1, 'term': '页面分裂'}
        _fsutil.dump_json(self.path, payload)
        self.assertEqual(_fsutil.load_json(self.path), payload)

    def test_dump_json_writes_trailing_newline(self):
        _fsutil.dump_json(self.path, {'a': 1})
        self.assertTrue(_fsutil.read_text(self.path).endswith('\n'))

    def test_dump_json_keeps_unicode(self):
        _fsutil.dump_json(self.path, {'term': '页面分裂'})
        self.assertIn('页面分裂', _fsutil.read_text(self.path))

    def test_invalid_json_exits(self):
        _fsutil.write_text(self.path, '{oops')
        with self.assertRaises(SystemExit) as ctx:
            _fsutil.load_json(self.path)
        self.assertIn('invalid JSON', str(ctx.exception.code))

    def test_load_json_missing_file_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            _fsutil.load_json(os.path.join(self.tmp.name, 'nope.json'))
        self.assertIn('cannot read', str(ctx.exception.code))


class TestEnsureDir(unittest.TestCase):
    def test_creates_nested_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, 'a', 'b', 'out.pdf')
            _fsutil.ensure_dir(target)
            self.assertTrue(os.path.isdir(os.path.dirname(target)))

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, 'out.pdf')
            _fsutil.ensure_dir(target)
            _fsutil.ensure_dir(target)
            self.assertTrue(os.path.isdir(tmp))


if __name__ == '__main__':
    unittest.main()
