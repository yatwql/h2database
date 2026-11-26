"""Measurement, comparison and calibration are arithmetic: test them without a book.

The CLI only renders what these functions compute, so a page count that moves for the
wrong reason should fail here rather than in a calibration run that costs minutes.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:render", "tier:fast")

_fixture.ensure_tools_path()

_metrics = __import__(
    "render.pdf_metrics",
    fromlist=[
        "describe",
        "compare",
        "Calibration",
        "calibrate",
        "compare_targets",
        "parse_targets",
        "write_back",
        "main",
    ],
)


def measured(**overrides) -> dict:
    """One measurement record, with the numbers a caller would read."""
    base = {
        "path": "/tmp/book.pdf",
        "pages": 900,
        "mb": 7.5,
        "chars_per_page": 1900,
        "body_pt": 6.8,
        "heading_pt": 21.6,
        "body_share": 74,
        "lines_per_page": 50,
        "pitch_pt": 8.2,
        "text_width_pt": 540.0,
    }
    base.update(overrides)
    return base


class DescribeTest(unittest.TestCase):
    def test_every_number_reaches_the_line(self):
        text = _metrics.describe(measured())
        for token in (
            "book.pdf",
            "900",
            "7.50 MB",
            "6.8pt",
            "74%",
            "21.6pt",
            "8.2pt",
            "50",
            "540.0pt",
            "1900",
        ):
            self.assertIn(token, text)

    def test_a_long_filename_is_clipped_to_the_column(self):
        text = _metrics.describe(measured(path="/tmp/" + "x" * 60 + ".pdf"))
        self.assertLessEqual(len(text.split()[0]), 34)


class CompareTest(unittest.TestCase):
    def test_a_metric_inside_the_tolerance_carries_no_flag(self):
        text = _metrics.compare(measured(), measured(pages=910))
        self.assertNotIn("←", text)

    def test_a_larger_metric_is_flagged_as_large(self):
        text = _metrics.compare(measured(), measured(pages=1200))
        self.assertIn("偏大", text)

    def test_a_smaller_metric_is_flagged_as_small(self):
        text = _metrics.compare(measured(), measured(pages=600))
        self.assertIn("偏小", text)

    def test_a_zero_reference_reports_no_delta_instead_of_dividing(self):
        text = _metrics.compare(measured(body_pt=0), measured(body_pt=7))
        self.assertIn("+0.0%", text)


class TargetsTest(unittest.TestCase):
    def test_a_target_spec_parses_to_numbers(self):
        self.assertEqual(
            _metrics.parse_targets("pages=843,chars_per_page=1905"),
            {"pages": 843.0, "chars_per_page": 1905.0},
        )

    def test_blank_parts_and_spaces_are_ignored(self):
        self.assertEqual(
            _metrics.parse_targets(" pages = 12 ,, mb=7.5 "), {"pages": 12.0, "mb": 7.5}
        )

    def test_an_unknown_metric_is_named(self):
        self.assertIn("未知指标", _metrics.compare_targets(measured(), {"nope": 1}))

    def test_a_target_is_compared_and_flagged(self):
        text = _metrics.compare_targets(measured(), {"pages": 500})
        self.assertIn("偏大", text)
        text = _metrics.compare_targets(measured(), {"pages": 900})
        self.assertNotIn("←", text)


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

    def test_a_measurement_exactly_on_target_moves_no_bound(self):
        search = _metrics.Calibration(target=100, low=0.5, high=1.5)
        search.record(1.0, 100)
        self.assertEqual((search.low, search.high), (0.5, 1.5))
        self.assertTrue(search.converged)

    def test_a_collapsed_interval_stops_without_converging(self):
        search = _metrics.Calibration(target=100, low=1.0, high=1.001)
        self.assertFalse(search.converged)
        self.assertIsNone(search.suggest())

    def test_the_report_names_the_bounds_and_the_verdict(self):
        search = _metrics.Calibration(target=100, low=0.5, high=1.5)
        search.record(1.0, 130)
        text = search.report()
        self.assertIn("目标 100 页", text)
        self.assertIn("未收敛", text)
        self.assertIn("scale=1.000", text)


class CalibrateTest(unittest.TestCase):
    def test_a_render_that_lands_on_target_returns_its_scale(self):
        pages = iter([80, 130, 99, 100])

        def render(scale: float) -> str:
            return f"/tmp/{scale}.pdf"

        with mock.patch.object(
            _metrics, "measure", side_effect=lambda path: {"pages": next(pages)}
        ):
            search, hit = _metrics.calibrate(render, target=100, low=0.5, high=1.5)
        self.assertIsNotNone(hit)
        self.assertTrue(search.converged)

    def test_a_search_that_never_lands_returns_none(self):
        with mock.patch.object(_metrics, "measure", return_value={"pages": 10}):
            search, hit = _metrics.calibrate(
                lambda scale: "/tmp/x.pdf", target=900, low=0.5, high=1.5, max_rounds=2
            )
        self.assertIsNone(hit)
        self.assertEqual(len(search.history), 2)


class WriteBackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "base.json")
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"toolchain": {"print_scale": 0.667, "pdf_max_mb": 12}}, handle)

    def read(self) -> dict:
        with open(self.path, encoding="utf-8") as handle:
            return json.load(handle)

    def test_the_value_is_replaced_and_the_rest_untouched(self):
        _metrics.write_back(self.path, "print_scale", 0.71)
        payload = self.read()
        self.assertEqual(payload["toolchain"]["print_scale"], 0.71)
        self.assertEqual(payload["toolchain"]["pdf_max_mb"], 12)

    def test_a_missing_key_is_refused(self):
        with self.assertRaises(SystemExit):
            _metrics.write_back(self.path, "nope", 1)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = os.path.join(self.tmp.name, "book.pdf")
        from pypdf import PdfWriter

        writer = PdfWriter()
        for _ in range(2):
            writer.add_blank_page(width=595, height=842)
        with open(self.pdf, "wb") as handle:
            writer.write(handle)

    def run_cli(self, *argv: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = _metrics.main(["pdf_metrics.py", *argv])
        return code, buffer.getvalue()

    def test_no_arguments_prints_the_usage_and_returns_two(self):
        code, out = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn("Usage", out + _metrics.__doc__)

    def test_a_measurement_is_printed_for_one_pdf(self):
        code, out = self.run_cli(self.pdf)
        self.assertEqual(code, 0)
        self.assertIn("book.pdf", out)

    def test_compare_needs_two_pdfs(self):
        code, out = self.run_cli("--compare", self.pdf)
        self.assertEqual(code, 2)
        self.assertIn("两个", out)

    def test_compare_prints_both_measurements(self):
        code, out = self.run_cli("--compare", self.pdf, self.pdf)
        self.assertEqual(code, 0)
        self.assertEqual(out.count("book.pdf"), 2)

    def test_a_target_compares_one_pdf_with_numbers(self):
        code, out = self.run_cli("--target", "pages=2", self.pdf)
        self.assertEqual(code, 0)
        self.assertIn("pages", out)

    def test_a_lone_target_flag_falls_through_to_the_usage(self):
        code, out = self.run_cli("--target")
        self.assertEqual(code, 2)
        self.assertIn("Usage", out)

    def test_a_dash_spec_is_not_a_file_path_so_the_usage_is_printed(self):
        # a spec starting with '-' never enters `args`; with no PDF path left the CLI
        # prints the usage instead of measuring the spec as a file
        code, out = self.run_cli("--target", "-pages=2")
        self.assertEqual(code, 2)
        self.assertEqual(out, _metrics.__doc__ + "\n")


class ModulePathTest(unittest.TestCase):
    """The module is importable from anywhere: it puts its package root first."""

    script = os.path.join(_fixture.TOOLS_DIR, "render", "pdf_metrics.py")

    def test_loading_it_without_its_package_root_restores_the_path(self):
        pruned = [
            entry
            for entry in sys.path
            if os.path.realpath(entry or ".") != os.path.realpath(_fixture.TOOLS_DIR)
        ]
        self.assertNotIn(
            os.path.realpath(_fixture.TOOLS_DIR),
            [os.path.realpath(entry or ".") for entry in pruned],
        )
        spec = importlib.util.spec_from_file_location("pdf_metrics_standalone", self.script)
        if spec is None or spec.loader is None:
            raise AssertionError(f"cannot load {self.script}")
        module = importlib.util.module_from_spec(spec)
        with mock.patch.object(sys, "path", pruned):
            spec.loader.exec_module(module)
            self.assertEqual(os.path.realpath(sys.path[0]), os.path.realpath(_fixture.TOOLS_DIR))
        self.assertEqual(module.SAMPLE_PAGES, 80)

    def test_the_script_entrypoint_prints_the_usage(self):
        code, out = _fixture.run_inproc(_fixture.BOOK_ROOT, "pdf_metrics.py")
        self.assertEqual(code, 2)
        self.assertIn("Usage", out)


class BoundaryTest(unittest.TestCase):
    """The comparisons at exactly 3% and exactly the sample size decide the outcome."""

    def test_exactly_three_percent_is_not_flagged(self):
        text = _metrics.compare(measured(), measured(pages=927))  # +3.0%
        self.assertNotIn("←", text)

    def test_just_over_three_percent_is_flagged(self):
        text = _metrics.compare(measured(), measured(pages=930))
        self.assertIn("←", text)

    def test_a_target_that_matches_exactly_is_not_flagged(self):
        text = _metrics.compare_targets(measured(), {"pages": 900})
        self.assertNotIn("←", text)

    def test_a_target_off_by_exactly_three_percent_is_not_flagged(self):
        text = _metrics.compare_targets(measured(), {"pages": 927})
        self.assertNotIn("←", text)

    def test_a_page_count_at_the_sample_size_is_returned_whole(self):
        reader = mock.Mock()
        reader.pages = list(range(_metrics.SAMPLE_PAGES))
        self.assertEqual(len(_metrics._sample(reader)), _metrics.SAMPLE_PAGES)

    def test_one_page_over_the_sample_is_windowed(self):
        reader = mock.Mock()
        reader.pages = list(range(_metrics.SAMPLE_PAGES + 10))
        self.assertEqual(len(_metrics._sample(reader)), _metrics.SAMPLE_PAGES)

    def test_landing_exactly_at_the_tolerance_converges(self):
        search = _metrics.Calibration(target=100, low=0.5, high=1.5, tolerance=4)
        search.record(1.0, 104)
        self.assertTrue(search.converged)

    def test_an_interval_at_the_floor_stops(self):
        search = _metrics.Calibration(target=100, low=1.000, high=1.005)
        self.assertIsNone(search.suggest())




class WriteBackCliTest(unittest.TestCase):
    """`--write-back` persists the calibrated knob and reports it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = os.path.join(self.tmp.name, "base.json")
        with open(self.config, "w", encoding="utf-8") as handle:
            handle.write('{\n  "toolchain": {\n    "pdf_bytes_per_page": 24576\n  }\n}\n')
        self.mod = _metrics

    def test_the_value_is_written_and_reported(self):
        buffer = io.StringIO()
        current = mock.Mock(base_policy_path=self.config)
        with (
            mock.patch.object(self.mod._config, "current", return_value=current),
            redirect_stdout(buffer),
        ):
            code = self.mod.main(["pdf_metrics.py", "--write-back", "pdf_bytes_per_page=30000"])
        self.assertEqual(code, 0)
        self.assertIn("pdf_bytes_per_page = 30000", buffer.getvalue())
        with open(self.config, encoding="utf-8") as handle:
            self.assertIn("30000", handle.read())

    def test_an_unknown_knob_is_refused(self):
        with self.assertRaises(SystemExit) as raised:
            self.mod.write_back(self.config, "no_such_knob", 1.0)
        self.assertIn("no_such_knob", str(raised.exception.code))


@unittest.skipUnless(importlib.util.find_spec("pypdf"), "pypdf not installed")
class MeasureTextPdfTest(unittest.TestCase):
    """A PDF with real text: the visitor path that a blank page never reaches."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = os.path.join(self.tmp.name, "text.pdf")
        self.write_text_pdf(self.pdf, [["First line of body text.", "Second line."]])

    @staticmethod
    def write_text_pdf(path: str, pages: list[list[str]]) -> None:
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

        writer = PdfWriter()
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        font_ref = writer._add_object(font)
        for lines in pages:
            page = writer.add_blank_page(width=595, height=842)
            page[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
            )
            stream = DecodedStreamObject()
            body = ["BT", "/F1 12 Tf", "14 TL", "40 800 Td"]
            for line in lines:
                escaped = line.replace("(", r"\(").replace(")", r"\)")
                body.append(f"({escaped}) Tj T*")
            body.append("ET")
            stream.set_data("\n".join(body).encode("utf-8"))
            page[NameObject("/Contents")] = writer._add_object(stream)
        with open(path, "wb") as handle:
            writer.write(handle)

    def test_the_measured_width_and_body_size_come_from_the_text(self):
        metrics = _metrics.measure(self.pdf)
        self.assertGreater(metrics["text_width_pt"], 0.0)
        self.assertGreater(metrics["body_pt"], 0.0)
        self.assertGreater(metrics["chars_per_page"], 0)
        # the share is a percentage of the characters actually counted
        self.assertLessEqual(metrics["body_share"], 100)
        self.assertGreater(metrics["body_share"], 0)
        # two lines set at 14pt leading: pitch and line count come from the order
        self.assertAlmostEqual(metrics["pitch_pt"], 14.0, places=1)
        self.assertEqual(metrics["lines_per_page"], 2)


if __name__ == "__main__":
    unittest.main()
