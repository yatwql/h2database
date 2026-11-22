#!/usr/bin/env python3
"""style.json schema: every rejection rule is proven by one mutation."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

REAL_STYLE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data', 'config', 'style.json')

class StyleSchemaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.module = _fixture.load_module(self.root, 'style_schema')
        with open(os.path.normpath(REAL_STYLE), encoding='utf-8') as fh:
            self.base = json.load(fh)

    def problems_after(self, mutate) -> list[str]:
        style = copy.deepcopy(self.base)
        mutate(style)
        return self.module.validate(style)

    def assert_problem(self, mutate, needle: str) -> None:
        problems = self.problems_after(mutate)
        self.assertTrue(any(needle in p for p in problems),
                        f'{needle!r} not in {problems}')

    # -- top level -------------------------------------------------------
    def test_unknown_top_level_key_is_rejected(self):
        self.assert_problem(lambda s: s.update(nope=1), 'unknown top-level keys')

    def test_missing_section_is_rejected(self):
        self.assert_problem(lambda s: s.pop('quality', None), '[quality] missing')

    def test_missing_required_field_is_rejected(self):
        self.assert_problem(lambda s: s['quality'].pop('min_chapter_lines', None),
                            '[quality].min_chapter_lines missing')

    # -- captions --------------------------------------------------------
    def test_missing_caption_preset_is_rejected(self):
        self.assert_problem(lambda s: s['captions']['presets'].pop('strict', None),
                            '[captions.presets].strict missing')

    def test_caption_preset_bounds_must_be_ordered(self):
        self.assert_problem(
            lambda s: s['captions']['presets']['strict'].update(min_chars=99, max_chars=1),
            'min_chars must be < max_chars')

    def test_caption_fail_at_must_be_non_negative(self):
        self.assert_problem(
            lambda s: s['captions']['presets']['strict'].update(fail_at=-1),
            'fail_at must be >= 0')

    # -- quality / prose -------------------------------------------------
    def test_chapter_line_bounds_must_be_ordered(self):
        self.assert_problem(
            lambda s: s['quality'].update(min_chapter_lines=900, max_chapter_lines=10),
            'min_chapter_lines must be < max_chapter_lines')

    def test_duplicate_ratio_must_be_a_percentage(self):
        self.assert_problem(lambda s: s['quality'].update(max_duplicate_ratio=300),
                            'max_duplicate_ratio must be within 0-100')

    def test_prose_anchor_pair_must_be_ordered(self):
        self.assert_problem(
            lambda s: s['prose'].update(avg_sentence_good=90, avg_sentence_bad=10),
            'must be <=')

    def test_prose_sections_must_be_defined(self):
        self.assert_problem(lambda s: s['prose'].update(sections=[]),
                            'sections must define body/caption/exercise')

    def test_composite_must_be_a_score(self):
        self.assert_problem(lambda s: s['prose'].update(min_composite=0),
                            'min_composite must be within (0, 100]')

    # -- style rules -----------------------------------------------------
    def test_style_rules_must_be_an_object(self):
        self.assert_problem(lambda s: s.update(style_rules=[]),
                            '[style_rules] missing or not an object')

    def test_terminology_groups_need_two_terms(self):
        self.assert_problem(lambda s: s['style_rules'].update(terminology=[['only-one']]),
                            'terminology must be a list of synonym groups')

    def test_banned_link_text_must_be_a_list(self):
        self.assert_problem(lambda s: s['style_rules'].update(banned_link_text='x'),
                            'banned_link_text must be a list')

    def test_heading_rules_must_be_an_object(self):
        self.assert_problem(lambda s: s['style_rules'].update(heading='off'),
                            '[style_rules].heading must be an object')

    # -- content depth ---------------------------------------------------
    def test_content_depth_must_be_an_object(self):
        self.assert_problem(lambda s: s.update(content_depth=[]),
                            '[content_depth] missing or not an object')

    def test_glossary_min_uses_must_be_positive(self):
        self.assert_problem(lambda s: s['content_depth'].update(glossary_min_uses=0),
                            'glossary_min_uses must be >= 1')

    def test_glossary_ignore_must_be_a_list(self):
        self.assert_problem(lambda s: s['content_depth'].update(glossary_ignore='x'),
                            'glossary_ignore must be a list')

    def test_excerpt_lines_must_be_an_int(self):
        self.assert_problem(lambda s: s['content_depth'].update(excerpt_lines='six'),
                            'excerpt_lines must be an int')

    # -- separation of document and config -------------------------------
    def test_prose_templates_are_rejected_in_style_json(self):
        self.assert_problem(
            lambda s: s['generation'].update(templates={'map_intro': '{pkgs}'}),
            'must not carry prose templates')

    def test_display_copy_is_rejected_in_style_json(self):
        self.assert_problem(lambda s: s.update(project={'title': 'x'}),
                            'must not carry display copy')

    # -- CLI -------------------------------------------------------------
    def test_main_reports_a_valid_file(self):
        _fixture.run_inproc(self.root, 'style_schema.py')
        code, out = _fixture.run_inproc(self.root, 'style_schema.py')
        self.assertEqual(code, 1, out[-300:])
        self.assertIn('must be a template string', out)
        self.assertTrue(out)

if __name__ == '__main__':
    unittest.main()
