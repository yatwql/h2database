#!/usr/bin/env python3
"""The style detectors, one row per rule: a line that must trip it, a line that must not.

The gate as a whole is covered by the end-to-end tests; this table answers a
narrower question — does each detector still fire on its trigger, and does it
stay quiet on ordinary prose?
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:audit", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ("lib", "audit", "manuscript", "render", "ingest"):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

CLEAN = ["这一段说明存储层的写入顺序，先落盘再更新索引。"]


class DetectorTableTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        with redirect_stdout(io.StringIO()):
            self.style = _fixture.load_module(self.root, "style")

    def findings(self, detector, lines: list[str], name: str) -> int:
        self.style.chapter_stats.clear()
        detector(lines, name)
        entry = self.style.chapter_stats.get(name) or {}
        return len(entry.get("warnings") or []) + len(entry.get("infos") or [])

    def test_each_detector_fires_on_its_trigger_and_quiet_on_clean_prose(self):
        table = [
            (self.style.detect_redundant_adverbs, ["这项设计实际上是幂等的。"]),
            (self.style.detect_vague_modifiers, ["这条路径非常快。"]),
            (self.style.detect_long_sentences, ["字" * 220]),
            (
                self.style.detect_passive_abuse,
                ["数据被写入，锁被持有，页被刷出，索引被更新，事务被提交，状态被清理。"],
            ),
            (self.style.detect_excessive_de, ["的" * 30]),
        ]
        for detector, lines in table:
            with self.subTest(detector=detector.__name__):
                self.assertGreater(
                    self.findings(detector, lines, "trip.md"),
                    0,
                    f"{detector.__name__} missed its trigger",
                )
                self.assertEqual(
                    self.findings(detector, CLEAN, "clean.md"),
                    0,
                    f"{detector.__name__} fired on clean prose",
                )

    def test_fenced_code_is_never_judged(self):
        lines = ["```java", "实际上非常快" * 20, "```"]
        self.assertEqual(self.findings(self.style.detect_redundant_adverbs, lines, "f.md"), 0)

    def test_repeated_openings_are_reported(self):
        lines = ["本节说明 A。", "本节说明 B。", "本节说明 C。"]
        self.assertGreater(self.findings(self.style.detect_sentence_monotony, lines, "m.md"), 0)


class DetectorBucketTest(unittest.TestCase):
    """Levels, fenced blocks and the branches that keep a detector quiet."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        with redirect_stdout(io.StringIO()):
            self.style = _fixture.load_module(self.root, "style")
        self.style.chapter_stats.clear()

    def findings(self, detector, lines: list[str], name: str) -> int:
        self.style.chapter_stats.clear()
        detector(lines, name)
        entry = self.style.chapter_stats.get(name) or {}
        return len(entry.get("warnings") or []) + len(entry.get("infos") or [])

    def test_info_level_warnings_land_in_the_info_bucket(self):
        self.style.warn("x.md", 7, "模糊指代", level="INFO")
        entry = self.style.chapter_stats["x.md"]
        self.assertEqual(entry["infos"], [(7, "模糊指代")])
        self.assertEqual(entry["warnings"], [])

    def test_a_blank_paragraph_has_no_sentence_starts(self):
        self.assertEqual(self.style._sentence_starts(["   ", ""], [0, 1]), [])

    def test_a_repeated_connector_far_apart_is_tolerated(self):
        self.assertEqual(
            self.findings(
                self.style.detect_repeated_connectors, ["同时" + "字" * 60 + "同时这里"], "far.md"
            ),
            0,
        )

    def test_a_repeated_connector_close_together_is_reported(self):
        self.assertGreater(
            self.findings(self.style.detect_repeated_connectors, ["同时写入同时更新"], "near.md"), 0
        )

    def test_a_weak_verb_construction_is_reported(self):
        self.assertGreater(
            self.findings(self.style.detect_weak_verb_xing, ["我们对索引进行分析。"], "weak.md"), 0
        )

    def test_the_progress_form_is_not_a_weak_verb(self):
        self.assertEqual(
            self.findings(self.style.detect_weak_verb_xing, ["进行中的事务不阻塞读。"], "progress.md"), 0
        )

    def test_forbidden_phrases_are_reported_but_not_inside_quotes_or_fences(self):
        with mock.patch.object(self.style, "FORBID_PHRASES", ["说白了"]):
            self.assertGreater(
                self.findings(
                    self.style.detect_forbidden_phrases, ["说白了，这就是缓存。"], "p.md"
                ),
                0,
            )
            skipped = ["> 说白了", "# 说白了", "| 说白了 |", "```", "说白了", "```"]
            self.assertEqual(
                self.findings(self.style.detect_forbidden_phrases, skipped, "skip.md"), 0
            )

    def test_a_vague_pronoun_after_several_subjects_is_an_info(self):
        lines = ["缓存，索引，日志，", "其值由调用方决定。"]
        self.style.chapter_stats.clear()
        self.style.detect_vague_qi(lines, "qi.md")
        self.assertEqual(len(self.style.chapter_stats["qi.md"]["infos"]), 1)

    def test_colloquial_phrases_and_mixed_code_are_reported(self):
        self.assertGreater(
            self.findings(self.style.detect_colloquial, ["众所周知，刷盘先于提交。"], "c.md"), 0
        )
        self.assertGreater(
            self.findings(self.style.detect_mixed_code, ["见 `BTree 写入` 一节。"], "m.md"), 0
        )

    def test_the_script_prints_the_warning_report_and_the_summary(self):
        path = os.path.join(self.root, "data", "manuscript", "ch1-test.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# 第1章 测试章节\n\n众所周知，刷盘先于提交。\n")
        code, out = _fixture.run_inproc(self.root, "style.py")
        self.assertIn(code, (0, 1), out[-300:])
        self.assertIn("Summary by type", out)
        self.assertIn("WARN", out)


if __name__ == "__main__":
    unittest.main()
