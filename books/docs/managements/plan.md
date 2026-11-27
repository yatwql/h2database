# 实施与维护计划

> 软件：bookwright — 源码分析成书工具 v0.2-dev
> 版本：v0.2-dev
> 定位：在办事项的**时机档与逐项验收**——每项现状 / 动作 / 验收 / 事实位只在这里；
> 不记设计细节（看 `technical.md`），也不存问题台账（看 `review-findings.md`）。
> **编号源**：`plan-next = 20`（新增计划项取此编号，写入后更新为 +1；已用最大 plan-19，
> 递增保证唯一，归档不回收。编号与 `review-findings.md` 的 `rf-*` 是两套，互不占用）

---

## 概述

在办 9 项：P2 5 项（**plan-13**、**plan-14**、**plan-16**、**plan-18**、**plan-19**）、P3 3 项（**plan-6**、**plan-12**、**plan-15**）、P4 1 项（**plan-4**）。
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

入选标准：不做就让门禁或文档事实失去意义。当前无待办项。

### P2 — 下一阶段就绪（条件满足即开工）

入选标准：价值明确、成本可控，前置条件可判定。

#### `plan-13` 对比类论述表格化

**现状**：附录 B 的版本差异与第 7 章的 Statement/PreparedStatement 对照已改为 3 列表（试点完成），
门禁与三个出口均已验证；其余候选（升级与回滚对照、附录 A 案例链路对照）仍是段落。
**动作**：按 `docs/plan/tabular-comparisons/plan.md` 继续阶段 3：把剩余候选逐一表格化，每处独立提交，
每次改动后跑全量门禁与一次 `deliver`/`print` 目视检查 EPUB 窄屏排布。
**验收**：每处改写前后事实逐条对应、无新增断言；交付校验（PDF、EPUB 两侧）全绿；`content_depth`、
`readability` 的结论与改动前一致（指标仍在区间内）；EPUB 窄屏下表格不溢出。
**事实位**：设计与计划在 `docs/plan/tabular-comparisons/design.md` 与 `docs/plan/tabular-comparisons/plan.md`；
表格体例在 `docs/manuals/how-to-write.md`，表格渲染与校验在 `render/to_html.py` 与交付校验两步。

#### `plan-14` 编辑风格档（元素集合与密度）

**现状**：优秀技术书的要素（学习目标、前置知识、要点回顾、常见误区、代码清单编号、术语中英对照、
提示类区块、图表并重）只有四项被 `[sections]` 强制，其余靠自觉；本书实测提示类 2 条、代码标注 0 处、
表格 3 处、学习目标 3/14 章。
**动作**：按 `docs/plan/editorial-profile/plan.md` 分阶段推进；阶段 1 已落地——`data/book/editing.toml`
声明风格档与逐项覆盖，三档预设写在 `lib/_editorial.py`，`audit/editorial.py` 量出学习目标、要点回顾、
常见误区、表格密度四项并按基线棘轮判定。阶段 2 已起步：八处「本章小结」条目化、`key_points` 打开；
剩余是学习目标与常见误区两项内容。
**验收**：每个元素都有能红的判据；本书三档判据全绿；换档只改配置即可通过。

**事实位**：设计与计划在 `docs/plan/editorial-profile/design.md` 与 `docs/plan/editorial-profile/plan.md`；
段落契约在 `data/book/book.toml [sections]`，标签词表在 `data/language/`，判据实现进 `src/python/audit/`。

#### `plan-16` LLM 契约起草与自评审

**现状**：LLM 只起草导读与小节小结，输入是包摘要，输出没有任何可核验约束，写多了风险就大。
**动作**：按 `docs/plan/llm-contract-drafting/plan.md` 分阶段推进；阶段 1 已落地——`data/book/llm-tasks.toml`
声明每个任务的长度与取数规则，`lib/_llm_contract.py` 校验并把每次调用（含被拒）写进
`data/state/llm-ledger.jsonl`（prompt/响应摘要 + 模型 + 配置指纹），违约草稿回退到确定性文本。
**验收**：模型不得引入事实块之外的数字、不得增删标注编号；每个任务产出全部过判据；人工抽查无编造。

**事实位**：设计与计划在 `docs/plan/llm-contract-drafting/design.md` 与 `docs/plan/llm-contract-drafting/plan.md`；
调用面在 `src/python/ingest/chapters.py`，provider 配置在 `data/config/`。

#### `plan-18` 快照身份（换书、换源树之后仍可安全比对）

**现状**：阶段 1 已落地——`manifest.json` 增 `identity` 段（书 slug/版本、源树根与版本、工具版本、配置指纹、语种），
新快照写入 `data/snapshots/<book-slug>/<date>-<label>`，`list` 输出「名称／书／源版本／工具／配置／文件／字节」，
`diff A B` 先比身份：不同书或不同源树默认拒绝，`--cross` 才放行并声明「不是退化」；旧平铺目录只读兼容并显示为 `legacy`。
同一次改动里把原来 `data/baselines/` 下的快照体积账本并入 manifest（`lib/_snapshot.py` 成为唯一读取方，
`snapshot.py baseline` 与那份 json 一并删除）。
**动作**：按 `docs/plan/snapshot-identity/plan.md` 推进阶段 2：`snapshot.py adopt` 给旧快照补身份并归位；
`diff --cross` 输出固定的身份差异摘要；`list --book/--source` 过滤。
**验收**：同日两本书的快照互不覆盖；`list` 一眼可辨书与源版本；跨书 `diff` 返回 2 并提示 `--cross`；
旧快照补身份后能与新快照正常比对；体积门禁从 manifest 取数，`data/baselines/` 不再有快照副本。

**事实位**：设计与计划在 `docs/plan/snapshot-identity/design.md` 与 `docs/plan/snapshot-identity/plan.md`；
读取方 `src/python/lib/_snapshot.py`，写入与命令 `src/python/manuscript/snapshot.py`，
体积门禁 `src/python/audit/content_volume.py`，目录归属见 `docs/managements/folder.md`。

#### `plan-19` 基线目录归一（信封、命名、键形态、源版本）——已交付

**现状**：两个阶段均已落地——`data/baselines/` 十个文件统一为门禁命名 + 统一信封
（`schema/gate/kind/keyed_by`），`base.json` 与 `lib/_defaults/base.json` 同步声明，旧名回退已删除。
**动作**：按 `docs/plan/baselines-unify/plan.md` 完成阶段 1（信封、命名、键形态、源版本提示）与阶段 2
（移除 `_baseline.LEGACY`/`legacy_path`，清单命令把旧文件名列为待重记项）。
**验收**：迁移前后每个文件条数一致；`make.py check --keep-going`、`test`、`cover` 全绿；
`manuscript/baselines.py --check` 零告警。
**事实位**：设计与计划在 `docs/plan/baselines-unify/`；写入方 `lib/_baseline.py`，清单命令
`manuscript/baselines.py`，迁移记录见 `changelog.md` 0.2-dev 段。

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

#### `plan-15` 依据化（claims 判据与三类事实块）

**现状**：`source_refs` 只校验已写出的坐标是否过期，不检查强断言是否有依据；分析器只抽包/类型/
API/依赖/坐标，失败路径、不变量、调用链没有产出。
**动作**：按 `docs/plan/evidence-and-claims/plan.md` 分阶段推进（claims 判据 → `failure`/`invariants`
块 → `paths` 块）；句式词表进语言包，抽取按语言适配器实现。
**验收**：claims 判据能红且本书基线可复现；两块新事实块能在正文被引用；路径首尾坐标可解析，断链处显式标注。

**事实位**：设计与计划在 `docs/plan/evidence-and-claims/design.md` 与 `docs/plan/evidence-and-claims/plan.md`；
事实块机制在 `src/python/ingest/factblocks.py`，坐标解析在 `src/python/audit/source_refs.py`。

### P4 — 先决门槛未过，暂缓

入选标准：接入前有硬性先决条件，门槛未过不排期。

#### `plan-4` 语言包扩展（第二语种）

**现状**：先决门槛未过——第二语种的手稿尚不存在，语言包换掉文案后没有一个真实语种的正文可供验证「双语等价性」，判据只能自证。另：`data/language/` 只有 `zh.json`，骨架名与练习提示语是中文单份；
图注前缀、跳章引用句式、必备段落名仍写在判据脚本里。
**动作**：按 `docs/plan/language-pack/plan.md` 分阶段推进（判据取值改造 → schema 冻结 →
第二语种包与骨架 → 双语等价性判据 → 产物与交付）；先把取词从脚本挪进语言包且中文版行为
零变化，再上第二语种。
**验收**：第二语种可构建；章节数与图号与中文版逐一对应；`structure.py` 绿；判据脚本里
不出现语种字面量，缺字段回退可见且有断言。
**事实位**：设计与计划在 `docs/plan/language-pack/design.md` 与 `docs/plan/language-pack/plan.md`；
语言资源在 `data/language/`；读取入口见 `technical.md` §3.3。

## 待归档（已完成，等版本发布时移入 `docs/archive/`）

> 收录已完成的迭代：工作已落地，结论在 `changelog.md` 与问题台账里；设计文件等发布时
> 由 `core/docs_archive.py` 整体移入 `docs/archive/v<major>.<minor>/`。本表不占计划编号，
> 每行只给主题目录与结论出处——没有这一节，完成的迭代就会成为没人认领的孤儿目录。

| 迭代目录 | 结论出处 |
| --- | --- |
| `docs/plan/book-quality-closeout/` | 四项（存量基线、拆章、印刷密度、引用与索引下限）见 `changelog.md` 0.2-dev 段 |

其余已完成的迭代已随 `docs/archive/v0.1/` 归档。

## 归档

> 已发布版本的计划快照只在上面的归档文件里；本文只留在办与将来的计划项。

- [`archived_plan.0.1.md`](../archive/v0.1/archived_plan.0.1.md) — v0.1（2026-11-26 发布）
