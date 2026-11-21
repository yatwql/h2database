# 实施与维护计划

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1
> 定位：在办事项的**时机档与逐项验收**——每项现状 / 动作 / 验收 / 事实位只在这里；
> 不记设计细节（看 `technical.md`），也不存问题台账（看 `review-findings.md`）。
> **编号源**：`plan-next = 11`（新增计划项取此编号，写入后更新为 +1；已用最大 plan-10，
> 递增保证唯一，归档不回收。编号与 `review-findings.md` 的 `rf-*` 是两套，互不占用）

---

## 概述

在办 4 项：P2 3 项（**plan-3**、**plan-4**、**plan-10**）、P3 1 项（**plan-6**）。
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

#### `plan-3` 覆盖率棘轮上调

**现状**：门槛已能跑（`make.py cover` 修复前会死锁，见 rf-29），实测已从 85% 抬到 86%，
下限同步抬到 86；目标仍是 88，还差 2 个点。
**动作**：下一步补 `check_runner.py`（69%）与 `structure.py`（82%）的分支测试——
这两处是剩余缺口最大且不需要 PDF 夹具的；`verify_pdf.py`（14%）与 `pdf_toc_links.py`（32%）
要造 PDF 夹具，收益大但成本更高，放第三档。一次只抬一档。
**验收**：`make.py cover` 在新区间通过；无测试被删除或跳过。
**事实位**：阈值在 `base.json`；判据见 `testplan.md` 的「覆盖率」行。

#### `plan-4` 语言包扩展（第二语种）

**现状**：`data/language/` 只有 `zh.json`，骨架名与练习提示语是中文单份。
**动作**：新增语种文件与 `BOOK_LANGUAGE` 分支，章节骨架名走语言包；图号与章节数
必须与中文版一致。
**验收**：第二语种可构建；章节数与图号与中文版逐一对应；`structure.py` 绿。
**事实位**：语言资源在 `data/language/`；读取入口见 `technical.md` §3.3。

#### `plan-10` 附录的符号断言纳入门禁

**现状**：`source_refs.py` 只扫章节文件（`chapter_names` 里以 `ch` 开头的那些），附录 A 的
`Class.method(` 断言因此从未被检查；实测有 10 条断言在对应类里找不到方法
（如 `CommandContainer.canReuse(`、`MVStore.openInternal(`、`MVStore.setLastChunk(`），
其余 6 条是已登记漂移。同一批附录里的 `Class.java:line` 坐标也不在扫描面内。

**动作**：把附录文件（`appendix-*.md`）加进`extract_references` 与
`extract_symbol_claims` 的扫描面；逐条核对 10 条断言——文档写错的改文档，改了名或不存在
的方法写明理由后进 `source-symbol-baseline.json`。一次只动这一份附录，不顺手改正文。

**验收**：`source_refs.py` 扫描面覆盖全部章节与附录；10 条断言逐条有结论（改文档或入基线
并在基线里写明理由）；`make.py check` 全绿；附录坐标无新增 missing。

**事实位**：扫描面在 `audit/source_refs.py` 的 `CHAPTER_FILES`；已登记漂移在
`data/baselines/source-symbol-baseline.json`；判据见 `testplan.md` 的「事实」行。

### P3 — 预期实施，有空时安排

入选标准：收益明确，但需要等时机或积累。

#### `plan-6` 图示升级（ASCII → 结构化图）

**现状**：关键流程用 ASCII 图表达，宽度受 `ascii_max_cols` 约束，复杂流程难画全。
**动作**：先挑 2–3 张最复杂的流程图改为结构化图，验证渲染链与 PDF 字体嵌入后铺开。
**验收**：换图后 `diagrams.py`、`figures.py`、`verify_pdf.py` 均绿；图号引用不变。
**事实位**：图注与图号规则见 `style-guide.md` §14 与 `testplan.md` §3。

### P4 — 先决门槛未过，暂缓

入选标准：接入前有硬性先决条件，门槛未过不排期。当前无待办项。

## 归档

本项目不按版本切分计划归档文件：计划项完成后写进 `changelog.md` 对应版本段，
本文不留存已完成项，历史由 git 保留。
