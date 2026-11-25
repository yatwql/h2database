#!/usr/bin/env python3
"""Unit tests for the helper functions behind the audits.

These target the pure logic (counting, parsing, clustering, PDF checks) that the
end-to-end tests exercise only indirectly.
"""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture
from _cases import FixtureCase

TAGS = ("layer:audit", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class TestSourceFreshnessHelpers(FixtureCase):
    def test_resolve_and_verify(self):
        sfc = self.module("source_refs")
        with tempfile.TemporaryDirectory() as tmp:
            java = os.path.join(tmp, "MVStore.java")
            with open(java, "w", encoding="utf-8") as fh:
                fh.write("class MVStore {\n  void open() {}\n}\n")
            index = {"MVStore": [java]}
            ref = sfc.Reference("ch1.md", 3, "MVStore", 2)
            resolved = sfc.resolve_references([ref], index)
            self.assertEqual(resolved[0].status, "FOUND")
            checks = sfc.verify_line_numbers(resolved)
            self.assertEqual(checks[0].status, "OK")

    def test_verify_line_numbers_flags_offset(self):
        sfc = self.module("source_refs")
        with tempfile.TemporaryDirectory() as tmp:
            java = os.path.join(tmp, "A.java")
            with open(java, "w", encoding="utf-8") as fh:
                fh.write("class A {}\n")
            index = {"A": [java]}
            resolved = sfc.resolve_references([sfc.Reference("ch.md", 1, "A", 99)], index)
            checks = sfc.verify_line_numbers(resolved)
            self.assertEqual(checks[0].status, "OFFSET")

    def test_missing_class_reported(self):
        sfc = self.module("source_refs")
        resolved = sfc.resolve_references([sfc.Reference("ch.md", 1, "NoSuchClass", 1)], {})
        self.assertEqual(resolved[0].status, "MISSING")

    def test_ambiguous_class_reported(self):
        sfc = self.module("source_refs")
        resolved = sfc.resolve_references(
            [sfc.Reference("ch.md", 1, "Dup", 1)], {"Dup": ["a.java", "b.java"]}
        )
        self.assertEqual(resolved[0].status, "AMBIGUOUS")

    def test_claim_key_is_stable(self):
        sfc = self.module("source_refs")
        a = sfc._claim_key("ch1.md", "MVMap", "open")
        b = sfc._claim_key("ch1.md", "MVMap", "open")
        self.assertEqual(a, b)
        self.assertNotEqual(a, sfc._claim_key("ch2.md", "MVMap", "open"))


if __name__ == "__main__":
    unittest.main()


class PrefixFallbackTest(unittest.TestCase):
    """An unconfigured package prefix is named as unknown, not left empty."""

    def setUp(self):
        self.mod = _fixture.load_module(_fixture.build_book(tempfile.mkdtemp()), "source_refs")

    def test_a_missing_prefix_reads_as_unknown(self):
        with mock.patch.dict(self.mod._config.SOURCES, {}, clear=True):
            self.assertEqual(self.mod.package_prefix(), "unknown")

    def test_a_configured_prefix_is_returned(self):
        with mock.patch.dict(self.mod._config.SOURCES, {"package_prefix": "org.x"}):
            self.assertEqual(self.mod.package_prefix(), "org.x")


class SourceFreshnessErrorPaths(FixtureCase):
    """The paths a clean source tree never reaches: unreadable files, bad state."""

    def sfc(self):
        return self.module("source_refs")

    def test_the_project_version_is_read_from_the_pom(self):
        sfc = self.sfc()
        pom = self.write("pom.xml", "<project>\n  <version>2.3.232</version>\n</project>\n")
        with mock.patch.object(sfc, "pom_path", lambda: pom):
            self.assertEqual(sfc.get_project_version(), "2.3.232")
        plain = self.write("pom2.xml", "<project/>\n")
        with mock.patch.object(sfc, "pom_path", lambda: plain):
            self.assertEqual(sfc.get_project_version(), "unknown")

    def test_an_unreadable_inventory_reads_as_empty(self):
        sfc = self.sfc()
        broken = self.write("state/source-inventory.json", "{not json")
        with mock.patch.object(sfc._config, "state_path", lambda name: broken):
            self.assertEqual(sfc._preferred_paths(), {})

    def test_a_claim_in_a_missing_chapter_is_skipped(self):
        sfc = self.sfc()
        self.assertEqual(sfc.extract_symbol_claims(["nope.md"], docs_dir=self.tmp.name), [])

    def test_a_claim_against_an_unreadable_class_file_is_not_an_error(self):
        sfc = self.sfc()
        claim = sfc.SymbolClaim("ch1.md", 1, "Gone", "open")
        missing = os.path.join(self.tmp.name, "gone", "Gone.java")
        self.assertEqual(sfc.verify_symbol_claims([claim], {"Gone": [missing]}), [])

    def test_an_unreadable_file_raises_with_a_note(self):
        sfc = self.sfc()
        with self.assertRaises(OSError) as raised:
            sfc._count_file_lines(os.path.join(self.tmp.name, "missing.java"))
        self.assertTrue(getattr(raised.exception, "__notes__", []))

    def test_line_verification_skips_the_candidates_it_cannot_read(self):
        sfc = self.sfc()
        good = self.write("A.java", "class A {}\n\n")
        index = {"A": [os.path.join(self.tmp.name, "missing.java"), good]}
        resolved = sfc.resolve_references([sfc.Reference("ch.md", 1, "A", 2)], index)
        self.assertEqual(sfc.verify_line_numbers(resolved)[0].status, "OK")

    def test_line_verification_reports_an_unreadable_file(self):
        sfc = self.sfc()
        index = {"A": [os.path.join(self.tmp.name, "missing.java")]}
        resolved = sfc.resolve_references([sfc.Reference("ch.md", 1, "A", 1)], index)
        self.assertEqual(sfc.verify_line_numbers(resolved)[0].status, "ERROR")

    def test_ambiguous_classes_are_listed_in_the_report(self):
        sfc = self.sfc()
        index = {
            "Dup": [
                os.path.join(self.tmp.name, "a", "Dup.java"),
                os.path.join(self.tmp.name, "b", "Dup.java"),
            ]
        }
        resolved = sfc.resolve_references([sfc.Reference("ch.md", 1, "Dup", 1)], index)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            sfc._print_ambiguous(sfc.verify_line_numbers(resolved), index)
        self.assertIn("AMBIGUOUS class names", buffer.getvalue())

    def test_the_baseline_is_written_and_reported(self):
        sfc = self.sfc()
        buffer = io.StringIO()
        with mock.patch.object(sfc, "save_baseline") as saved, redirect_stdout(buffer):
            self.assertEqual(sfc._record_baseline("base.json", [], "2.3"), 0)
        saved.assert_called_once()
        self.assertIn("baseline updated", buffer.getvalue())

    def test_new_and_known_drift_are_printed_with_hints(self):
        sfc = self.sfc()
        claim = sfc.SymbolClaim("ch1.md", 3, "MVMap", "open")
        args = mock.Mock(suggest=True)
        buffer = io.StringIO()
        with (
            mock.patch.object(sfc, "suggest_renames", return_value=["openMap"]),
            redirect_stdout(buffer),
        ):
            sfc._print_drift(
                [(claim, "MVMap.java")],
                [(claim, "MVMap.java")],
                [(claim, "MVMap.java")],
                args,
                {"MVMap": ["MVMap.java"]},
            )
        text = buffer.getvalue()
        self.assertIn("NEW", text)
        self.assertIn("openMap", text)
        self.assertIn("known", text)
        self.assertIn("refresh baseline", text)

    def test_main_separates_the_baseline_modes_from_the_report(self):
        sfc = self.sfc()
        claim = sfc.SymbolClaim("ch1.md", 3, "MVMap", "open")
        scan = mock.patch.object(sfc, "_scan", return_value=([], [(claim, "MVMap.java")]))
        index = mock.patch.object(sfc, "_index_or_skip", return_value={"MVMap": ["MVMap.java"]})
        saved = mock.patch.object(sfc, "save_baseline")
        for patcher in (scan, index, saved):
            patcher.start()
            self.addCleanup(patcher.stop)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(sfc.main(["--update-baseline"]), 0)
            self.assertEqual(sfc.main(["--prune"]), 0)
            self.assertEqual(sfc.main([]), 1)
        with (
            mock.patch.object(sfc, "_index_or_skip", side_effect=RuntimeError("boom")),
            redirect_stdout(io.StringIO()),
            mock.patch("sys.stderr", new=io.StringIO()),
        ):
            self.assertEqual(sfc.main([]), 1)
