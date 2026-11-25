# 立项：章节范围去重叠（重复句降到 12% 以下）

> 版本：0.1 · 2026-06-16 · 状态：已完成
> 关联：`plan.md` §9、`docs/spec/analysis-doc-standard.md`、`config.json [quality]`

## 1. 问题

`audit/audit_book_quality.py` 的重复度指标当前为 **16.5%**，阈值棘轮定在 17%，目标是 12%。
根因是**章节覆盖范围重叠**：`ch1-2`、`ch4-5`、`ch9-10` 都覆盖 `org.h2.engine`、
`org.h2.mvstore` 等同一批包，生成器只能对相同的包写出相同的句子。

## 2. 目标

1. 每个包在全书有**唯一主责章节**（`[chapters.packages]` 一一归属），其他章节只用交叉引用。
2. 重复句 ≤ 12%，且重复项只允许出现在表格事实（不计入指标）。
3. 章节行数保持 150–400，四层阶梯齐备，练习 ≥4 题。

## 3. 做法

1. 在 `data/tmpl/book.toml` 增加 `[chapters.packages]` 的唯一性校验：
   `plan_outline.py` 输出"包 → 主责章节"表，重复归属即报错。
2. 重叠章节改为"视角章"：不重复描述包，只写该视角下的差异（性能/并发/演化），
   正文用 `详见第X章《…》` 跳转。
3. 生成器新增 `--scope strict` 模式：非主责章节跳过包表与类型表，只留视角与跳转。
4. 达标后把 `config.json [quality].max_duplicate_ratio` 从 17 收紧到 12。

## 3.1 实施结果

- `book.toml [chapters.packages]` 改为**单主责归属**：20 个包各归一个章节，
  `plan_outline.py` 增加 `ownership_conflicts` 检查（重复归属即告警）。
- 非主责章节改为"视角章"：不再复述包表，新增 **跨章索引**（包 → 主责章节）跳转。
- 生成器补充 `逐类导读`、`源码坐标明细`（411 条坐标）、`知识点清单`，
  薄章节行数回到 150+。
- 实测：重复句 **4.3%**（目标 ≤12%）、正文 152–347 行、平均句长 34.9 字、
  每章坐标 ≥26；`max_duplicate_ratio` 由 17 收紧到 **12**。

## 4. 验收

- `audit_book_quality.py` 重复度 ≤ 12%；
- `make.py check` 全绿；
- 索引与术语仍能解析（章节号未变）；
- 两次 `make.py build` 哈希一致。
