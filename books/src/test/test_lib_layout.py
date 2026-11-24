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
_layout_typescale = _layout.TypeScale


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


class BodySizeDerivationTest(unittest.TestCase):
    """The body size follows the reading density, not a hard-coded pixel count."""

    def test_an_explicit_size_wins(self):
        layout = Layout.from_mapping({'layout_body_px': 15})[0]
        self.assertEqual(layout.body_size_px(), 15)

    def test_zero_derives_the_size_from_the_column_and_the_line_length(self):
        layout = Layout.from_mapping({'layout_body_px': 0, 'layout_column_px': 800,
                                      'layout_body_chars_per_line': 40})[0]
        self.assertEqual(layout.body_size_px(), 20)

    def test_a_derived_size_stays_inside_the_readable_range(self):
        wide = Layout.from_mapping({'layout_body_px': 0, 'layout_column_px': 1600,
                                    'layout_body_chars_per_line': 20})[0]
        self.assertLessEqual(wide.body_size_px(), 24)
        narrow = Layout.from_mapping({'layout_body_px': 0, 'layout_column_px': 480,
                                      'layout_body_chars_per_line': 80})[0]
        self.assertGreaterEqual(narrow.body_size_px(), 8)

    def test_the_page_leading_comes_from_the_lead_ratio(self):
        layout = Layout.from_mapping({'layout_lead_ratio': 0.4})[0]
        self.assertEqual(layout.body_line_height(), 1.4)

    def test_the_reflowable_leading_is_its_own_value(self):
        # a reader may zoom, so the EPUB keeps a roomier leading than the page
        layout = Layout.from_mapping({'layout_lead_ratio': 0.4,
                                      'layout_epub_line_height': 1.6})[0]
        self.assertEqual(layout.typescale().body_line_height, 1.6)
        self.assertEqual(layout.body_line_height(), 1.4)


class DefaultsIdentityTest(unittest.TestCase):
    """A default layout must derive the default scale: identity, not a second copy.

    Two tables of defaults drift apart silently. Asserting that the derived object
    equals the dataclass's own defaults turns any second copy into a failing test
    instead of a slow divergence nobody notices.
    """

    def test_the_default_layout_derives_the_default_scale(self):
        self.assertEqual(_layout_typescale.from_layout(Layout()), _layout_typescale())

    def test_the_default_layout_derives_the_default_geometry(self):
        geometry = Layout().geometry()
        self.assertEqual(geometry.page_size, DEFAULTS['layout_page_size'])
        self.assertEqual(geometry.body_px, Layout().body_size_px())
        self.assertEqual(geometry.code_px, DEFAULTS['layout_code_px'])

    def test_the_scale_and_geometry_do_not_share_paged_fields(self):
        self.assertFalse(hasattr(_layout_typescale(), 'page_size'))
        self.assertFalse(hasattr(Layout().geometry(), 'heading_em'))


if __name__ == '__main__':
    unittest.main()

