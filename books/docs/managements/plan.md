# 实施与维护计划

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1-dev
> 定位：在办事项的**时机档与逐项验收**——每项现状 / 动作 / 验收 / 事实位只在这里；
> 不记设计细节（看 `technical.md`），也不存问题台账（看 `review-findings.md`）。
> **编号源**：`plan-next = 12`（新增计划项取此编号，写入后更新为 +1；已用最大 plan-10，
> 递增保证唯一，归档不回收。编号与 `review-findings.md` 的 `rf-*` 是两套，互不占用）

---

## 概述

在办 3 项：P1 1 项（**plan-11**）、P2 1 项（**plan-4**）、P3 1 项（**plan-6**）。
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

#### `plan-11` 多书并行维护
**现状**：`_config` 已能按书解析（`Config(root)` + `use()`），但没有任何入口指定「这次跑
哪本书」，派生状态、基线、产物、日志都只有一份；第二本书进来会与第一本互相覆盖。
**动作**：按 `docs/plan/multi-book/plan.md` 推进——先做三项前置（源根解冻、惰性默认书、顶层取值机检），
再加 `--book` 与向上查找，随后是手稿的 edition 轴；多根源与工具链独立成包按需安排。
**验收**：`requirements.md` IR-10、IR-11 与 IR-13 的判据——指定不同书根时，路径、派生状态、基线与
产物全部随之改变且互不覆盖；不带 `--book` 时产物与日志位置保持不变。
**事实位**：设计与步骤在 `docs/plan/multi-book/design.md` 与 `docs/plan/multi-book/plan.md`；
配置对象的约定在 `technical.md` §3.1，按书隔离的目录归属在 `folder.md` §3。


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
图注体例与图号规则在 `style-guide.md` §14，图号唯一与连续由 `audit/structure.py` 判定、
图注词表与长度由 `audit/captions.py` 判定。

### P4 — 先决门槛未过，暂缓

入选标准：接入前有硬性先决条件，门槛未过不排期。当前无待办项。

## 待归档（已完成，等版本发布时移入 `docs/archive/`）

> 收录已完成的迭代：工作已落地，结论在 `changelog.md` 与问题台账里；设计文件等发布时
> 由 `core/docs_archive.py` 整体移入 `docs/archive/v<major>.<minor>/`。本表不占计划编号，
> 每行只给主题目录与结论出处——没有这一节，完成的迭代就会成为没人认领的孤儿目录。

| 迭代目录 | 结论出处 |
| --- | --- |
| `docs/plan/figure-chapter-plumbing/` | `rf-35`、`changelog.md` 的 6.5 段 |

## 归档

> 已发布版本的台账见 `docs/archive/`；当前尚无已归档版本。


本项目不按版本切分计划归档文件：计划项完成后写进 `changelog.md` 对应版本段，
本文不留存已完成项，历史由 git 保留。
