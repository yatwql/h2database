> 涵盖版本：0.1
> 归档时间：2026-11-25

# H2 Database 源码分析 — 实施计划（0.1 归档）

> 版本：0.1
> 最后更新：2026-06-15

---

## 1. 当前状态

文档已发布 0.1 工业级技术书籍质量里程碑，并在 0.1 扩展了 EPUB 交付形态：

- 12 章 + 5 附录已交付（A 端到端案例研究、B 源码版本变更说明、C 术语表、D 概念索引、E 参考文献）。
- 正式源码、管理文档与交付工具统一位于 `books/`。
- 标准 MD/HTML 验证链路通过；PDF / 印刷级 PDF / EPUB 按需生成。
- 全部历史审查问题均在 `books/docs/managements/review-findings.md` 中关闭（第 7 轮含 R7-1..R7-17 与 R8-1）。

具体统计（行数、图数、术语表/索引条目数、工具脚本数）以 `books/cover.md` 自动更新结果与 `books/src/python/final_check.py` 输出为准，本文件不再重复维护数字。

## 2. 正式目录

```text
books/
  cover.md
  front/                          # 书籍前件（preface, copyright, how-to-read）
  ch1-2-architecture.md
  ch3-packages.md
  ch4-5-modules-processes.md
  ch6-1-data-structures.md
  ch6-2-storage-algorithms.md
  ch6-3-query-algorithms.md
  ch7-sql-execution.md
  ch8-query-optimizer.md
  ch9-10-persistence-locking.md
  ch11-12-guide-summary.md
  appendix-a-case-studies.md      # 附录 A
  appendix-b-version-changes.md   # 附录 B
  back/glossary.md                # 附录 C 术语表
  back/index.md                   # 附录 D 概念索引
  back/references.md              # 附录 E 参考文献
  management/                     # 管理文档（README, requirements, plan, testplan, changelog, review-findings, style-guide, baseline-*.json）
  plan/                           # 阶段性实施计划（版本路线、详细 PRD/任务清单）
  h2-source-code-analysis.md      # 合并 Markdown 交付物
  tools/                          # 正式生成、审计与验证脚本
```

## 3. 验证流程

标准验证流程与 PDF 交付命令详见 `books/docs/managements/testplan.md` 第 1 节。本章节不重复维护命令清单。

## 5. 管理文档职责

管理文档职责分配见 `books/docs/managements/README.md` 与项目根 `CLAUDE.md` 的「Management Document Authority」节。核心原则：同一事实只维护在一个权威位置。

## 6. 维护策略

- 发现新问题时先登记到 `books/docs/managements/review-findings.md`，修复完成后同步记录到 `books/docs/managements/changelog.md`。
- 不保留一次性修复脚本、临时压缩包、`__pycache__` 或外部 session 文件。
- 本项目 session 文件只保留在仓库 `.claude/` 目录中。
- 建议在 H2 上游版本升级或源码大改后，运行 `python books/src/python/source_freshness_check.py` 检查源码引用保鲜状态。

## 7. 后续增强项

| 特性 | 说明 | 优先级 |
|------|------|--------|
| API 文档索引 | 从 javadoc 或源码生成关键类速查表 | P3 |
| 交互式图表 | 评估将部分 ASCII 图迁移为 Mermaid/HTML 交互图 | P3 |
| 英文版本 | 翻译为英文版 | P4 |
| CI 集成 | 将标准验证链路接入 GitHub Actions | P4 |

## 8. 风险与应对

| 风险 | 应对 |
|------|------|
| 源文件与合并文档不同步 | 运行 `rebuild_merged.py` 和 `final_check.py` |
| 统计数据漂移 | 先运行 `cover_stats.py`，统计以 cover/final_check 为准 |
| HTML TOC 或围栏状态回归 | 运行 `generate_html.py` 和 `final_check.py` |
| PDF 大纲/目录失效 | 正式交付前运行 PDF 三步验证 |
| 管理文档重复维护导致冲突 | 保持职责分离，删除重复段落，使用交叉引用 |

## 9. 当前在建项：源码重分析 → 手稿重生成

上游源码更新（H2 2.5.259-SNAPSHOT，843 个 Java 文件 / 231k 行）后，手稿改为
"事实驱动重生成 + 十轮质量复盘"：

- 阶段一（源码 → 手稿）：`sources/digest_source.py` 产出版图清单，
  `sources/plan_outline.py` 生成章节大纲与覆盖矩阵，`sources/build_manuscript.py`
  依据事实渲染章节（包版图、核心类型、源码坐标、练习）。
- 阶段二（手稿 → 文档）：沿用 `render/` 与 `audit/` 既有门禁。
- 质量复盘：十轮递进，每轮"度量 → 改进生成器 → 重生成 → 复核门禁"，
  度量口径与验收标准见 `books/docs/plan/2026-06-16-001-manuscript-regeneration.md`。

### 9.1 在建子项

| 立项 | 目标 | 设计文档 |
|------|------|----------|
| 章节范围去重叠 | 已完成：重复句 16.5% → 4.3%，阈值收紧到 12% | `docs/plan/2026-06-16-002-chapter-scope-disjoint.md` |
| 工具链通用化（配置已分三类：数据组织/基础/风格） | 去 H2 特化，成为通用源码分析出版工具 | `docs/plan/2026-06-16-003-toolchain-generality.md` |

---

# 实施与维护计划

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.2-dev
> 定位：在办事项的**时机档与逐项验收**——每项现状 / 动作 / 验收 / 事实位只在这里；
> 不记设计细节（看 `technical.md`），也不存问题台账（看 `review-findings.md`）。
> **编号源**：`plan-next = 13`（新增计划项取此编号，写入后更新为 +1；已用最大 plan-12，
> 递增保证唯一，归档不回收。编号与 `review-findings.md` 的 `rf-*` 是两套，互不占用）

---

## 概述

在办 3 项：P2 1 项（**plan-4**）、P3 2 项（**plan-6**、**plan-12**）。
单项的范围、验收与事实位只在本文维护；系统怎么搭见 `technical.md`，怎么验证见
`testplan.md`。

---

## 当前迭代待办

> **P1** = 当前待办（立即执行） · **P2** = 下一阶段就绪（条件满足即开工） ·
> **P3** = 预期实施，有空时安排 · **P4** = 先决门槛未过，暂缓。
>
> 分档表达时机，不改变编号；一项完成后从表中删除，摘要写进 `changelog.md` 对应版本段。

> **归档放弃项边界（禁止重提）**：不做通用静态站点生成器、不追求门禁的语义智能、
> 不做多书合一构建、不替代版本控制（理由见 `technical.md` §10）。

### P1 — 当前待办（立即执行）

入选标准：不做就让门禁或文档事实失去意义。

### P2 — 下一阶段就绪（条件满足即开工）

入选标准：价值明确、成本可控，前置条件可判定。

#### `plan-4` 语言包扩展（第二语种）

**现状**：`data/language/` 只有 `zh.json`，骨架名与练习提示语是中文单份；
图注前缀、跳章引用句式、必备段落名仍写在判据脚本里。
**动作**：按 `docs/plan/language-pack/plan.md` 分阶段推进（判据取值改造 → schema 冻结 →
第二语种包与骨架 → 双语等价性判据 → 产物与交付）；先把取词从脚本挪进语言包且中文版行为
零变化，再上第二语种。
**验收**：第二语种可构建；章节数与图号与中文版逐一对应；`structure.py` 绿；判据脚本里
不出现语种字面量，缺字段回退可见且有断言。
**事实位**：设计与计划在 `docs/plan/language-pack/design.md` 与 `docs/plan/language-pack/plan.md`；
语言资源在 `data/language/`；读取入口见 `technical.md` §3.3。

### P3 — 预期实施，有空时安排

入选标准：收益明确，但需要等时机或积累。

#### `plan-6` 图示升级（ASCII → 结构化图）

**现状**：关键流程用 ASCII 图表达，宽度受 `ascii_max_cols` 约束，复杂流程难画全。
**动作**：按 `docs/plan/diagram-upgrade/plan.md` 分阶段推进（门禁判据先行 → HTML → PDF → EPUB → 试点），
先挑 2 张最拥挤的流程图改为 SVG，验证三个出口与既有门禁后再决定是否铺开。
**验收**：换图后 `diagrams.py`、`figures.py`、`verify_pdf.py`、`verify_epub.py` 均绿且
每条新判据都有能红的用例；图号引用不变；`make.py check` 与 `deliver` 全绿。
**事实位**：设计与计划在 `docs/plan/diagram-upgrade/design.md` 与 `docs/plan/diagram-upgrade/plan.md`；
图注体例与图号规则在 `../manuals/how-to-write.md` §14，图号唯一与连续由 `audit/structure.py` 判定、
图注词表与长度由 `audit/captions.py` 判定。

#### `plan-12` C 语言源码解析（源码树 → 书）

**现状**：阶段 1–4 已落地——`ingest/languages/c.py` 按目录切包、头文件声明即 public、引号 `#include`
转包级依赖，注册表与 `sources.suffixes` 都已收 `c`，坐标匹配全部按 `sources.suffixes` 现建。
**动作**：还剩阶段 5：按 `docs/plan/c-language/plan.md` 用一棵真实 C 树跑 `digest.py → outline.py →
chapters.py`，填好 `book.toml [chapters.packages]` 后跑 `make.py check`。
**验收**：`digest.py` 产出的 inventory 行数与 `cloc` 同档、包数与目录结构一致；`outline.py` 无异常
且每包有章归属；`structure.py` 与 `source_refs.py` 绿，手稿里至少 20 处 `.c:` 坐标通过核验。
**事实位**：设计与计划在 `docs/plan/c-language/design.md` 与 `docs/plan/c-language/plan.md`；
分析器契约 `ingest/languages/_base.py`，注册与探测 `ingest/languages/__init__.py`，
后缀表 `data/config/base.json [sources]`，坐标核验 `audit/source_refs.py`。

### P4 — 先决门槛未过，暂缓

入选标准：接入前有硬性先决条件，门槛未过不排期。当前无待办项。

## 待归档（已完成，等版本发布时移入 `docs/archive/`）

> 收录已完成的迭代：工作已落地，结论在 `changelog.md` 与问题台账里；设计文件等发布时
> 由 `core/docs_archive.py` 整体移入 `docs/archive/v<major>.<minor>/`。本表不占计划编号，
> 每行只给主题目录与结论出处——没有这一节，完成的迭代就会成为没人认领的孤儿目录。

| 迭代目录 | 结论出处 |
| --- | --- |

当前无待归档项：已完成的迭代已随 `docs/archive/v0.1/` 归档。

## 归档

> 已关闭版本的台账在 `docs/archive/`；本文件只留当前与将来的计划项。

| 版本 | 计划快照 | 变更日志 | 问题台账 |
| --- | --- | --- | --- |
| v0.1 | [archived_plan.0.1.md](../archive/v0.1/archived_plan.0.1.md) | [archived_changelog.0.1.md](../archive/v0.1/archived_changelog.0.1.md) | [archived_review-findings.0.1.md](../archive/v0.1/archived_review-findings.0.1.md) |

计划项完成后摘要进 `changelog.md` 对应版本段，本文不留存已完成项，历史由 git 与归档目录保留。
