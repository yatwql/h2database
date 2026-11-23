"""The layout object is the single place density numbers are read and checked."""
from __future__ import annotations

import unittest

import _fixture

TAGS = ('layer:lib', 'tier:fast')

_fixture.ensure_tools_path()

# imported dynamically: the test path is set up above, at runtime
_layout = __import__('lib.layout', fromlist=['DEFAULTS', 'Layout'])
DEFAULTS = _layout.DEFAULTS
Layout = _layout.Layout


class LayoutDefaultsTest(unittest.TestCase):
    def test_an_empty_mapping_yields_the_documented_defaults(self):
        layout, problems = Layout.from_mapping({})
        self.assertEqual(problems, [])
        self.assertEqual(layout.body_px, DEFAULTS['layout_body_px'])
        self.assertEqual(layout.spacing_scale, DEFAULTS['layout_spacing_scale'])

    def test_a_missing_mapping_behaves_like_an_empty_one(self):
        layout, problems = Layout.from_mapping(None)
        self.assertEqual(problems, [])
        self.assertEqual(layout.code_px, DEFAULTS['layout_code_px'])


class LayoutCoercionTest(unittest.TestCase):
    def test_numbers_are_coerced_from_strings(self):
        layout, problems = Layout.from_mapping({'layout_spacing_scale': '0.7'})
        self.assertEqual(problems, [])
        self.assertAlmostEqual(layout.spacing_scale, 0.7)

    def test_an_integer_field_is_rounded_back_to_int(self):
        layout, _problems = Layout.from_mapping({'layout_body_px': '15'})
        self.assertIsInstance(layout.body_px, int)
        self.assertEqual(layout.body_px, 15)

    def test_a_non_numeric_value_keeps_the_default_and_is_reported(self):
        layout, problems = Layout.from_mapping({'layout_body_px': 'big'})
        self.assertEqual(layout.body_px, DEFAULTS['layout_body_px'])
        self.assertTrue(any('layout_body_px' in p for p in problems))

    def test_a_value_outside_the_range_keeps_the_default_and_is_reported(self):
        layout, problems = Layout.from_mapping({'layout_code_px': 99})
        self.assertEqual(layout.code_px, DEFAULTS['layout_code_px'])
        self.assertTrue(any('layout_code_px' in p for p in problems))

    def test_a_blank_string_keeps_the_default(self):
        layout, problems = Layout.from_mapping({'layout_page_margin': '   '})
        self.assertEqual(layout.page_margin, DEFAULTS['layout_page_margin'])
        self.assertTrue(problems)


class LayoutSpacingTest(unittest.TestCase):
    def test_every_gap_is_multiplied_by_the_scale(self):
        layout, _ = Layout.from_mapping({'layout_para_gap_em': 1.0,
                                         'layout_spacing_scale': 0.5})
        self.assertEqual(layout.gap('para_gap_em'), '0.5em')

    def test_the_page_rule_takes_size_and_margin_from_the_config(self):
        layout, _ = Layout.from_mapping({'layout_page_size': 'B5',
                                         'layout_page_margin': '18mm 16mm'})
        css = layout.apply('  @page { size: A4; margin: 24mm 20mm; }')
        self.assertIn('size: B5', css)
        self.assertIn('margin: 18mm 16mm', css)

    def test_describe_lists_every_field_for_the_build_log(self):
        layout, _ = Layout.from_mapping({})
        text = layout.describe()
        self.assertIn('body_px=', text)
        self.assertIn('spacing_scale=', text)


class TypeScaleTest(unittest.TestCase):
    """The shared half is relative; the paged half stays on the page."""

    def setUp(self):
        self.layout = Layout.from_mapping({'layout_body_px': 16,
                                           'layout_epub_code_em': 0.85})[0]

    def test_the_shared_scale_is_expressed_in_em(self):
        scale = self.layout.typescale()
        self.assertEqual(scale.css_substitutions()['font-size: 0.85em;'],
                         'font-size: 0.85em;')
        self.assertTrue(scale.gap('para_gap_em').endswith('em'))

    def test_page_dimensions_are_kept_out_of_the_shared_scale(self):
        self.assertFalse(hasattr(self.layout.typescale(), 'page_size'))
        self.assertEqual(self.layout.geometry().page_size, 'A4')

    def test_spacing_scale_moves_the_gaps_and_nothing_else(self):
        tight = Layout.from_mapping({'layout_spacing_scale': 0.5})[0]
        self.assertEqual(tight.typescale().gap('para_gap_em'), '0.4em')
        self.assertEqual(tight.typescale().heading_em, self.layout.typescale().heading_em)

    def test_the_scale_reaches_the_stylesheet(self):
        css = 'h1 { font-size: 1.6em; }\npre { font-size: 0.85em; }'
        scaled = self.layout.typescale().apply(css)
        self.assertIn('font-size: 1.6em', scaled)
        self.assertIn('font-size: 0.85em', scaled)


if __name__ == '__main__':
    unittest.main()

