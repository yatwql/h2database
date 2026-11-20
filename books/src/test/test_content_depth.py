#!/usr/bin/env python3
"""Tests for the content-depth checks (prereq / glossary / excerpt / exercise)."""

import json
import os
import sys
import tempfile
import unittest

import _fixture

TAGS = ('layer:infra', 'tier:fast')

TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'python'
)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.join(TOOLS_DIR, 'lib'))

class DepthCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = _fixture.build_book(self.tmp.name)

    def module(self):
        return _fixture.load_module(self.root, 'content_depth')

    def write(self, rel: str, text: str) -> str:
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
        return path

class TestPrerequisites(DepthCase):
    def test_forward_reference_needs_signpost(self):
        depth = self.module()
        owners = {'WidgetEngine': [2]}
        path = self.write('manuscript/ch1-test.md',
                          '# 第1章 测试\n\n调用 `WidgetEngine` 完成工作。\n')
        self.assertTrue(depth.check_prerequisites(path, 1, owners))

    def test_signposted_reference_is_fine(self):
        depth = self.module()
        owners = {'WidgetEngine': [2]}
        path = self.write('manuscript/ch1-test.md',
                          '# 第1章 测试\n\n调用 `WidgetEngine`（详见第2章《测试章节》）。\n')
        self.assertFalse(depth.check_prerequisites(path, 1, owners))

class TestGlossary(DepthCase):
    def test_repeated_type_without_entry_is_reported(self):
        depth = self.module()
        self.write('manuscript/back/glossary.md', '# 术语表\n\n## A\n\n- **Other**: x\n')
        path = self.write('manuscript/ch1-test.md', 'WidgetEngine WidgetEngine\n')
        findings = depth.check_glossary([path], min_uses=2, ignore=set())
        self.assertTrue(any('WidgetEngine' in item['detail'] for item in findings))

    def test_ignored_names_are_skipped(self):
        depth = self.module()
        self.write('manuscript/back/glossary.md', '# 术语表\n\n## A\n\n- **Other**: x\n')
        path = self.write('manuscript/ch1-test.md', 'WidgetEngine WidgetEngine\n')
        self.assertEqual(depth.check_glossary([path], min_uses=2,
                                              ignore={'WidgetEngine'}), [])

class TestExercises(DepthCase):
    def test_exercise_without_anchor_or_type_is_reported(self):
        depth = self.module()
        owners = {'WidgetEngine': [1]}
        body = ('# 第1章 测试\n\n## 1.9 延伸思考\n\n'
                '**1. 🟢★ 说说你的看法**\n\n> 提示：随便谈谈\n')
        path = self.write('manuscript/ch1-test.md', body)
        findings = depth.check_exercises([path], owners, {'ch1-test.md': [1]})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['kind'], 'EXERCISE')

    def test_exercise_naming_a_type_passes(self):
        depth = self.module()
        owners = {'WidgetEngine': [1]}
        body = ('# 第1章 测试\n\n## 1.9 延伸思考\n\n'
                '**1. 🟢★ WidgetEngine 如何调度任务**\n\n> 提示：看实现\n')
        path = self.write('manuscript/ch1-test.md', body)
        self.assertEqual(depth.check_exercises([path], owners, {'ch1-test.md': [1]}), [])

class TestWholeGate(DepthCase):
    def test_gate_runs_and_reports_json(self):
        code, out = _fixture.run_inproc(self.root, 'content_depth.py', '--json')
        self.assertIn(code, (0, 1), out[-300:])
        payload = json.loads(out)
        self.assertIn('by_kind', payload)

if __name__ == '__main__':
    unittest.main()
