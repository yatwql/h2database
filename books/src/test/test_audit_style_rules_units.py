#!/usr/bin/env python3
"""Style rules gate: terminology, spacing, headings, list punctuation."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

_fixture.ensure_tools_path()

BOOK_ROOT = os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR))


class StyleRulesUnitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(BOOK_ROOT, "style_rules")

    def doc(self, text: str) -> str:
        path = os.path.join(self.tmp.name, "doc.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def findings(self, text: str, rules: dict | None = None) -> list[dict]:
        settings = rules if rules is not None else {}
        with mock.patch.object(self.mod, "RULES", settings):
            return self.mod.check_file(self.doc(text))

    def test_clean_document_has_no_findings(self):
        rules = {
            "terminology": [],
            "banned_link_text": [],
            "heading": {},
            "cjk_latin_spacing": True,
        }
        self.assertEqual(
            self.findings("# 标题\n\n正文一段，中文与 English 之间留空格。\n", rules), []
        )

    def test_cjk_latin_spacing_is_reported(self):
        findings = self.findings(
            "# 标题\n\n使用 KVStore存储 的实现。\n", {"cjk_latin_spacing": True}
        )
        self.assertEqual(findings[0]["kind"], "CJK_SPACE")

    def test_terminology_synonyms_are_reported(self):
        rules = {"terminology": [["缓冲池", "缓冲区域"]]}
        findings = self.findings("# 标题\n\n缓冲池与缓冲区域并存。\n", rules)
        self.assertEqual(findings[0]["kind"], "TERM")

    def test_banned_link_text_is_reported(self):
        rules = {"banned_link_text": ["点这里"]}
        findings = self.findings("# 标题\n\n见[点这里](../x.md)。\n", rules)
        self.assertEqual(findings[0]["kind"], "LINK")

    def test_heading_rule_checks_trailing_punctuation(self):
        rules = {"heading": {"no_trailing_punctuation": True}}
        findings = self.findings("## 小节标题。\n", rules)
        self.assertEqual(findings[0]["kind"], "HEADING")

    def test_findings_have_a_stable_key(self):
        rules = {"terminology": [["缓冲池", "缓冲区域"]]}
        findings = self.findings("# 标题\n\n缓冲池与缓冲区域并存。\n", rules)
        key = self.mod._key(findings[0])
        self.assertIn("TERM", key)

    def test_baseline_round_trip(self):
        path = os.path.join(self.tmp.name, "baseline.json")
        with mock.patch.object(self.mod, "baseline_path", lambda: path):
            self.assertEqual(self.mod.load_baseline(), set())
            self.mod.save_baseline(
                [{"file": "a.md", "line": 1, "kind": "TERM", "detail": "mixed spellings"}]
            )
            self.assertTrue(self.mod.load_baseline())
            self.assertEqual(self.mod.baseline_path(), path)

    def test_json_output_reports_findings(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.mod.main(["--json"])
        payload = json.loads(buffer.getvalue())
        self.assertIn(code, (0, 1))
        self.assertIn("findings", payload)




class StyleRulesCliTest(unittest.TestCase):
    """Bare-label headings, mixed list punctuation, baseline update and the exits."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(_fixture.build_book(self.tmp.name), "style_rules")

    def test_a_bare_label_heading_is_reported(self):
        found = self.mod._heading_findings(1, "注意", {"forbid_bare": ["注意"]})
        self.assertEqual(found, [("HEADING", "bare label heading: 注意")])

    def test_a_list_that_mixes_endings_is_one_finding(self):
        path = os.path.join(self.tmp.name, "ch1-test.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# 第1章\n\n- 第一项。\n- 第二项\n\n- 甲。\n- 乙。\n")
        with mock.patch.dict(self.mod.RULES, {"list_punctuation": "consistent"}):
            kinds = [item["kind"] for item in self.mod.check_file(path)]
        self.assertIn("LIST", kinds)

    def test_a_mixed_list_that_ends_the_file_is_still_one_finding(self):
        path = os.path.join(self.tmp.name, "ch1-tail.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# 第1章\n\n- 甲。\n- 乙")
        with mock.patch.dict(self.mod.RULES, {"list_punctuation": "consistent"}):
            found = [item for item in self.mod.check_file(path) if item["kind"] == "LIST"]
        self.assertEqual([item["detail"] for item in found], ["1 list(s) mix ending punctuation"])

    def test_updating_the_baseline_reports_the_path(self):
        path = os.path.join(self.tmp.name, "style-rules.json")
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "files", return_value=[]),
            mock.patch.object(self.mod, "save_baseline") as saved,
            mock.patch.object(self.mod, "baseline_path", lambda: path),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main(["--update-baseline"]), 0)
        saved.assert_called_once()
        self.assertIn("baseline updated", buffer.getvalue())

    def test_new_findings_are_listed_and_the_gate_exits_one(self):
        finding = {"file": "ch1-test.md", "line": 2, "kind": "TERM", "detail": "mixed"}
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "files", return_value=["ch1-test.md"]),
            mock.patch.object(self.mod, "check_file", return_value=[finding]),
            mock.patch.object(self.mod, "load_baseline", return_value=set()),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main([]), 1)
        self.assertIn("TERM", buffer.getvalue())

    def test_an_all_accepted_run_passes(self):
        finding = {"file": "ch1-test.md", "line": 2, "kind": "TERM", "detail": "mixed"}
        buffer = io.StringIO()
        with (
            mock.patch.object(self.mod, "files", return_value=["ch1-test.md"]),
            mock.patch.object(self.mod, "check_file", return_value=[finding]),
            mock.patch.object(self.mod, "load_baseline", return_value={self.mod._key(finding)}),
            redirect_stdout(buffer),
        ):
            self.assertEqual(self.mod.main([]), 0)
        self.assertIn("风格规则通过", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
