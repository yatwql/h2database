#!/usr/bin/env python3
"""
Case-study outline generator (v5.4 / U9).

Emits a narrative skeleton for one of three end-to-end appendix case studies,
chaining curated section anchors from the published H2 source-code analysis
chapters. Authors of U10 / U11 / U12 use the output as scaffolding before
fleshing out figures, code excerpts, and decision-point commentary.

Usage:
    python case_studies.py --scenario select
    python case_studies.py --scenario commit
    python case_studies.py --scenario recover

Each scenario is a curated pipeline of (component, anchor, decision_point)
tuples. The anchors are real H2/§X.Y sub-sections that exist in the published
chapter files; running the script merely linearises them into a writing
template — it does NOT verify anchor freshness. The pipeline is responsible
for that via structure.py cross-reference checks.

Output is markdown ready to paste into appendix-a-case-studies.md as a draft.
"""

import os as _os
import sys as _sys

# make the shared package importable when the script runs standalone
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import os
import sys
import tomllib

from lib import _config, _fsutil

# Match the rest of the books tool chain: keep stdout pinned to UTF-8 so
# Chinese narrative output renders correctly when redirected on Windows
# consoles (gbk default), where bytes-to-stdout would mojibake otherwise.
_fsutil.pin_stdout_utf8()

# Each step is (component, anchor, decision_point). The anchor is shown in the
# narrative as `详见 §X.Y`, which is the cross-reference idiom enforced by
# structure.py. Decision points are short prose hooks the author then
# expands with figures and source-code excerpts.
CASE_STUDY_CONFIG = os.path.join(_config.BOOK_ROOT, 'data', 'tmpl', 'case-studies.toml')


def load_scenarios() -> dict[str, list[tuple[str, str, str]]]:
    """Read the case-study pipelines from data/tmpl/case-studies.toml."""
    try:
        with open(CASE_STUDY_CONFIG, 'rb') as fh:
            data = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise SystemExit(f'error: missing {CASE_STUDY_CONFIG}') from exc
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f'error: invalid TOML in {CASE_STUDY_CONFIG}: {exc}') from exc
    out: dict[str, list[tuple[str, str, str]]] = {}
    for name, scenario in (data.get('scenarios') or {}).items():
        out[name] = [(step.get('component', ''), step.get('anchor', ''),
                      step.get('decision', '')) for step in scenario.get('steps', [])]
    return out


SCENARIOS: dict[str, list[tuple[str, str, str]]] = load_scenarios()

SCENARIO_HEADERS = {
    'select': {
        'h2': '## A.1 案例 A：一条 SELECT 从 JDBC 到磁盘',
        'opening': (
            '当用户在应用代码中执行 `stmt.executeQuery("SELECT * FROM users WHERE id = 42")`，\n'
            '从 JDBC 入口到磁盘上的一行字节、再回到 ResultSet，全过程穿过 H2 的几乎\n'
            '所有核心子系统。本节以这条最基础的查询为线索，把分散在第3-9章的关键论述\n'
            '串接成一条单线叙事，每个步骤都给出 §X.Y 回指，便于读者按需深入。'
        ),
        'figure_prefix': 'A',
        'figure_start': 1,
    },
    'commit': {
        'h2': '## A.2 案例 B：一次 INSERT+UPDATE+COMMIT 事务的全链路',
        'opening': (
            '当用户在一个事务中执行 INSERT、紧接着 UPDATE、再 COMMIT，H2 在内存与磁盘\n'
            '上发生的事件比表面看起来要丰富得多——TransactionStore 状态迁移、Undo Log\n'
            '累积、MVCC 版本切换、CAS 提交点、后台 Chunk 落盘、Checkpoint 同步——\n'
            '每一环都有明确的不变量与失败可恢复点。本节把这条链路的关键决策点串起来。'
        ),
        'figure_prefix': 'A',
        'figure_start': 7,
    },
    'recover': {
        'h2': '## A.3 案例 C：一次崩溃后的恢复启动',
        'opening': (
            '进程崩溃发生在最不方便的时刻——某个 Chunk 写到一半、File Header 还指向旧位置——\n'
            '此时 H2 重新启动，必须在不丢已提交事务、不放过未提交事务的前提下，把存储\n'
            '状态恢复到一致点。本节按"打开文件 → 找到最新 Chunk → 重建可见性 → 决定哪些事务\n'
            '需要回滚 → 重新对外开放"的顺序展开，并在收尾处描述异常分支：Chunk 校验失败时\n'
            'H2 如何安全地降级。'
        ),
        'figure_prefix': 'A',
        'figure_start': 12,
    },
}

def render(scenario: str) -> str:
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}; expected one of {list(SCENARIOS)}")

    steps = SCENARIOS[scenario]
    header = SCENARIO_HEADERS[scenario]

    out = []
    out.append(header['h2'])
    out.append('')
    out.append(header['opening'])
    out.append('')
    out.append(f"> 本案例共 {len(steps)} 个流水线步骤，每步给出触发组件、关键决策点与原文回指。")
    out.append('')

    for idx, (component, anchor, decision) in enumerate(steps, start=1):
        out.append(f"### {scenario.upper()}.{idx} {component}")
        out.append('')
        out.append(f"**触发组件**：{component}")
        out.append('')
        out.append(f"**关键决策点**：{decision}")
        out.append('')
        out.append(f"**详见 {anchor}** — 原文给出完整源码路径与行号。")
        out.append('')
        out.append('<!-- 待补：1-2 段叙述 + 1 张子流程图 + 关键源码片段 -->')
        out.append('')

    out.append('### 思考小结')
    out.append('')
    out.append('1. 上述链路中，哪个环节的失败会被 H2 自动恢复？哪些会向调用方抛出异常？')
    out.append('2. 如果绕过 JDBC 直接调用引擎层 API，能省掉哪些步骤？为什么不建议这样做？')
    out.append('3. 在调试器里打哪些断点能完整复现这条链路？')
    out.append('')
    return '\n'.join(out)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=sorted(SCENARIOS), required=True,
                        help='which case study to scaffold')
    args = parser.parse_args()

    print(render(args.scenario))
    return 0

if __name__ == '__main__':
    sys.exit(main())
