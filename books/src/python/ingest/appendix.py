#!/usr/bin/env python3
"""Appendix rendering: verified source coordinates plus exercises.

An appendix does not own packages; it presents the coordinates that back the
case studies and the questions that send the reader into them. Kept beside the
chapter renderer, in its own module, because the two grow for different reasons.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import _config, _mdutil

TYPE_EMOJI = ('🟢', '🔵', '🟠')

EXERCISE_BANK = (
    '用一句话说清本章最大包的边界，并指出它与相邻包的调用方向。',
    '挑一个公开入口方法，沿调用链说明它在哪里加锁、在哪里释放。',
    '如果要把本章的某个包拆成两个，你会沿哪条缝切，代价是什么？',
    '列举本章中两处用空间换时间的设计，并说明其收益与上限。',
    '找一个失败路径（异常或回滚），说明状态如何回退到一致。',
)

APPENDIX_SPEC = {
    name: (nums[0], f'附录 {chr(65 + index)} {((_config.chapter_titles().get(name) or [name])[0])}')
    for index, (name, nums) in enumerate(_config.chapter_numbering().items())
    if name.startswith('appendix-') and nums
}


def render_appendix(ch: dict, spec_table: dict | None = None) -> str:
    """Verified source-coordinate block appended to an appendix (idempotent)."""
    spec = (spec_table if spec_table is not None else APPENDIX_SPEC).get(ch['file'])
    if not spec:
        return ''
    num, heading = spec
    pkgs = sorted(ch['packages'].items(), key=lambda kv: -kv[1]['lines'])
    L = [f'## {num}.1 {heading}', '']
    if pkgs:
        L += [f'本节由源码清单生成，覆盖 {len(pkgs)} 个包，行号对应当前源码树。', '']
    else:
        L += [('本附录不拥有源码包，内容以跨章引用为主；'
              '各包的实现细节见对应主责章节。'), '']
    rows = []
    for _pkg, info in pkgs:
        for cls in info['key_classes'][:4]:
            rel = cls.get('rel') or ''
            api_lines = cls.get('api_lines') or {}
            if not rel:
                continue
            for api in cls.get('api', [])[:1]:
                lineno = api_lines.get(api)
                rows.append([f"`{cls['name']}.{api}()`",
                             f'`{rel}:{lineno}`' if lineno else f'`{rel}`'])
    L += _mdutil.table(['入口', '源码坐标'], rows) + ['',
          f'## {num}.2 延伸思考', '',
          '下列题目面向"用坐标串起一次完整调用"。', '']
    for i in range(4):
        emoji = TYPE_EMOJI[i % 3]
        stars = '★' * (i + 1)
        body = EXERCISE_BANK[(num + i) % len(EXERCISE_BANK)]
        L += [f'**{i + 1}. {emoji}{stars} {body}**', '',
              f'> 提示：先从 §{num}.1 的坐标表挑一个入口。',
              f'> 回顾：§{num}.1 {heading}', '']
    L += [f'## {num}.3 本章小结', '',
          f'- 本节给出 {len(rows)} 个可核验的源码坐标。',
          '- 上游升级后重新生成即可刷新行号。', '',
          f'## {num}.4 延展阅读', '',
          '- 详见第3章《包结构与模块职责》。', '']
    return '\n'.join(L)
