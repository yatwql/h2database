#!/usr/bin/env python3
"""Branch coverage for the audit/report paths.

These exercise the error and edge branches (missing files, empty inputs,
threshold violations, alternate CLI modes) that the happy-path tests skip.
"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

from _cases import FixtureCase

SOURCE_PATH = os.path.join(os.sep, 'synthetic', 'A.java')

TAGS = ('layer:audit', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)


class TestSourceFreshnessReport(FixtureCase):
    def test_print_report_branches(self):
        sfc = self.module('source_refs')
        ref_ok = sfc.Reference('ch.md', 1, 'A', 2)
        ref_missing = sfc.Reference('ch.md', 2, 'B', 5)
        results = [
            sfc.Verification(ref_ok, 'OK', SOURCE_PATH, ''),
            sfc.Verification(ref_ok, 'OFFSET', SOURCE_PATH, 'file has 1 lines, offset -1'),
            sfc.Verification(ref_missing, 'MISSING', None, ''),
            sfc.Verification(ref_ok, 'ERROR', SOURCE_PATH, 'boom'),
        ]
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            sfc.print_report(results, {'A': [SOURCE_PATH], 'Dup': ['a', 'b']})
        report = buffer.getvalue()
        for status in ('OK', 'OFFSET', 'ERROR'):
            self.assertIn(status, report)


class TestSourceFreshnessBranches(FixtureCase):
    def test_missing_reference_and_baseline_flow(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n见 NoSuchClass.java:12 与 Page.java:3\n')
        code, out = self.run_script('source_refs.py')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('source tree not found', out)
        self.assertNotIn('Traceback', out)

    def test_update_baseline_then_clean(self):
        self.write('data/manuscript/ch1-test.md',
                   '# 第1章 测试章节\n\n见 MVStore.rollbackTo() 用法\n')
        code, _ = self.run_script('source_refs.py', '--update-baseline')
        self.assertEqual(code, 0)
        code, out = self.run_script('source_refs.py', '--suggest')
        self.assertEqual(code, 0, out[-300:])
        self.assertIn('source tree not found', out)


class DriftVersionNoticeTest(FixtureCase):
    """Accepted symbol drift is a statement about one source tree, not about all of them."""

    def notice(self, recorded, current):
        module = self.module("source_refs")
        with (
            mock.patch.object(module._baseline, "load_raw", return_value=recorded),
            mock.patch.object(module._config, "current") as config,
        ):
            config.return_value.versions.return_value = {"source": current}
            return module.drift_version_notice()

    def test_a_baseline_recorded_against_another_version_is_called_out(self):
        notice = self.notice({"source_version": "1.0"}, "2.0")
        self.assertIn("recorded against 1.0", notice)
        self.assertIn("tree is 2.0", notice)

    def test_matching_or_missing_versions_are_silent(self):
        self.assertEqual(self.notice({"source_version": "2.0"}, "2.0"), "")
        self.assertEqual(self.notice({}, "2.0"), "")
        self.assertEqual(self.notice({"source_version": ""}, "2.0"), "")

    def test_the_notice_is_printed_for_people_and_left_to_json_otherwise(self):
        module = self.module("source_refs")
        buffer = io.StringIO()
        with (
            mock.patch.object(module, "drift_version_notice", return_value="  [note] drift"),
            redirect_stdout(buffer),
        ):
            module.report_notice(False)
            module.report_notice(True)
        self.assertEqual(buffer.getvalue(), "  [note] drift\n")


if __name__ == '__main__':
    unittest.main()
