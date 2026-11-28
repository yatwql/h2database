#!/usr/bin/env python3
"""Section rendering above the single-package case: truncated maps, empty type
tables, chapters whose glossary hit nobody cites, and combined chapter files.

Each case feeds the renderer the facts a larger book produces — the branches no
fixture chapter reaches on its own.
"""

from __future__ import annotations

import tempfile
import unittest
from unittest import mock

import _fixture

TAGS = ("layer:ingest", "tier:fast")

_fixture.ensure_tools_path()


def package(lines: int, *, summary: str = "示例包", classes: int = 1) -> dict:
    """One package entry as the outline carries it."""
    return {
        "lines": lines,
        "files": 2,
        "summary": summary,
        "depends_on": {"org.example.core": 3},
        "key_classes": [
            {
                "name": f"Widget{index}",
                "lines": max(1, lines // 4),
                "public_methods": index + 1,
                "summary": "示例类型",
                "rel": f"org/example/Widget{index}.java",
                "api": ["run"],
                "api_lines": {"run": 8},
            }
            for index in range(classes)
        ],
    }


class SectionsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, "chapters")

    def ctx(self, cn: int, packages: dict) -> dict:
        ordered = sorted(packages.items(), key=lambda kv: -kv[1]["lines"])
        total = sum(info["lines"] for info in packages.values()) or 1
        return self.chapters._chapter_context(cn, packages, ordered, total)


class PackageMapTest(SectionsCase):
    def test_packages_past_the_table_limit_are_named_in_one_line(self):
        packages = {f"org.example.p{index:02d}": package(100 - index) for index in range(14)}
        with mock.patch.object(
            self.chapters,
            "_generation",
            return_value={"max_packages_per_table": 12, "max_classes_per_package": 1},
        ):
            text = "\n".join(self.chapters._map_sections(2, packages, self.ctx(2, packages)))
        self.assertIn("其余 2 个包规模较小", text)
        self.assertIn("`org.example.p13`", text)

    def test_a_package_without_key_classes_gets_no_type_table(self):
        packages = {
            "org.example.rich": package(300, classes=2),
            "org.example.bare": {**package(10), "key_classes": []},
        }
        with mock.patch.object(
            self.chapters, "_generation", return_value={"max_classes_per_package": 1}
        ):
            text = "\n".join(self.chapters._map_sections(1, packages, self.ctx(1, packages)))
        self.assertIn("### 1.2.1 `org.example.rich`", text)
        self.assertNotIn("### 1.2.2", text)


class TermBlockTest(SectionsCase):
    def test_a_chapter_no_glossary_entry_cites_keeps_the_plain_summary_number(self):
        packages = {"org.example": package(50, summary="与术语无关的包")}
        terms, cn_summary = self.chapters._term_sections(9, packages, self.ctx(9, packages), 2)
        self.assertEqual(terms, [])
        self.assertEqual(cn_summary, 4)

    def test_a_cited_term_already_seen_in_the_prose_is_not_listed_twice(self):
        packages = {"org.example": package(50, summary="ACID 事务的载体")}
        terms, cn_summary = self.chapters._term_sections(1, packages, self.ctx(1, packages), 2)
        bullets = [line for line in terms if line.startswith("- **ACID**")]
        self.assertEqual(len(bullets), 1)
        self.assertEqual(cn_summary, 5)


class DeepDiveTemplateTest(SectionsCase):
    def test_a_template_list_drives_the_deep_reading_block(self):
        packages = {"org.example": package(80)}
        with mock.patch.object(
            self.chapters, "_templates", return_value={"deep_dive": ["- 深读 `{top}`（{share}%）"]}
        ):
            text = "\n".join(self.chapters._deep_dive_sections(1, self.ctx(1, packages), 2))
        self.assertIn("## 1.4 深读要点", text)
        self.assertIn("- 深读 `org.example`（100%）", text)

    def test_an_unknown_template_key_stays_literal(self):
        packages = {"org.example": package(80)}
        with mock.patch.object(
            self.chapters, "_templates", return_value={"deep_dive": ["- {not_a_fact}"]}
        ):
            text = "\n".join(self.chapters._deep_dive_sections(1, self.ctx(1, packages), 2))
        self.assertIn("- {not_a_fact}", text)


class CombinedChapterFileTest(SectionsCase):
    """One file, two chapter numbers: packages split, titles cross-referenced."""

    def setUp(self):
        super().setUp()
        self.spec = {"ch2-test.md": [(3, "上半章"), (4, "下半章")]}
        patcher = mock.patch.dict(self.chapters.CHAPTER_SPEC, self.spec, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def chapter(self, packages: dict) -> dict:
        return {"file": "ch2-test.md", "source_lines": 400, "packages": packages}

    def test_packages_are_split_across_the_numbers_he_spec_names(self):
        packages = {"org.example.a": package(300), "org.example.b": package(100)}
        text = self.chapters.render_chapter(self.chapter(packages))
        self.assertIn("# 第3章 上半章", text)
        self.assertIn("# 第4章 下半章", text)
        self.assertIn("详见第4章", text)

    def test_a_leading_paragraph_without_the_quote_mark_still_reads_as_a_note(self):
        with mock.patch.object(self.chapters, "prose", return_value="导读只有一句话。"):
            text = self.chapters.render_chapter(self.chapter({"org.example.a": package(50)}))
        self.assertIn("> **本章导读**：导读只有一句话。", text)

    def test_an_unknown_chapter_file_renders_nothing(self):
        self.assertEqual(
            self.chapters.render_chapter(
                {"file": "ch9-unknown.md", "source_lines": 1, "packages": {}}
            ),
            "",
        )


class ApiSectionTest(SectionsCase):
    def api_text(self, packages: dict) -> str:
        return "\n".join(self.chapters._api_sections(1, self.ctx(1, packages)))

    def test_a_class_without_a_source_file_is_left_out_of_the_entry_table(self):
        packages = {"org.example": package(80)}
        packages["org.example"]["key_classes"][0]["rel"] = ""
        text = self.api_text(packages)
        self.assertNotIn("Widget0.run()", text)
        self.assertIn("`org/example/...`", text)

    def test_an_entry_without_a_line_number_keeps_the_file_coordinate(self):
        packages = {"org.example": package(80)}
        packages["org.example"]["key_classes"][0]["api_lines"] = {}
        text = self.api_text(packages)
        self.assertIn("`Widget0.run()`", text)
        self.assertIn("`org/example/Widget0.java`", text)
        # no line number means no row in the coordinate appendix
        self.assertNotIn("源码坐标明细", text)


class ProseCleanupTest(SectionsCase):
    def test_marker_only_lines_do_not_join_the_paragraph(self):
        reply = ">\n本章先看目录结构，再看两条调用链之间的关系与边界。"
        with mock.patch("lib._llm.complete", return_value=reply):
            text = self.chapters.prose("lead", "备用句子", enabled=True)
        self.assertEqual(text, "本章先看目录结构，再看两条调用链之间的关系与边界。")


if __name__ == "__main__":
    unittest.main()
