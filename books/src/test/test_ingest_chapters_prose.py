#!/usr/bin/env python3
"""Chapter prose: deterministic by default, LLM-drafted only on request."""

from __future__ import annotations

import importlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import _fixture

TAGS = ('layer:ingest', 'tier:fast')

_fixture.ensure_tools_path()

def _load(root: str):
    """Load chapters + the LLM layer against the fixture, not the real book."""
    chapters = _fixture.load_module(root, 'chapters')
    llm = importlib.import_module('lib._llm')
    return chapters, llm

class ProseSwitchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters, self.llm = _load(self.root)
        self.calls: list[str] = []
        self.reply = '本章围绕核心包展开，先建立整体印象再看具体实现。'
        self.complete = mock.patch.object(
            self.llm, 'complete',
            side_effect=lambda prompt, scenario='chapter-draft', **kw: (
                self.calls.append(scenario) or self.reply))
        self.complete.start()
        self.addCleanup(self.complete.stop)

    def test_deterministic_text_is_used_when_the_switch_is_off(self):
        self.assertEqual(self.chapters.prose('lead', '确定性导读', enabled=False, pkgs=3),
                         '确定性导读')
        self.assertEqual(self.calls, [])

    def test_llm_text_replaces_the_fallback_when_enabled(self):
        self.assertEqual(self.chapters.prose('lead', '确定性导读', enabled=True, pkgs=3),
                         self.reply)
        self.assertEqual(self.calls, ['chapter-draft'])

    def test_summary_uses_the_summary_scenario(self):
        self.chapters.prose('summary', '确定性小结', enabled=True, pkgs=3, lines='100',
                       top='org.x')
        self.assertEqual(self.calls, ['summary'])

    def test_provider_failure_falls_back_with_a_warning(self):
        with mock.patch.object(self.llm, 'complete',
                               side_effect=self.llm.LLMError('down')):
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(self.chapters.prose('lead', '确定性导读', enabled=True),
                                 '确定性导读')
        self.assertIn('LLM prose unavailable', err.getvalue())

    def test_structure_markers_are_stripped_from_provider_text(self):
        self.reply = '## 标题\n- 要点一\n```java\ncode();\n```\n本章讲清了包的边界与协作。'
        text = self.chapters.prose('lead', 'fallback', enabled=True)
        for marker in ('##', '- ', '```', 'java'):
            self.assertNotIn(marker, text)

    def test_too_short_provider_text_falls_back(self):
        self.reply = '短'
        self.assertEqual(self.chapters.prose('lead', '确定性导读', enabled=True),
                         '确定性导读')

    def test_long_provider_text_is_capped(self):
        self.reply = '本章内容具体而连贯。' * 60
        self.assertLessEqual(
            len(self.chapters.prose('lead', 'fallback', enabled=True)),
            self.chapters.PROSE_LIMIT)

class ProsePromptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters, _llm = _load(self.root)

    def test_lead_prompt_carries_the_facts(self):
        prompt = self.chapters._prose_prompt('lead', {'pkgs': 4, 'lines': '1,200', 'title': '存储'})
        self.assertIn('4 个包', prompt)
        self.assertIn('1,200 行', prompt)
        self.assertIn('存储', prompt)

    def test_summary_prompt_names_the_main_package(self):
        prompt = self.chapters._prose_prompt('summary', {'pkgs': 2, 'lines': '80', 'top': 'org.x.core'})
        self.assertIn('org.x.core', prompt)

class IngestSwitchConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def test_config_toggle_defaults_to_off(self):
        config = _fixture.load_module(self.root, '_config')
        self.assertFalse(config.llm_ingest_prose())

    def test_config_toggle_is_read_from_book_toml(self):
        path = os.path.join(self.root, 'data', 'book', 'book.toml')
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text.replace('[llm]', '[llm]\ningest_prose = true', 1))
        config = _fixture.load_module(self.root, '_config')
        self.assertTrue(config.llm_ingest_prose())

class OverwriteGuardTest(unittest.TestCase):
    """An ingest run never trades written prose for a fresh skeleton."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.chapters = _fixture.load_module(
            os.path.dirname(os.path.dirname(_fixture.TOOLS_DIR)), 'chapters')

    def chapter(self, body: str) -> str:
        path = os.path.join(self.tmp.name, 'ch1-test.md')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(body)
        return path

    def test_written_prose_is_not_replaced_by_a_skeleton(self):
        path = self.chapter('# 第1章 测试\n\n这里是人写好的正文。\n')
        self.assertFalse(self.chapters.rewrite_allowed(path, '# 第1章 新骨架\n', False))

    def test_force_is_what_overwrites(self):
        path = self.chapter('# 第1章 旧骨架\n')
        self.assertTrue(self.chapters.rewrite_allowed(path, '# 第1章 新骨架\n', True))

    def test_identical_text_may_be_rewritten(self):
        path = self.chapter('# 第1章 测试\n')
        self.assertTrue(self.chapters.rewrite_allowed(path, '# 第1章 测试\n', False))

    def test_a_missing_file_is_written(self):
        self.assertTrue(self.chapters.rewrite_allowed(
            os.path.join(self.tmp.name, 'absent.md'), 'x', False))


class LlmSkipNoticeTest(unittest.TestCase):
    """A run that writes nothing says why the provider was never used."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)
        self.chapters = _fixture.load_module(self.root, 'chapters')
        state = os.path.join(self.root, 'data', 'state')
        os.makedirs(state, exist_ok=True)
        chapter = {'file': 'ch1-test.md', 'source_lines': 10, 'packages': {}}
        with open(os.path.join(state, 'source-inventory.json'), 'w', encoding='utf-8') as fh:
            json.dump({'packages': {}}, fh)
        with open(os.path.join(state, 'outline.json'), 'w', encoding='utf-8') as fh:
            json.dump({'chapters': [chapter]}, fh)

    def test_a_skip_only_llm_run_says_so_before_scanning(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.chapters.main(['--llm'])
        text = buffer.getvalue()
        self.assertEqual(code, 0)
        # the answer arrives before the source scan, which is what took minutes
        self.assertIn('本轮不会生成或重写任何章节', text)
        self.assertIn('--force', text)

    def test_a_deterministic_run_stays_quiet_about_the_provider(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.chapters.main([])
        self.assertNotIn('LLM 未介入', buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
