#!/usr/bin/env python3
"""End-to-end tests: run the delivery scripts against a fixture book.

Each test materialises a miniature book (book.toml + manuscript/ + dist/) in a
temporary directory, points BOOK_ROOT at it, and asserts the script's real
behaviour. This is what catches path drift, config wiring mistakes and
regressions in the audits — the class of bug unit tests cannot see.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

import _fixture

TAGS = ("layer:audit", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class FixtureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def dist(self, name: str) -> str:
        return os.path.join(self.root, "dist", name)

    def read(self, path: str) -> str:
        with open(path, encoding="utf-8") as fh:
            return fh.read()


class TestAsciiScanScope(FixtureTest):
    """The file selection, the baseline writer and the report, in-process."""

    def manuscript(self, *parts: str) -> str:
        return os.path.join(self.root, "data", "manuscript", *parts)

    def diagrams(self):
        # `lib._baseline` keeps the config module of the book it was first imported
        # under; without dropping the package attribute the second book is read
        # through the first book's paths.
        lib = sys.modules.get("lib")
        if lib is not None and hasattr(lib, "_baseline"):
            delattr(lib, "_baseline")
        return _fixture.load_module(self.root, "diagrams")

    def test_a_pattern_selects_the_files_to_scan(self):
        diagrams = self.diagrams()
        self.assertEqual(
            [os.path.basename(p) for p in diagrams.target_files("ch2*.md")], ["ch2-test.md"]
        )

    def test_a_line_past_the_end_of_the_file_keys_on_an_empty_text(self):
        diagrams = self.diagrams()
        self.assertEqual(diagrams._line_text(self.manuscript("ch1-test.md"), 9999), "")

    def test_updating_the_baseline_accepts_the_violations_already_found(self):
        with open(self.manuscript("ch1-test.md"), "a", encoding="utf-8") as fh:
            fh.write("\n```text\n" + "x" * 130 + "\n```\n")
        diagrams = self.diagrams()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = diagrams.main(["--update-baseline"])
        self.assertEqual(code, 0, buffer.getvalue())
        self.assertIn("baseline updated", buffer.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(diagrams.main([]), 0)

    def test_the_report_says_how_many_violations_it_did_not_list(self):
        lines = "".join("```text\n" + "x" * 130 + "\n```\n" for _ in range(61))
        with open(self.manuscript("ch1-test.md"), "a", encoding="utf-8") as fh:
            fh.write("\n" + lines)
        diagrams = self.diagrams()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = diagrams.main([])
        self.assertEqual(code, 1, buffer.getvalue()[-500:])
        self.assertIn("and 1 more", buffer.getvalue())


class TestAsciiAudit(FixtureTest):
    def test_clean_fixture_passes(self):
        result = _fixture.run(self.root, "diagrams.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_wide_diagram_fails(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n```text\n" + "x" * 120 + "\n```\n")
        result = _fixture.run(self.root, "diagrams.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("WIDE_LINE", result.stdout)

    def test_baseline_absorbs_known_violation(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n```text\n" + "x" * 120 + "\n```\n")
        self.assertEqual(_fixture.run(self.root, "diagrams.py", "--update-baseline").returncode, 0)
        self.assertEqual(_fixture.run(self.root, "diagrams.py").returncode, 0)


if __name__ == "__main__":
    unittest.main()
