"""Measurement, comparison and calibration are arithmetic: test them without a book.

The CLI only renders what these functions compute, so a page count that moves for the
wrong reason should fail here rather than in a calibration run that costs minutes.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:render', 'tier:fast')

_fixture.ensure_tools_path()

_metrics = __import__('render.pdf_metrics',
                      fromlist=['describe', 'compare', 'Calibration', 'calibrate',
                                'compare_targets', 'parse_targets', 'write_back', 'main'])


def measured(**overrides) -> dict:
    """One measurement record, with the numbers a caller would read."""
    base = {'path': '/tmp/book.pdf', 'pages': 900, 'mb': 7.5, 'chars_per_page': 1900,
            'body_pt': 6.8, 'heading_pt': 21.6, 'body_share': 74, 'lines_per_page': 50,
            'pitch_pt': 8.2, 'text_width_pt': 540.0}
    base.update(overrides)
    return base


class DescribeTest(unittest.TestCase):
    def test_every_number_reaches_the_line(self):
        text = _metrics.describe(measured())
        for token in ('book.pdf', '900', '7.50 MB', '6.8pt', '74%', '21.6pt', '8.2pt',
                      '50', '540.0pt', '1900'):
            self.assertIn(token, text)

    def test_a_long_filename_is_clipped_to_the_column(self):
        text = _metrics.describe(measured(path='/tmp/' + 'x' * 60 + '.pdf'))
        self.assertLessEqual(len(text.split()[0]), 34)


class CompareTest(unittest.TestCase):
    def test_a_metric_inside_the_tolerance_carries_no_flag(self):
        text = _metrics.compare(measured(), measured(pages=910))
        self.assertNotIn('←', text)

    def test_a_larger_metric_is_flagged_as_large(self):
        text = _metrics.compare(measured(), measured(pages=1200))
        self.assertIn('偏大', text)

    def test_a_smaller_metric_is_flagged_as_small(self):
        text = _metrics.compare(measured(), measured(pages=600))
        self.assertIn('偏小', text)

    def test_a_zero_reference_reports_no_delta_instead_of_dividing(self):
        text = _metrics.compare(measured(body_pt=0), measured(body_pt=7))
        self.assertIn('+0.0%', text)


class TargetsTest(unittest.TestCase):
    def test_a_target_spec_parses_to_numbers(self):
        self.assertEqual(_metrics.parse_targets('pages=843,chars_per_page=1905'),
                         {'pages': 843.0, 'chars_per_page': 1905.0})

    def test_blank_parts_and_spaces_are_ignored(self):
        self.assertEqual(_metrics.parse_targets(' pages = 12 ,, mb=7.5 '),
                         {'pages': 12.0, 'mb': 7.5})

    def test_an_unknown_metric_is_named(self):
        self.assertIn('未知指标', _metrics.compare_targets(measured(), {'nope': 1}))

    def test_a_target_is_compared_and_flagged(self):
        text = _metrics.compare_targets(measured(), {'pages': 500})
        self.assertIn('偏大', text)
        text = _metrics.compare_targets(measured(), {'pages': 900})
        self.assertNotIn('←', text)


class CalibrationTest(unittest.TestCase):
    def test_the_first_suggestion_is_the_midpoint(self):
        search = _metrics.Calibration(target=100, low=0.5, high=1.5)
        self.assertEqual(search.suggest(), 1.0)

    def test_a_low_measurement_raises_the_lower_bound(self):
        search = _metrics.Calibration(target=100, low=0.5, high=1.5)
        search.record(0.8, 80)
        self.assertEqual(search.low, 0.8)

    def test_a_high_measurement_lowers_the_upper_bound(self):
        search = _metrics.Calibration(target=100, low=0.5, high=1.5)
        search.record(1.2, 130)
        self.assertEqual(search.high, 1.2)

    def test_landing_within_the_tolerance_converges_and_stops(self):
        search = _metrics.Calibration(target=100, low=0.5, high=1.5, tolerance=4)
        search.record(1.0, 102)
        self.assertTrue(search.converged)
        self.assertIsNone(search.suggest())

    def test_a_collapsed_interval_stops_without_converging(self):
        search = _metrics.Calibration(target=100, low=1.0, high=1.001)
        self.assertFalse(search.converged)
        self.assertIsNone(search.suggest())

    def test_the_report_names_the_bounds_and_the_verdict(self):
        search = _metrics.Calibration(target=100, low=0.5, high=1.5)
        search.record(1.0, 130)
        text = search.report()
        self.assertIn('目标 100 页', text)
        self.assertIn('未收敛', text)
        self.assertIn('scale=1.000', text)


class CalibrateTest(unittest.TestCase):
    def test_a_render_that_lands_on_target_returns_its_scale(self):
        pages = iter([80, 130, 99, 100])

        def render(scale: float) -> str:
            return f'/tmp/{scale}.pdf'

        with mock.patch.object(_metrics, 'measure',
                               side_effect=lambda path: {'pages': next(pages)}):
            search, hit = _metrics.calibrate(render, target=100, low=0.5, high=1.5)
        self.assertIsNotNone(hit)
        self.assertTrue(search.converged)

    def test_a_search_that_never_lands_returns_none(self):
        with mock.patch.object(_metrics, 'measure', return_value={'pages': 10}):
            search, hit = _metrics.calibrate(lambda scale: '/tmp/x.pdf', target=900,
                                             low=0.5, high=1.5, max_rounds=2)
        self.assertIsNone(hit)
        self.assertEqual(len(search.history), 2)


class WriteBackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, 'base.json')
        with open(self.path, 'w', encoding='utf-8') as handle:
            json.dump({'toolchain': {'print_scale': 0.667, 'pdf_max_mb': 12}}, handle)

    def read(self) -> dict:
        with open(self.path, encoding='utf-8') as handle:
            return json.load(handle)

    def test_the_value_is_replaced_and_the_rest_untouched(self):
        _metrics.write_back(self.path, 'print_scale', 0.71)
        payload = self.read()
        self.assertEqual(payload['toolchain']['print_scale'], 0.71)
        self.assertEqual(payload['toolchain']['pdf_max_mb'], 12)

    def test_a_missing_key_is_refused(self):
        with self.assertRaises(SystemExit):
            _metrics.write_back(self.path, 'nope', 1)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = os.path.join(self.tmp.name, 'book.pdf')
        from pypdf import PdfWriter
        writer = PdfWriter()
        for _ in range(2):
            writer.add_blank_page(width=595, height=842)
        with open(self.pdf, 'wb') as handle:
            writer.write(handle)

    def run_cli(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = _metrics.main(['pdf_metrics.py', *argv])
        return code, buffer.getvalue()

    def test_no_arguments_prints_the_usage_and_returns_two(self):
        code, out = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn('Usage', out + _metrics.__doc__)

    def test_a_measurement_is_printed_for_one_pdf(self):
        code, out = self.run_cli(self.pdf)
        self.assertEqual(code, 0)
        self.assertIn('book.pdf', out)

    def test_compare_needs_two_pdfs(self):
        code, out = self.run_cli('--compare', self.pdf)
        self.assertEqual(code, 2)
        self.assertIn('两个', out)

    def test_compare_prints_both_measurements(self):
        code, out = self.run_cli('--compare', self.pdf, self.pdf)
        self.assertEqual(code, 0)
        self.assertEqual(out.count('book.pdf'), 2)

    def test_a_target_compares_one_pdf_with_numbers(self):
        code, out = self.run_cli('--target', 'pages=2', self.pdf)
        self.assertEqual(code, 0)
        self.assertIn('pages', out)


if __name__ == '__main__':
    unittest.main()
