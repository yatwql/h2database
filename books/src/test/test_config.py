#!/usr/bin/env python3
"""Tests for the book's single source of truth (books/book.toml + _config)."""

import importlib
import os
import sys
import unittest

TAGS = ('layer:infra', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
    for _sub in ('lib', 'audit', 'manuscript', 'render', 'ingest'):
        _path = os.path.join(TOOLS_DIR, _sub)
        if _path not in sys.path:
            sys.path.insert(0, _path)

_config = importlib.import_module('lib._config')

class TestConfigStructure(unittest.TestCase):
    def test_config_file_exists(self):
        self.assertTrue(os.path.isfile(_config.CONFIG_PATH), _config.CONFIG_PATH)

    def test_book_metadata(self):
        self.assertTrue(_config.TITLE)
        self.assertTrue(_config.VERSION)
        self.assertTrue(_config.MERGED_NAME)

    def test_directories_exist(self):
        self.assertTrue(os.path.isdir(_config.MANUSCRIPT_DIR), _config.MANUSCRIPT_DIR)
        self.assertTrue(os.path.isdir(_config.DIST_DIR), _config.DIST_DIR)

class TestChapters(unittest.TestCase):
    def test_no_missing_chapter_files(self):
        missing = _config.missing_files()
        self.assertEqual(missing, [], f'book.toml lists non-existent files: {missing}')

    def test_no_duplicate_chapters(self):
        names = _config.chapter_names()
        self.assertEqual(len(names), len(set(names)), 'duplicate chapter entries')

    def test_cover_is_first(self):
        self.assertEqual(_config.chapter_names()[0], 'cover.md')

    def test_every_chapter_is_markdown(self):
        for path in _config.chapter_files():
            self.assertTrue(path.endswith('.md'), path)

    def test_front_and_back_matter_present(self):
        self.assertTrue(_config.front_matter(), 'front_glob matched nothing')
        self.assertTrue(_config.back_matter(), 'back_glob matched nothing')

    def test_all_manuscript_files_order(self):
        files = _config.all_manuscript_files()
        front = _config.front_matter()
        back = _config.back_matter()
        self.assertEqual(files[:len(front)], front)
        self.assertEqual(files[-len(back):], back)

    def test_glossary_and_index_resolve(self):
        self.assertTrue(os.path.isfile(_config.glossary_path()))
        self.assertTrue(os.path.isfile(_config.index_path()))

class TestArtifacts(unittest.TestCase):
    def test_artifacts_live_in_dist(self):
        for path in (
            _config.merged_md(), _config.merged_html(), _config.merged_pdf(),
            _config.merged_epub(), _config.merged_print_pdf(),
        ):
            self.assertEqual(os.path.dirname(path), _config.DIST_DIR, path)

    def test_artifact_names_share_prefix(self):
        for path in (_config.merged_html(), _config.merged_pdf(), _config.merged_epub()):
            self.assertTrue(os.path.basename(path).startswith(_config.MERGED_NAME))

class TestThresholds(unittest.TestCase):
    def test_thresholds_positive(self):
        for key in ('ascii_max_cols', 'pdf_max_mb', 'epub_max_mb',
                    'exercises_min_per_chapter', 'exercises_min_total',
                    'index_main_min', 'index_sub_min', 'index_see_also_min'):
            self.assertGreater(_config.THRESHOLDS[key], 0, key)

    def test_caption_presets_sane(self):
        presets = _config.CAPTIONS['presets']
        for name in ('strict', 'normal', 'loose'):
            preset = presets[name]
            self.assertLess(preset['min_chars'], preset['max_chars'], name)

    def test_caption_vocabulary_present(self):
        self.assertTrue(_config.CAPTIONS['leading_verbs'])
        self.assertTrue(_config.CAPTIONS['vague_trailing'])

    def test_policy_sources_and_baselines(self):
        self.assertTrue(os.path.isdir(_config.source_tree('src_main')))
        self.assertTrue(_config.baseline_path('ascii').endswith('.json'))

    def test_required_sections_declared(self):
        self.assertIn('本章小结', _config.REQUIRED_SECTIONS)
        self.assertIn('延伸思考', _config.REQUIRED_SECTIONS)

if __name__ == '__main__':
    unittest.main()
