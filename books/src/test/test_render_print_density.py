"""The printed edition is fitted to the sheet, and the fit is decided by numbers.

Two questions, one file: does the print CSS derive its column and code size from the
paper, and does the merge log what the compression pass decided. Both were invisible
before — the column was a literal and a skipped gs pass read like a pass that bought
nothing.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:render", "tier:fast")

_fixture.ensure_tools_path()

_split = __import__("render.pdf_split", fromlist=["accept_optimised", "_optimize"])
_shell = __import__("render.html_shell", fromlist=["apply_layout", "STYLE"])
_layout = __import__("lib.layout", fromlist=["Layout"])
_config = __import__("lib._config", fromlist=["THRESHOLDS"])

accept_optimised = _split.accept_optimised


def _blank_pdf(path: str, pages: int = 1) -> None:
    from pypdf import PdfWriter  # noqa: PLC0415 - after the fixture selected a book

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with open(path, "wb") as handle:
        writer.write(handle)


class OptimiseDecisionTest(unittest.TestCase):
    """The rewrite replaces the merge only when it is smaller and still complete."""

    def test_a_smaller_complete_file_is_accepted(self):
        self.assertTrue(accept_optimised(621, 6_000_000, 621, 5_000_000))

    def test_a_smaller_truncated_file_is_rejected(self):
        self.assertFalse(accept_optimised(621, 6_000_000, 600, 5_000_000))

    def test_a_larger_file_is_rejected(self):
        self.assertFalse(accept_optimised(621, 5_000_000, 621, 6_000_000))


class _FakeReader:
    """Stands in for pypdf: the run only needs the page count."""

    def __init__(self, pages: int):
        self.pages = list(range(pages))


class OptimiseRunTest(unittest.TestCase):
    """Every run says what it did: skipped, failed, accepted or refused."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = os.path.join(self.tmp.name, "merged.pdf")
        with open(self.pdf, "wb") as handle:
            handle.write(b"%PDF-1.4 original payload")
        self.log = mock.MagicMock()
        patcher = mock.patch.object(_split._log, "get_logger", return_value=self.log)
        patcher.start()
        self.addCleanup(patcher.stop)
        reader = mock.patch.object(
            _split, "PdfReader", side_effect=lambda path: _FakeReader(1 if path == self.pdf else 2)
        )
        reader.start()
        self.addCleanup(reader.stop)

    def fake_gs(self):
        """A gs stub that writes the path the command names."""

        def run(cmd, **_kwargs):
            target = next(part for part in cmd if part.startswith("-sOutputFile="))
            with open(target.split("=", 1)[1], "wb") as handle:
                handle.write(b"%PDF-1.4 compressed")

        return run

    def test_a_missing_gs_is_logged_and_the_file_is_left_alone(self):
        with mock.patch.object(_split.shutil, "which", return_value=None):
            _split._optimize(self.pdf)
        self.log.info.assert_called()
        self.assertIn("gs", self.log.info.call_args[0][0])
        with open(self.pdf, "rb") as handle:
            self.assertIn(b"original payload", handle.read())

    def test_an_accepted_rewrite_replaces_the_file(self):
        with (
            mock.patch.object(_split.shutil, "which", return_value="/usr/bin/gs"),
            mock.patch.object(_split.subprocess, "run", side_effect=self.fake_gs()),
            mock.patch.object(_split, "accept_optimised", return_value=True),
        ):
            _split._optimize(self.pdf)
        with open(self.pdf, "rb") as handle:
            self.assertIn(b"compressed", handle.read())
        self.assertIn("已采用", self.log.info.call_args[0])

    def test_a_refused_rewrite_keeps_the_merge(self):
        with (
            mock.patch.object(_split.shutil, "which", return_value="/usr/bin/gs"),
            mock.patch.object(_split.subprocess, "run", side_effect=self.fake_gs()),
            mock.patch.object(_split, "accept_optimised", return_value=False),
        ):
            _split._optimize(self.pdf)
        with open(self.pdf, "rb") as handle:
            self.assertIn(b"original payload", handle.read())
        self.assertIn("不采用（须同页数且更小）", self.log.info.call_args[0])

    def test_a_failed_gs_run_is_a_warning_not_a_broken_build(self):
        with (
            mock.patch.object(_split.shutil, "which", return_value="/usr/bin/gs"),
            mock.patch.object(_split.subprocess, "run", side_effect=OSError("boom")),
        ):
            _split._optimize(self.pdf)
        self.log.warning.assert_called()
        with open(self.pdf, "rb") as handle:
            self.assertIn(b"original payload", handle.read())

    def test_the_temporary_file_never_survives_the_run(self):
        with (
            mock.patch.object(_split.shutil, "which", return_value="/usr/bin/gs"),
            mock.patch.object(_split.subprocess, "run", side_effect=self.fake_gs()),
            mock.patch.object(_split, "accept_optimised", return_value=True),
        ):
            _split._optimize(self.pdf)
        self.assertEqual(sorted(os.listdir(self.tmp.name)), ["merged.pdf"])


class PrintStylesheetTest(unittest.TestCase):
    """The stylesheet takes the printed column and code size from the layout."""

    def layout(self):
        return _layout.Layout.from_mapping(_config.THRESHOLDS)[0]

    def test_the_printed_column_comes_from_the_layout(self):
        with mock.patch.dict(_config.THRESHOLDS, {"layout_column_px": 512}):
            css = _shell.apply_layout(_shell.STYLE)
        self.assertIn("max-width: 512px", css)

    def test_the_printed_code_size_follows_the_width_budget(self):
        columns = int(_config.THRESHOLDS.get("ascii_max_cols", 100))
        css = _shell.apply_layout(_shell.STYLE)
        self.assertIn(f"font-size: {self.layout().print_code_px(columns):g}px", css)

    def test_the_code_size_keeps_a_budget_line_inside_the_sheet(self):
        columns = int(_config.THRESHOLDS.get("ascii_max_cols", 100))
        layout = self.layout()
        self.assertLessEqual(
            columns * layout.print_mono_advance * layout.print_code_px(columns),
            layout.printable_width_px() + 0.5,
        )

    def test_the_budget_line_fits_so_wrapping_stays_off(self):
        columns = int(_config.THRESHOLDS.get("ascii_max_cols", 100))
        self.assertNotIn("white-space: pre-wrap", _shell.STYLE)
        self.assertFalse(self.layout().print_wraps(columns))

    def test_a_budget_wider_than_the_sheet_turns_on_wrapping(self):
        with mock.patch.dict(_config.THRESHOLDS, {"ascii_max_cols": 4000}):
            css = _shell.apply_layout(_shell.STYLE)
        self.assertIn("white-space: pre-wrap", css)

    def test_the_printed_toc_is_confined_to_the_column(self):
        css = _shell.apply_layout(_shell.STYLE)
        self.assertIn("margin-left: 0 !important", css)
        self.assertIn(f"#toc-page {{ max-width: {self.layout().print_column()}px; }}", css)

    def test_the_page_rule_names_the_sheet_and_the_derived_margin(self):
        css = _shell.apply_layout(_shell.STYLE)
        layout = self.layout()
        self.assertIn(
            f"  @page {{ size: {layout.page_size}; margin: {layout.print_page_margin()}; }}", css
        )

    def test_a_comma_separated_font_config_becomes_a_candidate_list(self):
        with mock.patch.dict(_config.THRESHOLDS, {"font_stack_sans": " Noto Sans , ,Source Han "}):
            self.assertEqual(
                _shell._configured_families("font_stack_sans"), ["Noto Sans", "Source Han"]
            )

    def test_a_font_config_given_as_a_list_drops_the_empty_names(self):
        with mock.patch.dict(_config.THRESHOLDS, {"font_stack_mono": [" JetBrains Mono ", "", 7]}):
            self.assertEqual(
                _shell._configured_families("font_stack_mono"), ["JetBrains Mono", "7"]
            )

    def test_a_font_config_of_another_shape_falls_back_to_the_host_guess(self):
        with mock.patch.dict(_config.THRESHOLDS, {"font_stack_mono": {"a": 1}}):
            self.assertIsNone(_shell._configured_families("font_stack_mono"))

    def test_the_shell_imports_without_the_config_module(self):
        # The print CSS is also rendered from a bare install where lib._config is
        # absent; the module degrades to host detection instead of failing to load.
        import runpy  # noqa: PLC0415 - only this case needs the machinery
        import types  # noqa: PLC0415

        # a package that has the font modules but no config module at all
        stub = types.SimpleNamespace(
            fonts=sys.modules["lib.fonts"], layout=sys.modules["lib.layout"]
        )
        with mock.patch.dict(sys.modules, {"lib": stub, "lib._config": None}):
            namespace = runpy.run_path(
                os.path.join(_fixture.TOOLS_DIR, "render", "html_shell.py"),
                run_name="html_shell_without_config",
            )
        self.assertIsNone(namespace["_config"])
        self.assertIsNone(namespace["_configured_families"]("font_stack_sans"))


if __name__ == "__main__":
    unittest.main()
