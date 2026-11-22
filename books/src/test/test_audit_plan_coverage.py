#!/usr/bin/env python3
"""Plan coverage gate: every design directory has exactly one owner."""
from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest

import _fixture

TAGS = ('layer:audit', 'tier:fast')

_fixture.ensure_tools_path()

PLAN = """# 实施与维护计划
> **编号源**：`plan-next = 12`
## 概述
在办 2 项：P1 1 项（**plan-11**）、P2 1 项（**plan-4**）。
## 当前迭代待办
### P1 — 当前待办（立即执行）
#### `plan-11` 多书并行维护
**现状**：一件事。
**动作**：做它。
**验收**：判据。
**事实位**：设计与步骤在 `docs/plan/multi-book/plan.md`。
### P2 — 下一阶段就绪（条件满足即开工）
#### `plan-4` 语言包
**现状**：一件事。
**动作**：做它。
**验收**：判据。
**事实位**：见 `docs/plan/language-pack/design.md`。
## 待归档（已完成）
| 迭代目录 | 结论出处 |
| --- | --- |
| `docs/plan/figure-chapter-plumbing/` | `rf-35` |
"""


class PlanCoverageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        os.makedirs(os.path.join(self.tmp, 'managements'))
        for topic in ('multi-book', 'language-pack', 'figure-chapter-plumbing'):
            os.makedirs(os.path.join(self.tmp, 'plan', topic))
        self.write_plan(PLAN)
        self.mod = importlib.import_module('audit.plan_coverage')

    def write_plan(self, text: str) -> None:
        with open(os.path.join(self.tmp, 'managements', 'plan.md'), 'w', encoding='utf-8') as fh:
            fh.write(text)

    def check(self) -> list[str]:
        return self.mod.check(self.tmp)

    def test_a_consistent_plan_is_green(self):
        self.assertEqual(self.check(), [])

    def test_a_design_directory_nobody_claims_is_reported(self):
        os.makedirs(os.path.join(self.tmp, 'plan', 'orphan-topic'))
        problems = self.check()
        self.assertTrue(any('orphan-topic' in p and '没有计划项认领' in p for p in problems))

    def test_an_item_without_a_design_directory_is_reported(self):
        self.write_plan(PLAN.replace('设计与步骤在 `docs/plan/multi-book/plan.md`。', '还没想好。'))
        self.assertTrue(any('事实位没有指向' in p for p in self.check()))

    def test_a_missing_block_is_reported(self):
        self.write_plan(PLAN.replace('**验收**：判据。\n', '', 1))
        self.assertTrue(any('缺少' in p for p in self.check()))

    def test_blocks_out_of_order_are_reported(self):
        self.write_plan(PLAN.replace('**现状**：一件事。\n**动作**：做它。',
                                     '**动作**：做它。\n**现状**：一件事。', 1))
        self.assertTrue(any('顺序' in p for p in self.check()))

    def test_a_duplicate_identifier_is_reported(self):
        self.write_plan(PLAN.replace('`plan-4` 语言包', '`plan-11` 语言包', 1))
        self.assertTrue(any('编号重复' in p for p in self.check()))

    def test_a_stale_next_number_is_reported(self):
        self.write_plan(PLAN.replace('plan-next = 12', 'plan-next = 9', 1))
        self.assertTrue(any('plan-next' in p for p in self.check()))

    def test_a_wrong_overview_count_is_reported(self):
        self.write_plan(PLAN.replace('在办 2 项：P1 1 项（**plan-11**）、P2 1 项（**plan-4**）。',
                                     '在办 3 项：P1 1 项（**plan-11**）、P2 1 项（**plan-4**）。', 1))
        self.assertTrue(any('在办' in p for p in self.check()))

    def test_a_wrong_tier_breakdown_is_reported(self):
        self.write_plan(PLAN.replace('P2 1 项（**plan-4**）', 'P2 2 项（**plan-4**）', 1))
        self.assertTrue(any('分档数字' in p for p in self.check()))

    def test_a_directory_claimed_twice_is_reported(self):
        self.write_plan(PLAN.replace('| `docs/plan/figure-chapter-plumbing/` | `rf-35` |',
                                     '| `docs/plan/multi-book/` | `rf-35` |', 1))
        self.assertTrue(any('同时认领' in p for p in self.check()))

    def test_a_reference_to_a_missing_directory_is_reported(self):
        shutil.rmtree(os.path.join(self.tmp, 'plan', 'language-pack'))
        self.assertTrue(any('不存在的目录' in p for p in self.check()))

    def test_a_pending_row_for_a_missing_directory_is_reported(self):
        self.write_plan(PLAN.replace('`docs/plan/figure-chapter-plumbing/`',
                                     '`docs/plan/already-deleted/`', 1))
        self.assertTrue(any('待归档' in p and '不存在的目录' in p for p in self.check()))


if __name__ == '__main__':
    unittest.main()
