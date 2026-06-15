#!/usr/bin/env python3
"""
Case-study outline generator (v5.4 / U9).

Emits a narrative skeleton for one of three end-to-end appendix case studies,
chaining curated section anchors from the published H2 source-code analysis
chapters. Authors of U10 / U11 / U12 use the output as scaffolding before
fleshing out figures, code excerpts, and decision-point commentary.

Usage:
    python build_case_study_outline.py --scenario select
    python build_case_study_outline.py --scenario commit
    python build_case_study_outline.py --scenario recover

Each scenario is a curated pipeline of (component, anchor, decision_point)
tuples. The anchors are real H2/§X.Y sub-sections that exist in the published
chapter files; running the script merely linearises them into a writing
template — it does NOT verify anchor freshness. The pipeline is responsible
for that via final_check.py cross-reference checks.

Output is markdown ready to paste into appendix-a-case-studies.md as a draft.
"""
import argparse
import io
import sys

# Match the rest of the docs-stm tool chain: keep stdout pinned to UTF-8 so
# Chinese narrative output renders correctly when redirected on Windows
# consoles (gbk default), where bytes-to-stdout would mojibake otherwise.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)


# Each step is (component, anchor, decision_point). The anchor is shown in the
# narrative as `详见 §X.Y`, which is the cross-reference idiom enforced by
# final_check.py. Decision points are short prose hooks the author then
# expands with figures and source-code excerpts.
SCENARIOS: dict[str, list[tuple[str, str, str]]] = {
    'select': [
        ('JDBC 入口', '§7.1', 'JdbcStatement 如何拿到 SessionLocal 并通过 prepareCommand 进入引擎层'),
        ('Tokenizer 词法分析', '§3.4', '关键字识别 / 字符串字面量 / 标识符的边界处理'),
        ('Parser 递归下降', '§7.2', 'parseSelect 的状态转换与表达式优先级处理'),
        ('Prepared 编译缓存', '§7.4', 'CommandContainer 如何通过 schema 版本号判定重编译'),
        ('Optimizer 选择执行计划', '§8.1', 'canStop 终止条件与 Hybrid 策略的入口'),
        ('TableFilter 索引选择', '§8.4', 'IndexCondition 三类（EQUALITY/RANGE/SPATIAL）匹配规则'),
        ('B-Tree 路径查找', '§6.1', 'Counted B-Tree 的二分定位与叶节点定位'),
        ('Page / Chunk 加载', '§9.6', 'Page Pointer 解码与跨 Chunk 引用的命中路径'),
        ('LIRS 缓存命中', '§6.5', '热/冷队列在点查负载下的命中模式'),
        ('FileStore 物理读', '§9.1', '何时走 FileChannel.read，何时复用映射页'),
        ('Value 比较与回填', '§3.10', 'ValueInteger 与 SQL Long 的类型协调'),
        ('LocalResult 行打包', '§7.5', '单行结果集的零拷贝直返路径'),
        ('JDBC 返回 ResultSet', '§7.1', 'JdbcResultSet 的迭代与 close 的资源释放'),
    ],
    'commit': [
        ('Session.beginTransaction', '§7.1.5', '事务对象如何在 SessionLocal 上初始化并取得 transactionId'),
        ('TransactionStore 注册', '§4.5', 'OPEN 状态的写入与 Undo Log 的 MVMap 占位'),
        ('INSERT 写入', '§5.2', 'TransactionMap.put 在快照视图与底层 MVMap 之间的 CAS 协议'),
        ('Undo Log 累积', '§5.5', '每条 (transactionId, key, oldValue) 三元组的写时序'),
        ('UPDATE 路径', '§5.3', 'VersionedValue 的 committed/uncommitted 切换与冲突检测'),
        ('TxDecisionMaker 写冲突', '§10.4', 'first-committer-wins 策略与等待 vs 失败的判定'),
        ('COMMIT 触发', '§5.5', 'Session.commit 的入口、PREPARED 状态的可选阶段'),
        ('CommitDecisionMaker 扫描 Undo Log', '§5.5', '逐条记录的状态切换与可见性翻转的原子性保证'),
        ('RootReference CAS', '§10.5', '版本号 +1 的提交点；并发读事务的快照保留窗口'),
        ('BackgroundWriter 后台落盘', '§9.5', 'autoCommitDelay 与 Chunk 写入触发条件'),
        ('Chunk Footer 写入与 Fletcher-32', '§9.3', 'Chunk 完整性的最后一道闸门'),
        ('File Header 同步点更新', '§9.6', '双重备份的写入顺序与崩溃可恢复性'),
        ('Checkpoint 完成', '§9.5', '事务对外可见性的最终确认'),
    ],
    'recover': [
        ('崩溃发生', '§9.7', '触发条件：进程 SIGKILL / OS panic / 磁盘瞬断'),
        ('FileStore 重新打开', '§9.1', '文件锁获取与文件版本检查'),
        ('File Header 双副本读取', '§9.6', '哪一份是最新；如何处理两份都不完整的退化情形'),
        ('最新 Chunk 定位', '§9.3', 'Chunk Header 链遍历与版本号最大值的选取'),
        ('Chunk Footer 校验', '§9.3', 'Fletcher-32 失败时的回退：跳过最后一个 Chunk'),
        ('B-Tree 根重建', '§9.2', 'RootReference 还原与可见性快照重建'),
        ('Undo Log 扫描', '§9.7', '识别 OPEN / PREPARED 状态的事务'),
        ('未完成事务回滚', '§5.6', 'RollbackDecisionMaker 逐条逆序恢复 oldValue'),
        ('PREPARED 事务的处理策略', '§5.5', '是否回滚取决于事务协调器约定'),
        ('Free Space 重算', '§6.6', 'FreeSpaceBitSet 从 Chunk 链回放重建'),
        ('一致性检查', '§9.7', '可选的全表扫描 vs 按需懒检查'),
        ('对外开放写入', '§9.1', '恢复完成的标志：FileStore.openComplete'),
        ('异常分支：Chunk 校验失败', '§9.7', 'Recover 工具与 simulateCrash 的可重入路径'),
    ],
}


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
        out.append('<!-- TODO: 1-2 段叙述 + 1 张子流程图 + 关键源码片段 -->')
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
