# H2 Database 源码分析 — 质量标准与测试计划

> 版本：v6.1
> 最后更新：2026-06-15

---

## 1. 权威验证流程

每次文档源文件、管理文档或工具脚本变更后，按顺序运行：

```bash
python docs-stm/tools/cover_stats.py
python docs-stm/tools/rebuild_merged.py
python docs-stm/tools/generate_html.py
python docs-stm/tools/_audit_smart.py
python docs-stm/tools/final_check.py
```

最终交付 PDF 时追加：

```bash
python docs-stm/tools/generate_pdf.py
python docs-stm/tools/add_pdf_toc_links.py
python docs-stm/tools/verify_pdf.py
```

PDF 生成较慢；日常编辑只要求标准流程通过。

## 2. 质量门禁

### 2.1 门禁分级（v6.0 / Phase H 起）

`final_check.py` 的检查项按"阻塞级别"分为 P0 / P1 / P2 三档：

| 级别 | 含义 | 阻塞级别 |
|------|------|----------|
| **P0** | 基础完整性 + 渲染正确性 | 任何交付（含日常） |
| **P1** | 内容质量 + 工具可用性 | 正式发布 |
| **P2** | v6.0 起的"叙事质量"门禁，处于试运营评估期 | 可选；当前已全部通过 |

`final_check.py` 命令行控制：

```bash
python docs-stm/tools/final_check.py                  # 默认 p2 = 全量
python docs-stm/tools/final_check.py --gate-level p1  # p0 + p1
python docs-stm/tools/final_check.py --gate-level p0  # 仅 p0
```

### 2.2 各检查项及其级别

| 类别 | 通过标准 | 验证方式 | 级别 |
|------|----------|----------|------|
| 章节结构 | 12 章 + 5 附录齐全，H1/H2/H3/H4 层级连续 | `final_check.py`（heading hierarchy） | P0 |
| 图号 | 每章图号唯一且完整；允许历史补号导致非严格位置顺序 | `final_check.py`（figure numbering） | P0 |
| 图表覆盖 | 内容型 `###` 小节 ≥ 2 图；模板型小节 ≥ 1 图 | `_audit_smart.py` | P0 |
| 代码围栏 | 所有围栏成对；HTML `<pre><code>` 平衡 | `final_check.py`（code fence balance / HTML TOC） | P0 |
| 跨章引用 | 章节互引 ≥ 1；前后件免检 | `final_check.py`（cross-references） | P0 |
| HTML TOC | TOC 与内容标题 1:1，零断链 | `final_check.py`（HTML TOC） | P0 |
| 合并文档 | 源文件总行数与合并文档一致 | `final_check.py`（merged doc） | P0 |
| 编码 | Markdown 和 HTML 均为有效 UTF-8 | `final_check.py`（UTF-8 encoding） | P0 |
| CSS 渲染钩子 | generate_html.py 含 9 项关键 CSS 标记（h1 装饰、复制按钮、面包屑等） | `final_check.py`（CSS style checks） | P0 |
| 索引完整性 | 索引 ≥ 120 条；每章 ≥ 5 条；章节引用对应实际内容 | `final_check.py`（index integrity） | P1 |
| 索引层级 | 主条目 ≥ 150；子条目 ≥ 50；see-also ≥ 30；see-also 全部解析；子条目章节 ∈ 1-12 | `final_check.py`、`build_index.py --hierarchy-check`、`_audit_index_xrefs.py` | P1 |
| 术语完整性 | 术语 ≥ 60 条；每条有对应章节引用；引用章节号 ∈ 1-12 | `final_check.py`（glossary content） | P1 |
| 工具脚本可用性 | `build_glossary.py` / `build_index.py` 语法有效 | `final_check.py`（glossary builder checks） | P1 |
| 图注动宾结构 | 全书图注以批准动词起首；长度 ∈ [8, 30] 字；无模糊后缀；strict 阈值下违规 = 0 | `_audit_captions.py --threshold strict` | P2 |
| 图簇桥接 | 3+ 张图在 ≤ 40 行内连续出现的"图簇"，前置一句桥接叙事点名所有图 | `_audit_figure_clusters.py --window 40 --needs-bridge`（应输出空清单） | P2 |
| 延伸思考 | 14 章节槽全部含 `## N.X 延伸思考` 小节；每章 ≥ 3 题；每题含难度/题型 emoji + 提示行 + 含锚点的回顾行；全书 ≥ 50 题 | `final_check.py`、`_audit_exercises.py` | P2 |
| 写作风格审计 | `check_style.py` 0 WARN | `final_check.py`（style check） | P2 |
| 版本统计 | cover 统计先更新；管理文档版本一致 | `cover_stats.py`, 人工核对 | P0 |

`final_check.py` 默认（`--gate-level p2`）必须达到全部检查通过。

## 3. 格式规范

- 图注格式：`**图 X-Y: Title**`，独立成行，不放入代码围栏。
- ASCII 图围栏：使用 ` ```text `。
- Java 代码围栏：使用 ` ```java `；SQL 使用 ` ```sql `。
- 源码路径：使用 `org/h2/...`，不使用 `h2/src/main/...` 前缀。
- 源码引用：使用 `ClassName.java:行号`，但不得放入章节标题或 PDF Outline 标题。
- 跨章引用：使用 `详见第X章《实际 H1 标题》`。
- 管理文档职责：需求、计划、测试、变更、审查问题分别维护，避免重复。

## 4. 交付形态专项门禁

本节列出"非日常"的可选交付形态门禁。所有这些产出都不在日常流水线内生成；按需在交付的最后阶段单独运行。

### 4.1 标准 PDF（日常交付）

正式 PDF 交付必须满足：

- PDF 文件重新生成自当前 HTML。
- PDF Document Outline 与 HTML 标题一致。
- 正文前目录条目可点击并指向有效页面。
- Outline 标题不得包含"代码片段"、源码文件名、源码位置或行号范围。

验证命令为：

```bash
python docs-stm/tools/generate_pdf.py
python docs-stm/tools/add_pdf_toc_links.py
python docs-stm/tools/verify_pdf.py
```

### 4.2 印刷级 PDF（v6.0 / Phase G 起，可选交付）

印刷级 PDF 是日常 PDF 的并行产出，用于实体印刷或正式归档场景。要求：

- 印刷级 PDF 与日常 PDF 文件分离（`h2-source-code-analysis.pdf` 与 `h2-source-code-analysis-print.pdf`），互不覆盖
- 每章 H1 在印刷级 PDF 上独占一页（chapter cover），含装饰性渐变条与底分隔线
- 目录页每条 TOC 条目以"标题 ………… 页码"虚线对齐渲染
- 页眉左侧含"H2 Database 源码分析"，右侧含版本标识；页脚居中含"第 N 页 / 共 M 页"
- 所有 H1-H4 在 PDF Outline 中可点击跳转
- 印刷级 PDF 文件大小 ≤ 标准 PDF 1.5 倍

验证命令：

```bash
python docs-stm/tools/pdf_print_grade.py
```

视觉验证：在 Chrome / Adobe Reader 中检查 (a) 章首装饰条 (b) TOC 虚线对齐 (c) 页眉/页脚一致出现。

### 4.3 EPUB（v6.0 起，可选交付）

EPUB 是面向电子阅读器（Apple Books / Kindle / Calibre / Readium 等）的可选交付形态，**只在交付的最后阶段按需输出**，不进入日常流水线。要求：

- EPUB 由 pandoc 从合并后的 `h2-source-code-analysis.md` 生成；运行前先调用 `rebuild_merged.py` 保证源最新
- 输出路径：`docs-stm/h2-source-code-analysis.epub`（与日常 PDF / 印刷级 PDF 互相独立）
- 元数据：`<dc:title>` / `<dc:creator>` / `<dc:date>` / `<dc:language>=zh-CN` 由 cover.md 自动提取（标题 / 副标题 / 版本 / 作者 / 出版日期）
- 每个 H1 章节在 EPUB 内部独立分卷（`--split-level=1`），便于阅读器分章导航
- 目录深度 H1-H3（`--toc --toc-depth=3`），与 HTML 侧边栏 TOC 层级一致
- 内嵌精简 CSS：等宽字体代码块 + 蓝色左竖条 + 表头蓝底白字 + 引用块浅蓝背景
- 文件大小：合理 EPUB 通常在 2-5 MB 范围；超过 10 MB 视为异常需人工排查

依赖：[pandoc](https://pandoc.org/)（不是日常依赖；只在出 EPUB 时需要）

验证命令：

```bash
python docs-stm/tools/generate_epub.py
```

视觉验证：在 Apple Books / Calibre / Readium 中至少查看一章正文 + 一个代码块 + 一张 ASCII 图 + 目录导航是否正常。

EPUB 不接入 `final_check.py`（按 plan §4.6 / §4.8 印刷级 + 按需交付物均走人工视觉验证起步）。

## 5. 拒绝标准

以下任一情况不得交付：

- 标准验证流程失败。
- 缺失核心章节、核心流程或核心算法。
- HTML TOC 存在断链或标题数量不一致。
- 代码围栏不平衡或导致正文大段进入代码块。
- 图注格式、源码路径格式或跨章引用出现系统性不一致。
- PDF 交付时未通过 PDF 三步验证。
- 管理文档之间存在版本、路径、流程或职责冲突。

## 6. 维护周期

- 每次文档变更后运行标准流程。
- 每次正式归档或发布前运行 PDF 验证。
- 每次发现新问题时登记到 `docs-stm/management/review-findings.md`，修复后同步更新 `docs-stm/management/changelog.md`。

## 7. 门禁演进史

记录各检查项加入 P0/P1/P2 框架的版本与升级判定，便于评估"试运营 → 正式门禁"的过渡过程。

| 版本 | 检查项 | 起始级别 | 当前级别 | 备注 |
|------|--------|---------|---------|------|
| v3.x | 章节结构 / 图号 / 代码围栏 / 跨章引用 / UTF-8 / HTML TOC / 合并文档 | P0 | P0 | v6.0 之前即"必过" |
| v4.27 | 图表覆盖（`_audit_smart.py`） | P0 | P0 | 由独立工具确保 |
| v5.0 | 索引完整性 / 术语完整性 / 工具脚本可用性 / CSS 渲染钩子 | P1 | P1 | 内容质量保障层 |
| v5.3 (Phase C) | 索引层级（main/sub/see-also） | P2 | P1 | v5.7 实测 see-also 全部解析；P1 升级判定通过 |
| v5.5 (Phase E) | 图注动宾结构（strict） | P2 | P2 | 已运行多版本，0 违规；保留 P2 至少一个版本周期再评估升级 |
| v5.5 (Phase E) | 图簇桥接 | P2 | P2 | 33 簇全部含桥接；保留 P2 至少一个版本周期再评估升级 |
| v5.6 (Phase F) | 延伸思考 | P2 | P2 | 56 题 / 14 章节槽；保留 P2 至少一个版本周期再评估升级 |
| v5.x | 写作风格审计（`check_style.py`） | P2 | P2 | 永久 advisory；不计划升级 |
| v5.8 (Phase G) | 印刷级 PDF 视觉验证 | 人工 | 人工 | 当前不接入 `final_check.py`；视觉验证为主，待 verify_pdf 自动化后再评估 |

**升级判定规则**（plan §4.8）：

1. **试运营期**：P2 检查项至少跨一个版本周期，记录命中数 / 误报率 / 修复成本
2. **升级 P2 → P1** 条件：误报率 < 10% 且修复成本可承受
3. **降级**：从未发生；如因工具误报率上升需要降级，必须在 changelog 记录原因

**当前 P2 候选升级清单**（v6.1+ 评估）：

- 图注动宾结构、图簇桥接、延伸思考三项均跨版本稳定，待下一个工具迭代后评估升级 P1
- 索引层级已在 v6.0 升级 P1（v5.7 / v5.8 两个版本周期 0 误报）
