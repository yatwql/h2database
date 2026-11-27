#!/usr/bin/env python3
"""The claims gate: a strong assertion must point at something checkable.

The gate is a ratchet over per-file counts, so every case here can fail: a sentence that
asserts and gives no evidence is found, the same sentence with a coordinate is not, and a
count that rises above the baseline fails the run.
"""

import io
import json
import os
import unittest
from contextlib import redirect_stdout

from _cases import FixtureCase

TAGS = ("layer:audit", "tier:fast")


class ClaimDetectionTest(FixtureCase):
    def sentence(self, text):
        claims = self.module("claims")
        return claims.has_evidence(text)

    def test_a_coordinate_symbol_or_class_counts_as_evidence(self):
        self.assertTrue(self.sentence("锁在 MVStore.java:120 处释放。"))
        self.assertTrue(self.sentence("这里调用 `MVMap.get()` 取得根引用。"))
        self.assertTrue(self.sentence("这一判断由 `TransactionStore` 负责。"))
        self.assertFalse(self.sentence("该行为永远是安全的。"))

    def test_a_strong_claim_without_evidence_is_reported(self):
        claims = self.module("claims")
        self.write(
            "data/manuscript/ch1-test.md",
            "# 第1章 测试章节\n\n这里总是先加锁再写入，读者不必怀疑。\n",
        )
        found = claims.findings()
        texts = [hit["text"] for hits in found.values() for hit in hits]
        self.assertTrue(any("总是" in text for text in texts), texts)

    def test_the_same_claim_with_its_coordinate_is_not_reported(self):
        claims = self.module("claims")
        self.write(
            "data/manuscript/ch1-test.md",
            "# 第1章 测试章节\n\n这里总是先加锁再写入（`SessionLocal.java:88`）。\n",
        )
        self.assertNotIn("ch1-test.md", claims.findings())

    def test_figure_leadins_tables_and_listings_are_not_prose(self):
        claims = self.module("claims")
        self.write(
            "data/manuscript/ch1-test.md",
            "# 第1章 测试章节\n\n"
            "如图 1-1 所示，该流程永远先校验参数。\n\n"
            "| 选项 | 说明 |\n| --- | --- |\n| 永远 | 总是 |\n\n"
            "```java\n// 总是加锁\n```\n",
        )
        self.assertNotIn("ch1-test.md", claims.findings())


class ClaimsRatchetTest(FixtureCase):
    def baseline(self):
        return os.path.join(self.root, "data", "baselines", "claims.json")

    def run_gate(self, *args):
        claims = self.module("claims")
        out = io.StringIO()
        with redirect_stdout(out):
            code = claims.main(list(args))
        return code, out.getvalue()

    def test_the_first_run_asks_for_a_baseline(self):
        self.write(
            "data/manuscript/ch1-test.md",
            "# 第1章 测试章节\n\n这里总要加锁。\n\n这条断言永远成立。\n",
        )
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("record today's count", out)

    def test_recording_then_repeating_is_green_and_a_rise_is_red(self):
        self.write("data/manuscript/ch1-test.md", "# 第1章 测试章节\n\n这条断言永远成立。\n")
        self.assertEqual(self.run_gate("--update-baseline")[0], 0)
        self.assertEqual(self.run_gate()[0], 0)
        self.write(
            "data/manuscript/ch1-test.md",
            "# 第1章 测试章节\n\n这条断言永远成立。\n\n另一条也必然成立。\n",
        )
        code, out = self.run_gate()
        self.assertEqual(code, 1)
        self.assertIn("baseline", out)

    def test_json_mode_carries_counts_regressions_and_findings(self):
        self.write("data/manuscript/ch1-test.md", "# 第1章 测试章节\n\n这条断言永远成立。\n")
        self.run_gate("--update-baseline")
        claims = self.module("claims")
        out = io.StringIO()
        with redirect_stdout(out):
            code = claims.main(["--json"])
        payload = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(payload["counts"]["total"], 1)
        self.assertIn("ch1-test.md", payload["findings"])

    def test_listing_names_the_file_line_and_sentence(self):
        self.write("data/manuscript/ch1-test.md", "# 第1章 测试章节\n\n这条断言永远成立。\n")
        self.run_gate("--update-baseline")
        code, out = self.run_gate("--list")
        self.assertEqual(code, 0)
        self.assertIn("ch1-test.md:3", out)
        self.assertIn("永远", out)


    def test_a_quoted_misconception_is_exempt_and_plain_prose_is_not(self):
        claims = self.module("claims")
        self.write("data/manuscript/ch1-test.md",
                   "# 第1章 测试章节\n\n- **误区**：这里永远不需要加锁。\n"
                   "  **为什么**：见 `MVTable.java:167` 的互斥。\n\n"
                   "这段正文则永远是错的，没有任何依据。\n")
        found = claims.findings()
        texts = [hit["text"] for hits in found.values() for hit in hits]
        self.assertFalse(any("误区" in text for text in texts), texts)
        self.assertTrue(any("这段正文" in text for text in texts), texts)


if __name__ == "__main__":
    unittest.main()
