"""Font resolution judges files by their content and stacks by script."""
from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()

_fonts = __import__('lib.fonts', fromlist=['is_collection_file', 'portable_stack'])
is_collection_file = _fonts.is_collection_file
portable_stack = _fonts.portable_stack


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


class PortableStackTest(unittest.TestCase):
    """A viewer-side stack must describe the reader's device, not this machine."""

    def test_the_latin_face_comes_before_the_cjk_one(self):
        stack = portable_stack('mono')
        self.assertLess(stack.index('Consolas'), stack.index('Source Han Mono'))

    def test_the_roles_end_in_their_generic_family(self):
        self.assertTrue(portable_stack('serif').endswith('serif'))
        self.assertTrue(portable_stack('mono').endswith('monospace'))
        self.assertTrue(portable_stack('sans').endswith('sans-serif'))

    def test_an_unknown_role_falls_back_to_sans(self):
        self.assertEqual(portable_stack('nonsense'), portable_stack('sans'))

    def test_families_with_spaces_are_quoted(self):
        self.assertIn('"Source Han Serif"', portable_stack('serif'))


if __name__ == '__main__':
    unittest.main()
