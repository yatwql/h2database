# H2 Database 源码分析 — 实施计划

> 版本：v5.8
> 最后更新：2026-06-15

---

## 1. 当前状态

文档已完成 v5.x 多轮质量增强，目前处于 v6.0「工业级技术书籍质量提升」推进阶段：

- 12 章 + 2 附录已交付（附录 A 端到端案例研究、附录 B 源码版本变更说明）。
- 正式源码、管理文档与交付工具统一位于 `docs-stm/`。
- 标准 MD/HTML 验证链路通过；PDF 按需生成。
- 全部历史审查问题均在 `docs-stm/management/review-findings.md` 中关闭；v6.0 各阶段进度同样维护在该文件中。

具体统计（行数、图数、术语表/索引条目数、工具脚本数）以 `docs-stm/cover.md` 自动更新结果与 `docs-stm/tools/final_check.py` 输出为准，本文件不再重复维护数字。

## 2. 正式目录

```text
docs-stm/
  cover.md
  front/                     # 书籍前件（preface, copyright, how-to-read）
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
  appendix-a-case-studies.md
  appendix-b-version-changes.md
  back/                      # 书籍后件（glossary, references, index）
  management/                # 管理文档（README, requirements, plan, testplan, changelog, review-findings, style-guide, baseline-*.json）
  plan/                      # 阶段性实施计划（版本路线、详细 PRD/任务清单）
  h2-source-code-analysis.md # 合并 Markdown 交付物
  tools/                     # 正式生成、审计与验证脚本
```

## 3. 验证流程

标准验证流程与 PDF 交付命令详见 `docs-stm/management/testplan.md` 第 1 节。本章节不重复维护命令清单。

## 4. 阶段进展

- v1.0 – v5.0：12 章并行撰写、合并/HTML/PDF 工具链、图表与结构审查、工具迁移到 `docs-stm/tools/`、管理文档职责收敛、写作风格增强。
- v5.1 – v5.7（v6.0 推进中）：基线度量、ch7-8 拆分、前后件深度化、端到端案例研究附录、图注与图簇桥接质量、章末延伸思考、附录 A/B 拆分、HTML 视觉与交互修复、后件升级为附录 C/D/E。
- v5.8（Phase G 起步）：印刷级 PDF 渲染管道（独立产出）—— 章首装饰页、TOC 虚线对齐、印刷级页眉页脚。

每个版本的具体增量、工具新增、文件变更记录均在 `docs-stm/management/changelog.md` 中维护；v6.0 阶段路线见 `docs-stm/plan/2026-06-15-001-feat-industrial-book-quality-plan.md`。

## 5. 管理文档职责

管理文档职责分配见 `docs-stm/management/README.md` 与项目根 `CLAUDE.md` 的「Management Document Authority」节。核心原则：同一事实只维护在一个权威位置。

## 6. 维护策略

- 发现新问题时先登记到 `docs-stm/management/review-findings.md`，修复完成后同步记录到 `docs-stm/management/changelog.md`。
- 不保留一次性修复脚本、临时压缩包、`__pycache__` 或外部 session 文件。
- 本项目 session 文件只保留在仓库 `.claude/` 目录中。
- 建议在 H2 上游版本升级或源码大改后，运行 `python docs-stm/tools/source_freshness_check.py` 检查源码引用保鲜状态。

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
