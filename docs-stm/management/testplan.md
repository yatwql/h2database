# H2 Database 源码分析 — 质量标准与测试计划

> 版本：v5.8
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

| 类别 | 通过标准 | 验证方式 |
|------|----------|----------|
| 章节结构 | 12 章齐全，H1/H2/H3/H4 层级连续 | `final_check.py` |
| 图号 | 每章图号唯一且完整；允许历史补号导致非严格位置顺序 | `final_check.py` |
| 图表覆盖 | 内容型 `###` 小节 ≥ 2 图；模板型小节 ≥ 1 图 | `_audit_smart.py` |
| 代码围栏 | 所有围栏成对；HTML `<pre><code>` 平衡 | `generate_html.py`, `final_check.py` |
| HTML TOC | TOC 与内容标题 1:1，零断链 | `final_check.py` |
| 合并文档 | 源文件总行数与合并文档一致 | `final_check.py` |
| 编码 | Markdown 和 HTML 均为有效 UTF-8 | `final_check.py` |
| 索引完整性 | 索引 ≥ 120 条；每章 ≥ 5 条；章节引用对应实际内容 | `final_check.py`, `build_index.py --coverage` |
| 索引层级（v6.0） | 主条目 ≥ 150；子条目 ≥ 50；see-also ≥ 30；总条目 ≥ 250；see-also 全部解析；子条目章节 ∈ 1-12 | `final_check.py`、`build_index.py --hierarchy-check`、`_audit_index_xrefs.py` |
| 图注动宾结构（v6.0） | 全书图注以批准动词起首；长度 ∈ [8, 30] 字；无模糊后缀；strict 阈值下违规 = 0 | `_audit_captions.py --threshold strict` |
| 图簇桥接（v6.0） | 3+ 张图在 ≤ 40 行内连续出现的"图簇"，前置一句桥接叙事点名所有图 | `_audit_figure_clusters.py --window 40 --needs-bridge`（应输出空清单） |
| 延伸思考（v6.0） | 14 章节槽全部含 `## N.X 延伸思考` 小节；每章 ≥ 3 题；每题含难度/题型 emoji + 提示行 + 含锚点的回顾行；全书 ≥ 50 题 | `final_check.py`、`_audit_exercises.py` |
| 术语完整性 | 术语 ≥ 100 条；每条有对应章节引用；引用章节号有效；see-also 双向闭合 | `final_check.py`、`_annotate_terms.py --check-related`、`build_glossary.py --validate` |
| 版本统计 | cover 统计先更新；管理文档版本一致 | `cover_stats.py`, 人工核对 |

标准流程必须达到 `final_check.py` 全部检查通过。

## 3. 格式规范

- 图注格式：`**图 X-Y: Title**`，独立成行，不放入代码围栏。
- ASCII 图围栏：使用 ` ```text `。
- Java 代码围栏：使用 ` ```java `；SQL 使用 ` ```sql `。
- 源码路径：使用 `org/h2/...`，不使用 `h2/src/main/...` 前缀。
- 源码引用：使用 `ClassName.java:行号`，但不得放入章节标题或 PDF Outline 标题。
- 跨章引用：使用 `详见第X章《实际 H1 标题》`。
- 管理文档职责：需求、计划、测试、变更、审查问题分别维护，避免重复。

## 4. PDF 专项门禁

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
