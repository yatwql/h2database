"""Font resolution judges files by their content and stacks by script."""
from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()

_fonts = __import__('lib.fonts', fromlist=['is_collection_file', 'script_stack'])
is_collection_file = _fonts.is_collection_file
script_stack = _fonts.script_stack


class CollectionDetectionTest(unittest.TestCase):
    def test_a_collection_header_is_recognised(self):
        with tempfile.NamedTemporaryFile(suffix='.otf', delete=False) as handle:
            handle.write(b'ttcf' + b'\x00' * 8)
            path = handle.name
        self.addCleanup(os.remove, path)
        # an .otf name would suggest a single face; the header says otherwise
        self.assertTrue(is_collection_file(path))

    def test_a_single_face_header_is_not_a_collection(self):
        with tempfile.NamedTemporaryFile(suffix='.ttc', delete=False) as handle:
            handle.write(b'OTTO' + b'\x00' * 8)
            path = handle.name
        self.addCleanup(os.remove, path)
        self.assertFalse(is_collection_file(path))

    def test_a_missing_file_is_not_a_collection(self):
        self.assertFalse(is_collection_file(os.path.join(tempfile.gettempdir(),
                                                         'no-such-font.ttf')))


class ScriptStackTest(unittest.TestCase):
    def test_cjk_families_are_appended_after_the_latin_ones(self):
        stack = script_stack(['DejaVu Sans'], ['Droid Sans Fallback'])
        self.assertLess(stack.index('DejaVu Sans'), stack.index('Droid Sans Fallback'))
        self.assertTrue(stack.endswith('sans-serif'))

    def test_a_family_listed_twice_appears_once(self):
        stack = script_stack(['DejaVu Sans'], ['DejaVu Sans', 'Droid Sans Fallback'])
        self.assertEqual(stack.count('DejaVu Sans'), 1)

    def test_multiple_families_are_quoted(self):
        stack = script_stack(['DejaVu Sans'], None)
        self.assertIn('"DejaVu Sans"', stack)


if __name__ == '__main__':
    unittest.main()
