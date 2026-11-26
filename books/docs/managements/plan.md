# 实施与维护计划

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.2-dev
> 定位：在办事项的**时机档与逐项验收**——每项现状 / 动作 / 验收 / 事实位只在这里；
> 不记设计细节（看 `technical.md`），也不存问题台账（看 `review-findings.md`）。
> **编号源**：`plan-next = 14`（新增计划项取此编号，写入后更新为 +1；已用最大 plan-13，
> 递增保证唯一，归档不回收。编号与 `review-findings.md` 的 `rf-*` 是两套，互不占用）

---

## 概述

在办 4 项：P2 1 项（**plan-4**）、P3 3 项（**plan-6**、**plan-12**、**plan-13**）。
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

#### `plan-13` 对比类论述表格化

**现状**：并列比较（相邻小版本差异、优化器参数取舍、升级与回滚对照）写成长段落，读时要自行对齐
两侧取值；全书表格仅 3 处。
**动作**：按 `docs/plan/tabular-comparisons/plan.md` 分阶段推进（选点与判据冻结 → 试点两处 →
铺开与门禁回归 → 收尾）；先挑附录 B 与 ch7 参数取舍两处改 3 列表，验证三个出口（HTML/PDF/EPUB）
与既有判据后再铺开。
**验收**：每处改写前后事实逐条对应、无新增断言；交付校验（PDF、EPUB 两侧）全绿；`content_depth`、
`readability` 的结论与改动前一致（指标仍在区间内）；EPUB 窄屏下表格不溢出。
**事实位**：设计与计划在 `docs/plan/tabular-comparisons/design.md` 与 `docs/plan/tabular-comparisons/plan.md`；
表格体例在 `docs/manuals/how-to-write.md`，表格渲染与校验在 `render/to_html.py` 与交付校验两步。

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

> 已发布版本的计划快照只在上面的归档文件里；本文只留在办与将来的计划项。

- [`archived_plan.0.1.md`](../archive/v0.1/archived_plan.0.1.md) — v0.1（2026-11-26 发布）
