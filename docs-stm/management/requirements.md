# H2 Database 源码分析 — 需求文档

> 版本：v4.24
> 状态：已交付，维护中
> 最后更新：2026-06-10

---

## 1. 项目目标

对 H2 Database v2.x Java 源码进行系统分析，输出面向开发者的中文技术文档，帮助读者理解 H2 的架构分层、SQL 执行链路、存储引擎、事务、查询优化器、持久化和锁实现。

## 2. 交付物

| 产物 | 路径 | 说明 |
|------|------|------|
| 源章节 | `docs-stm/ch*.md` | 10 个源文件覆盖 12 章 |
| 合并 Markdown | `docs-stm/h2-source-code-analysis.md` | 标准可提交交付物，由源章节生成 |
| HTML | `docs-stm/h2-source-code-analysis.html` | 按需生成，带侧边栏 TOC，git 忽略 |
| PDF | `docs-stm/h2-source-code-analysis.pdf` | 按需生成，带大纲和可点击目录，git 忽略 |
| 工具脚本 | `docs-stm/tools/` | 正式生成、审计和验证工具 |
| 管理文档 | `docs-stm/management/requirements.md`, `plan.md`, `testplan.md`, `changelog.md`, `review-findings.md` | 当前需求、计划、质量门禁、历史和问题追踪 |

当前统计数据以 `docs-stm/cover.md` 自动更新结果和 `docs-stm/tools/final_check.py` 输出为准。

## 3. 内容范围

文档必须覆盖：

- H2 定位、历史和整体架构。
- JDBC/Server/Engine/Command/Expression/Table-Index/MVStore/FileSystem 等核心层次。
- 主要 `org.h2.*` 包结构和关键类职责。
- SELECT、INSERT、UPDATE、DELETE、COMMIT、ROLLBACK、COMPACT、CHUNK、READ 等核心流程。
- B-Tree、Copy-on-Write、MVCC、Chunk、LIRS、FreeSpace、MVStore 平衡、Optimizer、R-Tree、Recursive Descent Parser 等核心算法。
- SQL 执行、查询优化、持久化、恢复、锁和并发控制。
- 源码阅读路线、调试入口和总结。

## 4. 质量需求

质量门禁以 `docs-stm/management/testplan.md` 为唯一权威来源。本文件只保留需求摘要：

- 章节完整：12 章齐全，H1 格式一致。
- 图表完整：内容型小节至少 2 图，模板型小节至少 1 图。
- 源码引用：关键论述包含文件名和行号，路径使用 `org/h2/...` 格式。
- 格式一致：图注、代码围栏、跨章引用和标题层级符合约定。
- 导航有效：HTML TOC、PDF Outline 和目录链接必须可验证。
- 管理文档一致：版本号、统计、流程和职责不得相互冲突。

## 5. 验证流程

验证流程以 `docs-stm/management/testplan.md` 第1节为准。本章节只保持引用关系，不重复维护命令。

## 6. 非目标

- 不在 `docs/` 或 `.claude/` 中维护正式交付文档或工具脚本。
- 不提交临时修复脚本、压缩包、`__pycache__` 或过程性 session 文件。
- 不在多个管理文档中重复维护长版本历史、完整问题清单或大段验证脚本。

## 7. 版本历史

完整版本历史见 `docs-stm/management/changelog.md`。
