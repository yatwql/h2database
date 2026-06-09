# H2 Database 源码分析 — 质量标准与测试计划

> 版本：v4.22
> 最后更新：2026-06-08

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

正式 PDF 交付必须满足：

- PDF 文件重新生成自当前 HTML。
- PDF Document Outline 与 HTML 标题一致。
- 正文前目录条目可点击并指向有效页面。
- Outline 标题不得包含“代码片段”、源码文件名、源码位置或行号范围。

验证命令为：

```bash
python docs-stm/tools/generate_pdf.py
python docs-stm/tools/add_pdf_toc_links.py
python docs-stm/tools/verify_pdf.py
```

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
- 每次发现新问题时登记到 `docs-stm/review-findings.md`，修复后同步更新 `docs-stm/changelog.md`。
