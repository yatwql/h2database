#!/usr/bin/env python3
"""
Case-study outline generator.

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
import sys

from lib import _config, _errors, _fsutil

# Match the rest of the books tool chain: keep stdout pinned to UTF-8 so
# Chinese narrative output renders correctly when redirected on Windows
# consoles (gbk default), where bytes-to-stdout would mojibake otherwise.
_fsutil.pin_stdout_utf8()

# Each step is (component, anchor, decision_point). The anchor is shown in the
# narrative as `详见 §X.Y`, which is the cross-reference idiom enforced by
# structure.py. Decision points are short prose hooks the author then
# expands with figures and source-code excerpts.
def case_study_config() -> str:
    """Where this book keeps its case-study input, resolved when used."""
    return _config.book_path('case-studies.toml')


def load_scenarios() -> dict[str, list[tuple[str, str, str]]]:
    """Read the case-study pipelines from data/book/case-studies.toml.

    The file belongs to one book: a book without case studies simply has no such
    file. Callers treat an empty table as "nothing configured" rather than as a
    broken toolchain, so importing this module never requires the file.
    """
    import tomllib  # stdlib only from 3.11 on; imported where it is used

    try:
        with open(case_study_config(), 'rb') as fh:
            data = tomllib.load(fh)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f'error: invalid TOML in {case_study_config()}: {exc}') from exc
    out: dict[str, list[tuple[str, str, str]]] = {}
    for name, scenario in (data.get('scenarios') or {}).items():
        out[name] = [(step.get('component', ''), step.get('anchor', ''),
                      step.get('decision', '')) for step in scenario.get('steps', [])]
    return out


def scenarios() -> dict[str, list[tuple[str, str, str]]]:
    """The book's case-study pipelines, read when used (never at import)."""
    return load_scenarios()


def scenario_headers() -> dict[str, dict]:
    """Each scenario's appendix heading and opening prose, from the same file."""
    import tomllib

    try:
        with open(case_study_config(), "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return {str(name): dict(block) for name, block in (data.get("headers") or {}).items()}


def render(scenario: str) -> str:
    pipelines = scenarios()
    if scenario not in pipelines:
        raise ValueError(f"unknown scenario {scenario!r}; expected one of {list(pipelines)}")

    steps = pipelines[scenario]
    header = scenario_headers()[scenario]

    out = []
    out.append(header['heading'])
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
    parser.add_argument('--scenario', choices=sorted(scenarios()) or None, required=True,
                        help='which case study to scaffold')
    args = parser.parse_args()

    print(render(args.scenario))
    return 0

if __name__ == '__main__':
    sys.exit(_errors.run(main))
