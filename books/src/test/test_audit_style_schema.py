#!/usr/bin/env python3
"""style.json schema: every rejection rule is proven by one mutation."""

from __future__ import annotations

import copy
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

REAL_STYLE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "config",
    "style.json",
)


class StyleSchemaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.module = _fixture.load_module(self.root, "style_schema")
        with open(os.path.normpath(REAL_STYLE), encoding="utf-8") as fh:
            self.base = json.load(fh)

    def problems_after(self, mutate) -> list[str]:
        style = copy.deepcopy(self.base)
        mutate(style)
        return self.module.validate(style)

    def assert_problem(self, mutate, needle: str) -> None:
        problems = self.problems_after(mutate)
        self.assertTrue(any(needle in p for p in problems), f"{needle!r} not in {problems}")

    # -- top level -------------------------------------------------------
    def test_unknown_top_level_key_is_rejected(self):
        self.assert_problem(lambda s: s.update(nope=1), "unknown top-level keys")

    def test_missing_section_is_rejected(self):
        self.assert_problem(lambda s: s.pop("quality", None), "[quality] missing")

    def test_missing_required_field_is_rejected(self):
        self.assert_problem(
            lambda s: s["quality"].pop("min_chapter_lines", None),
            "[quality].min_chapter_lines missing",
        )

    # -- captions --------------------------------------------------------
    def test_missing_caption_preset_is_rejected(self):
        self.assert_problem(
            lambda s: s["captions"]["presets"].pop("strict", None),
            "[captions.presets].strict missing",
        )

    def test_caption_preset_bounds_must_be_ordered(self):
        self.assert_problem(
            lambda s: s["captions"]["presets"]["strict"].update(min_chars=99, max_chars=1),
            "min_chars must be < max_chars",
        )

    def test_caption_fail_at_must_be_non_negative(self):
        self.assert_problem(
            lambda s: s["captions"]["presets"]["strict"].update(fail_at=-1), "fail_at must be >= 0"
        )

    # -- quality / prose -------------------------------------------------
    def test_chapter_line_bounds_must_be_ordered(self):
        self.assert_problem(
            lambda s: s["quality"].update(min_chapter_lines=900, max_chapter_lines=10),
            "min_chapter_lines must be < max_chapter_lines",
        )

    def test_duplicate_ratio_must_be_a_percentage(self):
        self.assert_problem(
            lambda s: s["quality"].update(max_duplicate_ratio=300),
            "max_duplicate_ratio must be within 0-100",
        )

    def test_prose_anchor_pair_must_be_ordered(self):
        self.assert_problem(
            lambda s: s["prose"].update(avg_sentence_good=90, avg_sentence_bad=10), "must be <="
        )

    def test_prose_sections_must_be_defined(self):
        self.assert_problem(
            lambda s: s["prose"].update(sections=[]), "sections must define body/caption/exercise"
        )

    def test_composite_must_be_a_score(self):
        self.assert_problem(
            lambda s: s["prose"].update(min_composite=0), "min_composite must be within (0, 100]"
        )

    # -- style rules -----------------------------------------------------
    def test_style_rules_must_be_an_object(self):
        self.assert_problem(
            lambda s: s.update(style_rules=[]), "[style_rules] missing or not an object"
        )

    def test_terminology_groups_need_two_terms(self):
        self.assert_problem(
            lambda s: s["style_rules"].update(terminology=[["only-one"]]),
            "terminology must be a list of synonym groups",
        )

    def test_banned_link_text_must_be_a_list(self):
        self.assert_problem(
            lambda s: s["style_rules"].update(banned_link_text="x"),
            "banned_link_text must be a list",
        )

    def test_heading_rules_must_be_an_object(self):
        self.assert_problem(
            lambda s: s["style_rules"].update(heading="off"),
            "[style_rules].heading must be an object",
        )

    # -- content depth ---------------------------------------------------
    def test_content_depth_must_be_an_object(self):
        self.assert_problem(
            lambda s: s.update(content_depth=[]), "[content_depth] missing or not an object"
        )

    def test_glossary_min_uses_must_be_positive(self):
        self.assert_problem(
            lambda s: s["content_depth"].update(glossary_min_uses=0),
            "glossary_min_uses must be >= 1",
        )

    def test_glossary_ignore_must_be_a_list(self):
        self.assert_problem(
            lambda s: s["content_depth"].update(glossary_ignore="x"),
            "glossary_ignore must be a list",
        )

    def test_excerpt_lines_must_be_an_int(self):
        self.assert_problem(
            lambda s: s["content_depth"].update(excerpt_lines="six"), "excerpt_lines must be an int"
        )

    # -- separation of document and config -------------------------------
    def test_prose_templates_are_rejected_in_style_json(self):
        self.assert_problem(
            lambda s: s["generation"].update(templates={"map_intro": "{pkgs}"}),
            "must not carry prose templates",
        )

    def test_display_copy_is_rejected_in_style_json(self):
        self.assert_problem(
            lambda s: s.update(project={"title": "x"}), "must not carry display copy"
        )

    # -- CLI -------------------------------------------------------------
    def test_main_reports_a_valid_file(self):
        _fixture.run_inproc(self.root, "style_schema.py")
        code, out = _fixture.run_inproc(self.root, "style_schema.py")
        self.assertEqual(code, 1, out[-300:])
        self.assertIn("must be a template string", out)




class StyleSchemaMessageTest(unittest.TestCase):
    """The three prose.sections messages, the unparsable file and the clean verdict."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(_fixture.build_book(self.tmp.name), "style_schema")

    def prose(self, **sections) -> dict:
        base = {
            "tone": "plain",
            "audience": "engineers",
            "sections": {
                "body": {"avg_sentence_good": 10, "avg_sentence_bad": 20},
                "caption": {"max_chars": 30},
                "exercise": {"min_items": 2},
            },
        }
        base["sections"].update(sections)
        return {"prose": base}

    def test_a_body_anchor_that_is_inverted_is_reported(self):
        style = self.prose(body={"avg_sentence_good": 30, "avg_sentence_bad": 20})
        problems = self.mod._check_prose(style)
        self.assertTrue(any("good must be <= bad" in p for p in problems), problems)

    def test_a_non_integer_caption_limit_is_reported(self):
        problems = self.mod._check_prose(self.prose(caption={"max_chars": "30"}))
        self.assertTrue(any("max_chars must be an int" in p for p in problems), problems)

    def test_an_exercise_floor_below_one_is_reported(self):
        problems = self.mod._check_prose(self.prose(exercise={"min_items": 0}))
        self.assertTrue(any("min_items must be >= 1" in p for p in problems), problems)

    def test_a_style_file_that_does_not_parse_exits_with_a_message(self):
        # _fsutil.read_text turns an unreadable file into a clean exit of its own,
        # so a broken document is the one failure left for load() to report
        path = self.mod._config.config_path("style.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('{"captions": ')
        with self.assertRaises(SystemExit) as raised:
            self.mod.load()
        self.assertIn("cannot read", str(raised.exception))

    def test_the_cli_reports_a_clean_file(self):
        buffer = io.StringIO()
        with mock.patch.object(self.mod, "validate", return_value=[]), redirect_stdout(buffer):
            self.assertEqual(self.mod.main([]), 0)
        self.assertIn("结构合规", buffer.getvalue())


class StyleSchemaTemplateAndLimitTest(unittest.TestCase):
    """The template library and the per-kind budgets, one rejection each."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mod = _fixture.load_module(_fixture.build_book(self.tmp.name), "style_schema")

    def test_an_unknown_prose_template_key_is_named(self):
        templates = dict(self.mod._config.templates())
        templates["bogus_intro"] = "x {name}"
        with mock.patch.object(self.mod._config, "templates", return_value=templates):
            problems = self.mod._check_templates({})
        self.assertIn("templates: unknown keys ['bogus_intro']", problems)

    def test_an_empty_template_library_does_not_ask_for_deep_dive(self):
        with mock.patch.object(self.mod._config, "templates", return_value={}):
            problems = self.mod._check_templates({})
        self.assertNotIn("templates.deep_dive must be a list of strings", problems)

    def test_a_limit_entry_that_is_not_a_mapping_is_named(self):
        self.assertEqual(
            self.mod._check_limits({"limits": {"prose": "80"}}), ["[limits].prose needs limit/warn"]
        )


if __name__ == "__main__":
    unittest.main()
