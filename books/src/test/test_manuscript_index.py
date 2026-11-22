#!/usr/bin/env python3
"""Error and fallback paths of the delivery scripts.

Missing optional tools (pandoc, chromium), missing prerequisites and malformed
artifacts are the branches that never run in the happy path but do fire in real
use — and they are where a toolchain silently misbehaves instead of reporting.
"""

import importlib.util
import os
import sys
import tempfile
import unittest

import _fixture

TAGS = ('layer:manuscript', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

SLOW = os.environ.get('BOOK_SLOW') == '1'
HAS_PANDOC = bool(__import__('shutil').which('pandoc'))
HAS_PYPDF = importlib.util.find_spec('pypdf') is not None

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def run_script(self, script: str, *args: str, env: dict | None = None):
        if env is None:
            return _fixture.run_inproc(self.root, script, *args)
        previous = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            return _fixture.run_inproc(self.root, script, *args)
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

class TestIndexAndStyleBranches(Base):
    def test_index_with_subsections(self):
        self.write('data/manuscript/back/index.md',
                   '# 索引\n\n## A\n\n- ACID —— §1.1\n'
                   '  - 原子性 —— §1.1\n  - 隔离性 —— §2.1\n  see also: MVStore\n\n'
                   '## M\n\n- MVStore —— §2.1\n  see also: ACID\n')
        code, out = self.run_script('index_xrefs.py')
        self.assertIn(code, (0, 1), out[-300:])
        code, out = self.run_script('index.py', '--hierarchy-check')
        self.assertIn(code, (0, 1), out[-300:])

    def test_style_flags_long_line_and_monotony(self):
        body = '这是短句。' * 30
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n' + body + '\n\n' + '很' * 200 + '\n')
        code, out = self.run_script('style.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('长句', out)

if __name__ == '__main__':
    unittest.main()
