#!/usr/bin/env python3
"""manuscript.terms: the parse shapes a clean glossary never produces.

A duplicated chapter reference, a second identical see-also link, an entry that
ends because the next line stopped being indented, a bold term the report must
skip because it is a caption — each is one line of the parser that only a
malformed or unusual glossary reaches.
"""

from __future__ import annotations

import os
import tempfile
import unittest

import _fixture

TAGS = ("layer:manuscript", "tier:fast")

_fixture.ensure_tools_path()


class TermsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.terms = _fixture.load_module(self.root, "terms")

    def glossary(self, text: str) -> str:
        path = os.path.join(self.root, "data", "manuscript", "back", "glossary.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def chapter(self, text: str, name: str = "ch1-test.md") -> None:
        path = os.path.join(self.root, "data", "manuscript", name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def book_terms(self, aliases: dict[str, str], skip: tuple[str, ...] = ()) -> None:
        """Write the book's glossary config: aliases plus the skip list."""
        lines = ["skip = [" + ", ".join(f'"{item}"' for item in skip) + "]", "", "[aliases]"]
        lines += [f'"{key}" = "{value}"' for key, value in aliases.items()]
        path = os.path.join(self.root, "data", "book", "glossary.toml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        self.terms = _fixture.load_module(self.root, "terms")


class ParseTermsTest(TermsCase):
    def test_one_entry_citing_a_chapter_twice_lists_it_once(self):
        path = self.glossary("- **ACID**: 事务特性。\n  **章节**：第1章 §1.1 与第1章 §1.2\n")
        self.assertEqual(self.terms.parse_glossary_terms(path), {"ACID": [1]})

    def test_a_line_that_loses_its_indent_ends_the_entry(self):
        path = self.glossary(
            "- **ACID**: 事务特性。\n  **章节**：第1章 §1.1\n这一行没有缩进，条目到此结束\n"
        )
        self.assertEqual(self.terms.parse_glossary_terms(path), {"ACID": [1]})

    def test_an_entry_left_open_at_the_end_of_the_file_is_still_returned(self):
        path = self.glossary("## A\n\n- **MVStore**: 存储引擎。\n  **章节**：第2章 §2.1\n")
        self.assertEqual(self.terms.parse_glossary_terms(path), {"MVStore": [2]})


class RelatedEntriesTest(TermsCase):
    def test_a_term_line_citing_one_chapter_twice_lists_it_once(self):
        path = self.glossary("- **ACID**: 事务特性。第1章、第1章\n")
        self.assertEqual(self.terms.parse_glossary_with_related(path)["ACID"]["chapters"], [1])

    def test_a_glossary_without_entries_has_nothing_to_close(self):
        path = self.glossary("## 术语表\n\n暂无。\n")
        self.assertEqual(self.terms.parse_glossary_with_related(path), {})

    def test_a_repeated_link_is_recorded_once_and_an_empty_one_is_dropped(self):
        path = self.glossary(
            "- **ACID**: 事务特性。\n  **章节**：第1章 §1.1 与第1章 §1.2\n"
            "  **相关**：[[MVStore]]、[[MVStore]]、[[]]\n"
            "条目在下一行结束\n"
            "- **MVStore**: 存储引擎。\n  **章节**：第2章 §2.1\n"
        )
        entries = self.terms.parse_glossary_with_related(path)
        self.assertEqual(entries["ACID"]["related"], ["MVStore"])
        self.assertEqual(entries["ACID"]["chapters"], [1])
        self.assertEqual(entries["MVStore"]["chapters"], [2])

    def test_a_link_that_only_matches_by_expansion_is_not_dangling(self):
        self.glossary(
            "- **COW / Copy-on-Write**: 写时复制。\n  **章节**：第1章 §1.1\n"
            "  **相关**：[[Copy-on-Write]]\n"
        )
        self.assertEqual(self.terms.check_related(), 0)

    def test_quiet_mode_still_counts_a_dangling_link(self):
        self.glossary(
            "- **ACID**: 事务特性。\n  **章节**：第1章 §1.1\n  **相关**：[[不存在的术语]]\n"
        )
        self.assertEqual(self.terms.check_related(verbose=False), 1)


class MissingTermReportTest(TermsCase):
    def test_aliases_captions_and_skip_terms_are_not_reported(self):
        self.book_terms({"写放大": "Write Amplification"}, skip=("关键字",))
        self.glossary("- **Write Amplification**: 写放大。\n  **章节**：第1章 §1.1\n")
        self.chapter("# 第1章 测试章节\n\n**写放大**\n**图 1-1 布局**\n**1.2 小节**\n**关键字**\n")
        self.assertEqual(self.terms.report_missing(), 0)

    def test_a_term_outside_the_glossary_is_reported_and_refused_in_check_mode(self):
        self.glossary("- **ACID**: 事务特性。\n  **章节**：第1章 §1.1\n")
        self.chapter("# 第1章 测试章节\n\n**PageSplit 布局**\n")
        self.assertEqual(self.terms.report_missing(), 1)
        with self.assertRaises(self.terms._errors.ToolError) as caught:
            self.terms.report_missing(check_mode=True)
        self.assertIn("missing term", caught.exception.message)


class WriteErrorTest(TermsCase):
    def test_a_directory_in_place_of_the_file_becomes_one_message(self):
        directory = os.path.join(self.root, "data", "manuscript", "back")
        with self.assertRaises(self.terms._errors.ToolError) as caught:
            self.terms._write_text(directory, "正文")
        self.assertIn("cannot write", caught.exception.message)


class CandidateRuleTest(TermsCase):
    def test_a_method_call_and_a_sql_keyword_are_not_terms(self):
        for term in ("run(arg)", "SELECT 语句"):
            with self.subTest(term=term):
                self.assertFalse(self.terms.is_glossary_candidate(term))

    def test_an_unclosed_call_reference_is_not_a_term(self):
        self.assertFalse(self.terms.is_glossary_candidate("append(元素"))


class GlossaryConfigTest(TermsCase):
    def test_a_broken_glossary_config_leaves_no_aliases_or_skips(self):
        path = os.path.join(self.root, "data", "book", "glossary.toml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("[aliases\n")
        self.terms = _fixture.load_module(self.root, "terms")
        self.assertEqual(self.terms.term_aliases(), {})
        self.assertEqual(self.terms.skip_terms(), frozenset())


if __name__ == "__main__":
    unittest.main()
