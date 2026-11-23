"""Comparing against numbers, and the arithmetic of a bounded calibration."""
from __future__ import annotations

import unittest

import _fixture

TAGS = ('layer:render', 'tier:fast')

_fixture.ensure_tools_path()

_metrics = __import__('render.pdf_metrics',
                      fromlist=['Calibration', 'compare_targets', 'parse_targets'])
Calibration = _metrics.Calibration
compare_targets = _metrics.compare_targets
parse_targets = _metrics.parse_targets


class ParseTargetsTest(unittest.TestCase):
    def test_a_spec_becomes_numbers(self):
        self.assertEqual(parse_targets('pages=843,chars_per_page=1905'),
                         {'pages': 843.0, 'chars_per_page': 1905.0})

    def test_empty_entries_are_ignored(self):
        self.assertEqual(parse_targets('pages=843,,'), {'pages': 843.0})


class CompareTargetsTest(unittest.TestCase):
    def test_within_three_percent_is_not_flagged(self):
        text = compare_targets({'pages': 862}, {'pages': 843})
        self.assertNotIn('偏', text)

    def test_beyond_three_percent_is_flagged_the_right_way(self):
        self.assertIn('偏大', compare_targets({'pages': 900}, {'pages': 843}))
        self.assertIn('偏小', compare_targets({'pages': 700}, {'pages': 843}))

    def test_an_unknown_metric_is_reported_not_crashed(self):
        self.assertIn('未知指标', compare_targets({'pages': 1}, {'nope': 2}))


class CalibrationTest(unittest.TestCase):
    def test_the_first_suggestion_is_the_midpoint(self):
        cal = Calibration(target=843, low=0.5, high=1.0)
        self.assertEqual(cal.suggest(), 0.75)

    def test_too_many_pages_lowers_the_upper_bound(self):
        cal = Calibration(target=843, low=0.5, high=1.0)
        cal.record(0.75, 900)
        self.assertEqual(cal.high, 0.75)
        self.assertLess(cal.suggest(), 0.75)

    def test_too_few_pages_raises_the_lower_bound(self):
        cal = Calibration(target=843, low=0.5, high=1.0)
        cal.record(0.75, 800)
        self.assertEqual(cal.low, 0.75)
        self.assertGreater(cal.suggest(), 0.75)

    def test_within_tolerance_converges_and_stops(self):
        cal = Calibration(target=843, low=0.5, high=1.0, tolerance=4)
        cal.record(0.7, 845)
        self.assertTrue(cal.converged)
        self.assertIsNone(cal.suggest())

    def test_a_collapsed_interval_stops_the_search(self):
        cal = Calibration(target=843, low=0.70, high=0.703)
        cal.record(0.701, 700)
        self.assertIsNone(cal.suggest())

    def test_the_report_lists_every_measurement(self):
        cal = Calibration(target=843, low=0.5, high=1.0)
        cal.record(0.75, 900)
        report = cal.report()
        self.assertIn('scale=0.750 → 900 页', report)
        self.assertIn('未收敛', report)


if __name__ == '__main__':
    unittest.main()
