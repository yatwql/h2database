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


class PrintColumnTest(unittest.TestCase):
    """The printed column is measured against the sheet, not chosen by hand."""

    def test_the_column_is_the_reading_measure_times_the_body_size(self):
        layout = Layout.from_mapping({'layout_page_size': 'A4',
                                      'layout_body_px': 16,
                                      'layout_print_chars_per_line': 42})[0]
        self.assertEqual(layout.print_column(), 42 * 16)

    def test_the_margin_is_what_the_column_leaves(self):
        layout = Layout.from_mapping({'layout_page_size': 'A4',
                                      'layout_body_px': 16,
                                      'layout_print_chars_per_line': 42,
                                      'layout_page_margin': '24mm 20mm'})[0]
        _vertical, horizontal = layout.print_margins_mm()
        # 210mm - 42 x 16px / 96dpi = 210 - 177.8 = 32.2mm, so 16.1mm each side
        self.assertAlmostEqual(horizontal, 16.1, delta=0.1)
        self.assertAlmostEqual(layout.printable_width_px(), 672, delta=1)
        self.assertAlmostEqual(layout.printable_width_pt(), 504, delta=1)

    def test_a_narrower_measure_widens_the_margins(self):
        layout = Layout.from_mapping({'layout_page_size': 'A4',
                                      'layout_body_px': 16,
                                      'layout_print_chars_per_line': 30})[0]
        self.assertEqual(layout.print_column(), 480)
        self.assertAlmostEqual(layout.print_margins_mm()[1], (210 - 127) / 2, delta=0.1)

    def test_a_measure_wider_than_the_floor_shrinks_to_the_floor(self):
        layout = Layout.from_mapping({'layout_page_size': 'A4',
                                      'layout_body_px': 16,
                                      'layout_print_chars_per_line': 60,
                                      'layout_print_margin_min_mm': 16})[0]
        # 60 x 16 = 960px does not fit A4 at 16mm margins, so the column gives way
        self.assertLess(layout.print_column(), 960)
        self.assertEqual(layout.print_margins_mm()[1], 16.0)
        self.assertLessEqual(layout.print_column(), layout.printable_width_px() + 1)

    def test_an_explicit_column_overrides_the_measure(self):
        layout = Layout.from_mapping({'layout_print_column_px': 720})[0]
        self.assertEqual(layout.print_column(), 720)

    def test_the_page_margin_names_what_the_column_leaves(self):
        layout = Layout.from_mapping({'layout_page_size': 'A4',
                                      'layout_body_px': 16,
                                      'layout_print_chars_per_line': 42})[0]
        self.assertEqual(layout.print_page_margin(), '24.0mm 16.1mm')

    def test_the_vertical_margin_is_the_configured_one(self):
        layout = Layout.from_mapping({'layout_page_margin': '30mm 20mm'})[0]
        self.assertEqual(layout.print_margins_mm()[0], 30.0)

    def test_four_configured_margins_still_only_lend_the_vertical_one(self):
        layout = Layout.from_mapping({'layout_page_margin': '10mm 12mm 14mm 16mm'})[0]
        self.assertEqual(layout.margins_mm(), (16.0, 12.0))
        self.assertEqual(layout.print_margins_mm()[0], 10.0)

    def test_a_named_size_or_an_explicit_one_both_resolve(self):
        self.assertEqual(Layout.from_mapping({'layout_page_size': 'B5'})[0].page_size_mm(),
                         (176.0, 250.0))
        explicit = Layout.from_mapping({'layout_page_size': '200mmx300mm'})[0]
        self.assertEqual(explicit.page_size_mm(), (200.0, 300.0))

    def test_an_unknown_size_falls_back_to_a4(self):
        self.assertEqual(Layout.from_mapping({'layout_page_size': 'tabloid-ish'})[0]
                         .page_size_mm(), (210.0, 297.0))

    def test_a_broken_margin_does_not_break_the_fit(self):
        layout = Layout.from_mapping({'layout_page_margin': 'wide'})[0]
        self.assertEqual(layout.margins_mm(), (0.0, 0.0))
        self.assertGreater(layout.printable_width_px(), 0)

    def test_the_column_is_derived_unless_configured(self):
        derived = Layout.from_mapping({'layout_page_size': 'A4'})[0]
        self.assertEqual(derived.print_column(),
                         derived.print_chars_per_line * derived.body_size_px())

    def test_the_code_size_shrinks_until_the_widest_line_fits(self):
        layout = Layout.from_mapping({'layout_page_size': 'A4',
                                      'layout_page_margin': '24mm 20mm',
                                      'layout_code_px': 10})[0]
        # 100 columns at the screen size need 600px and the sheet has 642px
        self.assertEqual(layout.print_code_px(100), 10)
        # a long line cannot fit at the screen size, so the type follows it down
        narrow = layout.print_code_px(150)
        self.assertLess(narrow, 10)
        self.assertLessEqual(150 * layout.print_mono_advance * narrow,
                             layout.printable_width_px() + 1.0)

    def test_the_code_size_never_drops_below_the_readable_floor(self):
        layout = Layout.from_mapping({'layout_print_code_min_px': 8})[0]
        self.assertEqual(layout.print_code_px(400), 8.0)

    def test_below_the_floor_the_column_wraps_instead(self):
        layout = Layout.from_mapping({'layout_print_code_min_px': 8})[0]
        self.assertTrue(layout.print_wraps(400))
        self.assertFalse(Layout().print_wraps(100))

    def test_the_wrap_knob_forces_wrapping(self):
        layout = Layout.from_mapping({'layout_print_wrap': 1})[0]
        self.assertTrue(layout.print_wraps(10))


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

