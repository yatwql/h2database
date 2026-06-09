# H2 Database 源码分析 — 实施计划

> 最后更新：2026-06-08
> 版本：v4.22

---

## 1. 当前状态

文档已完成并进入维护阶段：

- 12 章源码分析内容已交付。
- 正式源码、管理文档和交付工具统一位于 `docs-stm/`。
- 标准 MD/HTML 验证链路通过；PDF 按需生成。
- 已记录审查问题均在 `docs-stm/review-findings.md` 中关闭。

当前统计以 `docs-stm/cover.md` 和 `docs-stm/tools/final_check.py` 输出为准，避免在多个管理文档中重复维护数字。

## 2. 正式目录

```text
docs-stm/
  cover.md
  ch1-2-architecture.md
  ch3-packages.md
  ch4-5-modules-processes.md
  ch6-1-data-structures.md
  ch6-2-storage-algorithms.md
  ch6-3-query-algorithms.md
  ch7-8-sql-optimizer.md
  ch9-10-persistence-locking.md
  ch11-12-guide-summary.md
  h2-source-code-analysis.md
  requirements.md
  plan.md
  testplan.md
  changelog.md
  review-findings.md
  tools/
```

## 3. 验证流程

标准验证流程和 PDF 交付命令详见 `docs-stm/testplan.md` 第1节。本章节不重复维护。

## 4. 已完成阶段

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 1 | 需求确认、源码探索、章节结构设计 | ✅ 完成 |
| Phase 2 | 12 章并行撰写 | ✅ 完成 |
| Phase 3 | 合并 Markdown、HTML/PDF 生成工具 | ✅ 完成 |
| Phase 4 | 图表覆盖、章节结构、TOC 审查 | ✅ 完成 |
| Phase 5 | 多轮审查与质量修复 | ✅ 完成 |
| Phase 6 | 工具迁移到 `docs-stm/tools/` | ✅ 完成 |
| Phase 7 | 管理文档职责收敛与冲突清理 | ✅ 完成 |

详细历史见 `docs-stm/changelog.md`。

## 5. 管理文档职责

管理文档职责分配见 `CLAUDE.md` 中的「Management Document Authority」节。核心原则：同一事实只维护在一个权威位置。

## 6. 维护策略

- 发现新问题时先登记到 `docs-stm/review-findings.md`，修复完成后同步记录到 `docs-stm/changelog.md`。
- 不保留一次性修复脚本、临时压缩包、`__pycache__` 或外部 session 文件。
- 本项目 session 文件只保留在仓库 `.claude/` 目录中。

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
