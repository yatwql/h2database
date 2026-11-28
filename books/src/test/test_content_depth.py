#!/usr/bin/env python3
"""Tests for the content-depth checks (prereq / glossary / excerpt / exercise)."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import _fixture

TAGS = ("layer:infra", "tier:fast")

TOOLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, "lib"))


class DepthCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def module(self):
        return _fixture.load_module(self.root, "content_depth")

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path


class TestPrerequisites(DepthCase):
    def test_forward_reference_needs_signpost(self):
        depth = self.module()
        owners = {"WidgetEngine": [2]}
        path = self.write(
            "manuscript/ch1-test.md", "# 第1章 测试\n\n调用 `WidgetEngine` 完成工作。\n"
        )
        self.assertTrue(depth.check_prerequisites(path, 1, owners))

    def test_signposted_reference_is_fine(self):
        depth = self.module()
        owners = {"WidgetEngine": [2]}
        path = self.write(
            "manuscript/ch1-test.md",
            "# 第1章 测试\n\n调用 `WidgetEngine`（详见第2章《测试章节》）。\n",
        )
        self.assertFalse(depth.check_prerequisites(path, 1, owners))


class TestGlossary(DepthCase):
    def test_repeated_type_without_entry_is_reported(self):
        depth = self.module()
        self.write("manuscript/back/glossary.md", "# 术语表\n\n## A\n\n- **Other**: x\n")
        path = self.write("manuscript/ch1-test.md", "WidgetEngine WidgetEngine\n")
        findings = depth.check_glossary([path], min_uses=2, ignore=set())
        self.assertTrue(any("WidgetEngine" in item["detail"] for item in findings))

    def test_ignored_names_are_skipped(self):
        depth = self.module()
        self.write("manuscript/back/glossary.md", "# 术语表\n\n## A\n\n- **Other**: x\n")
        path = self.write("manuscript/ch1-test.md", "WidgetEngine WidgetEngine\n")
        self.assertEqual(depth.check_glossary([path], min_uses=2, ignore={"WidgetEngine"}), [])


class TestExercises(DepthCase):
    def test_exercise_without_anchor_or_type_is_reported(self):
        depth = self.module()
        owners = {"WidgetEngine": [1]}
        body = "# 第1章 测试\n\n## 1.9 延伸思考\n\n**1. 🟢★ 说说你的看法**\n\n> 提示：随便谈谈\n"
        path = self.write("manuscript/ch1-test.md", body)
        findings = depth.check_exercises([path], owners, {"ch1-test.md": [1]})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["kind"], "EXERCISE")

    def test_exercise_naming_a_type_passes(self):
        depth = self.module()
        owners = {"WidgetEngine": [1]}
        body = (
            "# 第1章 测试\n\n## 1.9 延伸思考\n\n"
            "**1. 🟢★ WidgetEngine 如何调度任务**\n\n> 提示：看实现\n"
        )
        path = self.write("manuscript/ch1-test.md", body)
        self.assertEqual(depth.check_exercises([path], owners, {"ch1-test.md": [1]}), [])


class TestWholeGate(DepthCase):
    def test_gate_runs_and_reports_json(self):
        code, out = _fixture.run_inproc(self.root, "content_depth.py", "--json")
        self.assertIn(code, (0, 1), out[-300:])
        payload = json.loads(out)
        self.assertIn("by_kind", payload)


class DepthSurfacesTest(DepthCase):
    """Owner mapping, the two exercise exemptions, and the two CLI outcomes."""

    def depth(self):
        return _fixture.load_module(self.root, "content_depth")

    def test_the_owner_map_comes_from_the_inventory_and_the_chapter_packages(self):
        self.write(
            "data/state/source-inventory.json",
            json.dumps(
                {
                    "packages": {
                        "pkg.core": {
                            "classes": [
                                {"name": "WidgetEngine", "rel": "pkg/core/WidgetEngine.java"}
                            ]
                        }
                    }
                }
            ),
        )
        depth = self.depth()
        with (
            mock.patch.object(
                depth._config, "chapter_packages", lambda: {"ch1-test.md": ["pkg.core"]}
            ),
            mock.patch.object(depth._config, "chapter_numbering", lambda: {"ch1-test.md": [1]}),
        ):
            self.assertEqual(depth.owner_map(), {"WidgetEngine": [1]})

    def test_an_exercise_with_a_forward_anchor_is_exempt(self):
        depth = self.depth()
        body = "# 第1章 测试\n\n## 1.9 延伸思考\n\n**1. 🟢★ 说说你的看法**\n\n> 提示：见 §2.1\n"
        path = self.write("manuscript/ch1-test.md", body)
        self.assertEqual(depth.check_exercises([path], {}, {"ch1-test.md": [1]}), [])

    def test_a_chapter_without_exercises_is_skipped(self):
        depth = self.depth()
        path = self.write("manuscript/ch1-test.md", "# 第1章 测试\n\n正文。\n")
        self.assertEqual(depth.check_exercises([path], {}, {"ch1-test.md": [1]}), [])

    def findings(self) -> list[dict]:
        return [
            {
                "file": "ch1-test.md",
                "line": 3,
                "kind": "GLOSSARY",
                "detail": "MVStore 没有术语条目",
            },
            {"file": "ch2-test.md", "line": 9, "kind": "EXERCISE", "detail": "练习没有指向"},
        ]

    def patched_gate(self, depth):
        return (
            mock.patch.object(depth, "check_prerequisites", return_value=[]),
            mock.patch.object(depth, "check_glossary", return_value=self.findings()),
            mock.patch.object(depth, "check_excerpts", return_value=[]),
            mock.patch.object(depth, "check_exercises", return_value=[]),
        )

    def test_updating_the_baseline_records_the_current_findings(self):
        depth = self.depth()
        patches = self.patched_gate(depth)
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        buffer = io.StringIO()
        with (
            mock.patch.object(
                depth._baseline, "save", return_value=os.path.join(self.root, "b.json")
            ),
            redirect_stdout(buffer),
        ):
            self.assertEqual(depth.main(["--update-baseline"]), 0)
        self.assertIn("内容深度基线已更新", buffer.getvalue())

    def test_the_report_counts_each_kind_and_lists_the_stale_entries(self):
        depth = self.depth()
        for patcher in self.patched_gate(depth):
            patcher.start()
            self.addCleanup(patcher.stop)
        buffer = io.StringIO()
        keys = {f"{item['file']}:{item['kind']}:{item['detail']}" for item in self.findings()}
        with (
            mock.patch.object(depth._baseline, "split", return_value=(keys, {"old-key"})),
            redirect_stdout(buffer),
        ):
            code = depth.main([])
        self.assertEqual(code, 1)
        text = buffer.getvalue()
        self.assertIn("GLOSSARY=1", text)
        self.assertIn("已不再出现", text)

    def test_a_book_without_a_baseline_prints_every_finding_and_no_stale_line(self):
        depth = self.depth()
        for patcher in self.patched_gate(depth):
            patcher.start()
            self.addCleanup(patcher.stop)
        buffer = io.StringIO()
        keys = {f"{item['file']}:{item['kind']}:{item['detail']}" for item in self.findings()}
        with (
            mock.patch.object(depth._baseline, "split", return_value=(keys, set())),
            redirect_stdout(buffer),
        ):
            code = depth.main([])
        text = buffer.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("ch2-test.md:9  [EXERCISE] 练习没有指向", text)
        self.assertNotIn("已不再出现", text)


class ExcerptSpanTest(unittest.TestCase):
    """A ranged excerpt promises a span; elisions must be marked, code must match."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.source = os.path.join(self.tmp.name, "src")
        os.makedirs(os.path.join(self.source, "org", "demo"), exist_ok=True)
        self.java = os.path.join(self.source, "org", "demo", "Thing.java")
        with open(self.java, "w", encoding="utf-8") as fh:
            fh.write("class Thing {\n"
                     "    int size;\n"
                     "    /** doc */\n"
                     "    int count;\n"
                     "    void run() {\n"
                     "        size++;\n"
                     "    }\n"
                     "}\n")
        self.chapter = os.path.join(self.root, "data", "manuscript", "ch1-test.md")

    def depth(self):
        module = _fixture.load_module(self.root, "content_depth")
        module._config.source_tree = lambda *_args: self.source
        return module

    def check(self, body: str):
        with open(self.chapter, "w", encoding="utf-8") as fh:
            fh.write("```java\n" + body + "```\n")
        return self.depth().check_excerpts([self.chapter])

    def test_a_span_that_matches_line_for_line_passes(self):
        body = ("// Thing.java:5-7\n"
                "void run() {\n        size++;\n    }\n")
        self.assertEqual(self.check(body), [])

    def test_a_changed_line_in_the_span_is_drift(self):
        body = ("// Thing.java:5-7\n"
                "void run() {\n        size += 2;\n    }\n")
        self.assertTrue(self.check(body))

    def test_an_elision_makes_the_body_a_subsequence(self):
        body = ("// Thing.java:1-8\n"
                "class Thing {\n    int size;\n// ...\n    int count;\n// ...\n"
                "    void run() {\n    }\n")
        self.assertEqual(self.check(body), [])

    def test_skipping_lines_without_an_elision_is_drift(self):
        body = ("// Thing.java:1-8\n"
                "class Thing {\n    int size;\n    int count;\n")
        self.assertTrue(self.check(body))

    def test_an_appended_annotation_does_not_count_as_a_change(self):
        body = ("// Thing.java:5-7\n"
                "void run() {   // 入口\n        size++;  // 自增\n    }\n")
        self.assertEqual(self.check(body), [])

    def test_a_line_outside_the_span_is_drift(self):
        body = ("// Thing.java:1-2\n"
                "class Thing {\n    int size;\n    void run() {\n")
        self.assertTrue(self.check(body))


    def test_an_elided_body_with_a_line_outside_the_span_is_drift(self):
        body = ("// Thing.java:1-8\n"
                "class Thing {\n// ...\n    void stop() {}\n")
        self.assertTrue(self.check(body))

    def test_a_line_that_carries_only_an_elision_matches_anything(self):
        module = _fixture.load_module(self.root, "content_depth")
        self.assertTrue(module._mdutil.excerpt_is_elision("// ..."))
        self.assertTrue(module._mdutil.excerpt_line_matches("int count;", "    int count;"))

    def test_a_trailing_blank_line_is_layout_not_source(self):
        body = ("// Thing.java:1-2\n"
                "class Thing {\n    int size;\n\n")
        self.assertEqual(self.check(body), [])

    def test_a_header_without_a_body_yields_no_excerpt(self):
        module = _fixture.load_module(self.root, "content_depth")
        self.assertEqual(module._excerpt_body(["// Thing.java:1"], 0), [])

    def test_a_blank_line_inside_the_span_is_not_drift(self):
        with open(self.java, "w", encoding="utf-8") as fh:
            fh.write("class Thing {\n    int size;\n\n    void run() {\n"
                     "        size++;\n    }\n}\n")
        body = ("// Thing.java:1-7\nclass Thing {\n    int size;\n\n"
                "    void run() {\n        size++;\n    }\n}\n")
        self.assertEqual(self.check(body), [])

if __name__ == "__main__":
    unittest.main()
