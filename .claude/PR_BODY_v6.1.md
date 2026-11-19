# 工业级技术书籍质量提升 — Phase A → H + EPUB 交付（v5.1 → v6.1）

> **52 files changed · +23,894 / -5,958**
> **32 commits**（v5.1 Phase A → v6.1 EPUB）
> **基线**：v5.0（2026-06-11 已交付，36,775 行 / 578 图 / 88/88 检查通过）
> **目标**：v6.0「工业级技术书籍质量」里程碑 + v6.1 EPUB 按需交付

---

## 总体里程碑（v5.0 → v6.1 数字对照）

| 维度 | v5.0 基线 | v6.1 实测 | Δ |
|---|---|---|---|
| 章节文件数 | 9 | 10（ch7-8 拆分）+ 5 附录 | +1 章节 +5 附录 |
| 章节总行数 | 36,314 | 39,779 | **+3,465** |
| ASCII 图数 | 579 | 598 | **+19** |
| 源码引用 | 185 | 197 | **+12** |
| 术语表条目 | 73 | 113 | **+40** |
| 概念索引主条目 | 122 | 209（合计 331） | **+87** |
| `final_check.py` 检查项 | 88/88 | 106/106 | **+18** |
| 章节均衡 max_min_ratio | 3.748 | 3.044 | -18.8% |
| 工具脚本数 | 17 | 24 | **+7** |
| 交付形态 | MD + HTML + PDF | + 印刷级 PDF + EPUB | +2 |

---

## Phase A → H + EPUB 路线图

| 阶段 | 版本 | 主要交付 |
|---|---|---|
| Phase A | v5.1 | 度量基线工具 `balance_check.py`，固化 `baseline-v5.0.json` |
| Phase B | v5.2 | ch7-8 拆分（8,085 行 → 3,642 + 4,443）；max_min_ratio 3.748 → 3.044 |
| Phase C | v5.3 | 前后件深度化：preface / copyright / how-to-read / glossary / index 三档层级化 |
| Phase D | v5.4 | 附录 A：端到端案例研究（SELECT / COMMIT / Recovery 三案例） |
| Phase E | v5.5 | 图注动宾结构（strict 0 违规）+ 图簇桥接（33 簇全部含桥接句） |
| Phase F | v5.6 | 章末延伸思考（14 章节槽 56 题，难度 emoji + 提示行 + 锚点回顾行） |
| — | v5.7 | 附录 A/B 拆分；管理文档归一；HTML 视觉/交互修复（intro-mode / 收起展开 / 事件委托 / JS 语法 bug 修复 / 后件升级为附录 C/D/E） |
| Phase G | v5.8 | 印刷级 PDF（章首装饰、TOC 虚线、独立产出 `*-print.pdf`） |
| Phase H | v6.0 | 门禁分级 P0/P1/P2 + `final_check.py --gate-level` 入口 + 门禁演进史 + v6.0 全量回归发布 |
| — | v6.1 | EPUB 按需交付形态（pandoc 引擎，最终交付阶段产出） |

---

## 主要变更

### 内容
- **新增 5 个附录**（H1 顶级条目）：A 端到端案例研究 / B 源码版本变更说明 / C 术语表 / D 概念索引 / E 参考文献
- **ch7-8 大文件拆分**为独立的 `ch7-sql-execution.md`（3,642 行）+ `ch8-query-optimizer.md`（4,443 行），不再有 8,000+ 单文件
- **章末延伸思考**：14 章节槽全部新增 `## N.X 延伸思考` 小节，56 道题；每题难度 emoji 🟢/🔵/🟠 + 提示行 + 含 `§X.Y` 锚点的回顾行
- **前后件深度化**：preface / copyright / how-to-read 信息密度提升；术语表 113 条；索引 main / sub / see-also 三档层级（合计 331 条）
- **图注重写**：全书图注 strict 阈值 0 违规（动宾起首 + 8-30 字 + 无模糊后缀）
- **图簇桥接**：33 个图簇（3+ 张图在 ≤ 40 行内连续出现）全部含桥接句

### 工具链（新增 7 个 + 多个增强）
新工具：
- `balance_check.py` — 章节均衡度量基线工具
- `_audit_captions.py` — 图注动宾结构审计
- `_audit_figure_clusters.py` — 图簇桥接审计
- `_audit_exercises.py` — 章末延伸思考审计
- `_audit_index_xrefs.py` — 索引 see-also 与子条目章节有效性审计
- `pdf_print_grade.py` — 印刷级 PDF 渲染（章首装饰 + TOC 虚线对齐 + 独立产出）
- `generate_epub.py` — EPUB 渲染（pandoc 引擎，按需在最终交付阶段产出）
- `source_freshness_check.py` — 源码引用保鲜检查（H2 上游版本升级时使用）
- `build_case_study_outline.py` — 端到端案例叙事大纲生成

增强：
- `final_check.py`：`--gate-level p0|p1|p2` 三档门禁；`SECTION_LEVEL` 模块级状态 + `section()` 帮助函数；15 个区段全部贴标签；p0=93/93、p1=102/102、p2=106/106
- `generate_html.py`：intro-mode 类（封面/目录页隐藏 TOC）+ 桌面端 TOC 收起/展开（`#sidebar-toggle` 表头条 + 浮动 `›` + `[` 快捷键 + localStorage 持久化）+ document 级事件委托；同时修复"f-string 把 `'\n'` 求值为真实换行导致整段 `<script>` 抛 SyntaxError"的潜伏 bug
- `_audit_smart.py`、`build_index.py`、`build_glossary.py`、`_annotate_terms.py`、`readability_check.py` 不同程度增强

### 门禁框架（v6.0）
`final_check.py` 检查项分 P0 / P1 / P2 三档：

| 级别 | 含义 | 当前通过 |
|---|---|---|
| P0 | 基础完整性 + 渲染正确性（图号、跨章引用、围栏、UTF-8、HTML TOC、合并文档、CSS 钩子） | 93/93 |
| P1 | 内容质量 + 工具可用性（索引完整性 + 层级、术语表、工具脚本） | 102/102 |
| P2 | v6.0 起的"叙事质量"门禁，处于试运营评估期（图注 / 图簇 / 延伸思考 / 写作风格） | 106/106 |

`testplan.md §7 门禁演进史`记录每项检查"起始级别 → 当前级别"演进 + 升级判定规则。索引层级在 v6.0 从 P2 升级 P1（v5.7/v5.8 双周期 0 误报）。

### 新增交付形态
| 形态 | 触发 | 工具 |
|---|---|---|
| 印刷级 PDF | 最终交付按需 | `pdf_print_grade.py` |
| EPUB | 最终交付按需 | `generate_epub.py`（依赖 pandoc） |

两者**都不进入日常流水线**，按 plan §4.6 "印刷级 PDF 增量推进，不阻塞 MD/HTML 流水线"原则。

### 管理文档归一
- 所有版本号对齐 v6.1
- `phase3-audit.md`（v4.25 时期）归档到 `archive/phase3-audit-v4.25.md`
- `requirements.md` / `plan.md` 删除过期统计（如 `glossary 47 条`、`tools 17 个`），统一指向 cover.md / final_check.py 自动统计
- 第 7 轮审查（R7-1..R7-17 + R8-1）全部关闭

---

## 流水线状态

```
final_check.py (默认 p2):       106/106 OK
final_check.py --gate-level p1: 102/102 OK
final_check.py --gate-level p0:  93/93 OK
_audit_smart.py:                 0 sections needing diagrams
check_style.py:                  0 WARN / 0 INFO
generate_html.py:                616 TOC entries, 2,192 fence lines
generate_epub.py:                Python 语法校验 OK（运行需 pandoc）
pdf_print_grade.py:              Python 语法校验 OK（运行需 Playwright + Chromium）
合并文档:                         39,777 行
```

## 测试计划

合并前请在干净 checkout 下运行：

```bash
# 标准流水线
python docs-stm/tools/cover_stats.py
python docs-stm/tools/rebuild_merged.py
python docs-stm/tools/generate_html.py
python docs-stm/tools/_audit_smart.py
python docs-stm/tools/final_check.py                  # → 106/106
python docs-stm/tools/final_check.py --gate-level p1  # → 102/102
python docs-stm/tools/final_check.py --gate-level p0  # → 93/93
python docs-stm/tools/check_style.py                  # → 0 WARN

# 可选交付物（按需）
python docs-stm/tools/generate_pdf.py                 # 标准 PDF（需 Playwright）
python docs-stm/tools/pdf_print_grade.py              # 印刷级 PDF
python docs-stm/tools/generate_epub.py                # EPUB（需 pandoc）
```

## 后续路线（不阻塞此 PR）

`docs-stm/management/plan.md §7` 已记录：
- API 文档索引（P3）
- 交互式图表（P3）
- 英文版翻译（P4）
- CI 集成（P4）
- 印刷级 PDF: per-chapter running header（待 paged.js 或同等方案）

🤖 Generated with [Claude Code](https://claude.com/claude-code)
