"""A second book is a configuration and a manuscript — no code change.

This builds a throwaway book from the repository's own scaffolding plus two short
chapters, then runs the real renderers against it. If any path, font stack, or
chapter split depended on this particular book, this test would fail while the
first book kept working.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile

import _fixture

TAGS = ('layer:render', 'tier:slow')

_fixture.ensure_tools_path()

BOOKS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO_BOOK = BOOKS
PYTHON = os.path.join(REPO_BOOK, '.venv', 'bin', 'python') if os.path.exists(
    os.path.join(REPO_BOOK, '.venv', 'bin', 'python')) else 'python3'

CHAPTER_ONE = """# 第一章 起头

这是一个只有两百来个字的小书，用来证明换一本书不需要改代码。

## 1.1 小节

正文若干行，足够让排版引擎产生一页。

**图 1-1: 一个文本图**
============================================================

```
┌──────┐
│ 方块 │
└──────┘
```
"""

CHAPTER_TWO = """# 第二章 收尾

## 2.1 小节

第二章的内容同样短小，但足以成为一个独立文件。
"""


def _scaffold(root: str) -> None:
    """Copy the repository's own config skeleton, then replace the manuscript."""
    for relative in ('data/config', 'data/book', 'data/language'):
        shutil.copytree(os.path.join(BOOKS, relative), os.path.join(root, relative))
    manuscript = os.path.join(root, 'data', 'manuscript')
    os.makedirs(manuscript)
    shutil.copy(os.path.join(BOOKS, 'data', 'manuscript', 'cover.md'),
                os.path.join(manuscript, 'cover.md'))
    # the reading order is configuration: point it at this book's two chapters
    book = os.path.join(root, 'data', 'book', 'book.toml')
    with open(book, encoding='utf-8') as handle:
        text = handle.read()
    # the reading order is a plain list of files: replace the list wholesale
    block = re.search(r'\[chapters\](.*?)(?=\n\[)', text, re.S)
    if block:
        body = block.group(1)
        replaced = re.sub(r'files\s*=\s*\[[^\]]*\]',
                          'files = [\n    "cover.md",\n    "ch1.md",\n    "ch2.md",\n]',
                          body, count=1, flags=re.S)
        text = text[:block.start(1)] + replaced + text[block.end(1):]
    with open(book, 'w', encoding='utf-8') as handle:
        handle.write(text)
    with open(os.path.join(manuscript, 'ch1.md'), 'w', encoding='utf-8') as handle:
        handle.write(CHAPTER_ONE)
    with open(os.path.join(manuscript, 'ch2.md'), 'w', encoding='utf-8') as handle:
        handle.write(CHAPTER_TWO)


def _run(root: str, script: str) -> subprocess.CompletedProcess:
    """Merge the manuscript first: both renderers consume the merged markdown."""
    env = dict(os.environ, BOOK_ROOT=root)
    merged = subprocess.run([PYTHON, os.path.join(BOOKS, 'src', 'python', 'render', 'merge.py')],
                            cwd=root, env=env, capture_output=True, text=True, timeout=600)
    if merged.returncode != 0:
        return merged
    return subprocess.run([PYTHON, os.path.join(BOOKS, 'src', 'python', script)],
                          cwd=root, env=env, capture_output=True, text=True, timeout=600)


class SecondBookTest(unittest.TestCase):
    def test_the_epub_builds_for_a_different_book(self):
        with tempfile.TemporaryDirectory() as root:
            _scaffold(root)
            result = _run(root, 'render/to_epub.py')
            self.assertEqual(result.returncode, 0, result.stderr[-800:])
            epub = os.path.join(root, 'dist', 'h2-source-code-analysis.epub')
            self.assertTrue(os.path.exists(epub))
            with zipfile.ZipFile(epub) as archive:
                bodies = sorted(n for n in archive.namelist()
                                if '/ch' in n and n.endswith('.xhtml'))
                text = ''.join(archive.read(n).decode('utf-8', 'ignore') for n in bodies)
            # cover + title page + the two chapters; the caption's underline must
            # not add a file of its own, which is what this count pins
            self.assertIn('第一章 起头', text)
            self.assertIn('第二章 收尾', text)
            self.assertEqual(len(bodies), 4, bodies)

    def test_the_pdf_builds_for_a_different_book(self):
        with tempfile.TemporaryDirectory() as root:
            _scaffold(root)
            result = _run(root, 'render/to_pdf.py')
            self.assertEqual(result.returncode, 0, result.stderr[-800:])
            pdf = os.path.join(root, 'dist', 'h2-source-code-analysis.pdf')
            self.assertTrue(os.path.exists(pdf))
            from pypdf import PdfReader
            self.assertGreater(len(PdfReader(pdf).pages), 0)


if __name__ == '__main__':
    unittest.main()
