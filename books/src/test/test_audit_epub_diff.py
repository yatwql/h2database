"""The EPUB comparison reads its numbers out of the container, and judging is separate."""
from __future__ import annotations

import os
import tempfile
import unittest
import zipfile

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

_epub_diff = __import__('audit.epub_diff', fromlist=['check', 'compare', 'measure'])
measure = _epub_diff.measure
compare = _epub_diff.compare
check = _epub_diff.check

CSS = ('body { font-family: "Source Han Serif", serif; font-size: 1em; '
       'line-height: 1.55; }')


def build(directory: str, name: str, chapters: int, css: str = CSS) -> str:
    """A minimal EPUB-shaped zip: CSS plus one XHTML file per chapter."""
    path = os.path.join(directory, name)
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('EPUB/styles/stylesheet1.css', css)
        for index in range(1, chapters + 1):
            archive.writestr(f'EPUB/text/ch{index:03d}.xhtml',
                             f'<html><body><p>{"字" * 10}</p></body></html>')
    return path


class MeasureTest(unittest.TestCase):
    def test_chapters_and_characters_are_counted_from_the_container(self):
        with tempfile.TemporaryDirectory() as directory:
            stats = measure(build(directory, 'b.epub', 3))
        self.assertEqual(stats['chapters'], 3)
        self.assertEqual(stats['chars'], 30)

    def test_css_rules_are_surfaced_for_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            stats = measure(build(directory, 'b.epub', 1))
        self.assertEqual(stats['sizes'], ['1em'])
        self.assertEqual(stats['leads'], ['1.55'])
        self.assertEqual(stats['fonts'], ['"Source Han Serif", serif'])


class CompareTest(unittest.TestCase):
    def test_identical_builds_report_no_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            left = build(directory, 'a.epub', 2)
            right = build(directory, 'b.epub', 2)
            self.assertEqual(compare(left, right), 0)

    def test_a_changed_font_size_is_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            left = build(directory, 'a.epub', 1)
            right = build(directory, 'b.epub', 1, css='body { font-size: 1.1em; }')
            self.assertEqual(compare(left, right), 1)


class CheckTest(unittest.TestCase):
    def test_cover_plus_one_file_per_heading_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            epub = build(directory, 'b.epub', 3)
            merged = os.path.join(directory, 'merged.md')
            with open(merged, 'w', encoding='utf-8') as handle:
                handle.write('# one\n\n# two\n')
            self.assertEqual(check(epub, merged), 0)

    def test_a_missing_chapter_file_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            epub = build(directory, 'b.epub', 2)
            merged = os.path.join(directory, 'merged.md')
            with open(merged, 'w', encoding='utf-8') as handle:
                handle.write('# one\n\n# two\n\n# three\n')
            self.assertEqual(check(epub, merged), 1)

    def test_an_unreadable_merged_file_fails_without_raising(self):
        with tempfile.TemporaryDirectory() as directory:
            epub = build(directory, 'b.epub', 1)
            self.assertEqual(check(epub, os.path.join(directory, 'missing.md')), 1)


if __name__ == '__main__':
    unittest.main()
