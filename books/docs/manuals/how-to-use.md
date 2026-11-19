# 脚本使用手册（books/src/python）

> 本文件是工具链使用方式的唯一说明。`CLAUDE.md` 只保留指向本文的链接。
> 目录结构与文件职责见 `books/docs/managements/folder.md`。

## 1. 单入口：make.py

日常一律走单入口，不要手工按顺序调用脚本：

```bash
python books/src/python/make.py check      # 全部质量门禁（只读，不写产物）
python books/src/python/make.py build      # cover 统计 + 合并 Markdown + HTML
python books/src/python/make.py verify     # 与 check 相同（语义化别名）
python books/src/python/make.py test       # 单元 + 集成测试（books/src/test）
python books/src/python/make.py cover      # 覆盖率 + 棘轮阈值（book.toml 的 coverage_fail_under）
python books/src/python/make.py deliver    # build + PDF + verify_pdf + EPUB
python books/src/python/make.py doctor     # 可选依赖检查（pandoc / playwright / pypdf）
```

通用参数：

| 参数 | 作用 |
|------|------|
| `--only NAME[,NAME]` | 只跑指定步骤 |
| `--skip NAME[,NAME]` | 跳过指定步骤 |
| `--timings` | 打印每步耗时 |
| `--keep-going` | 单步失败后继续跑完，最后汇总失败项 |

典型用法：

```bash
python books/src/python/make.py check --only audit_links,audit_ascii
python books/src/python/make.py build --timings
python books/src/python/make.py deliver --skip generate_pdf
```

## 2. 日常编辑流程

1. 改 `books/data/manuscript/` 下的手稿。
2. `make.py check` —— 任一 P0 门禁失败即停下修复。
3. `make.py build` —— 重新生成 `books/dist/` 里的合并 Markdown 与 HTML。
4. 交付前 `make.py deliver` —— 生成 PDF/EPUB 并自动校验。

配置分三类，脚本统一通过 `_config` 读取，**不要硬编码**：

- 数据组织：`data/tmpl/book.toml`（章节清单、标题、编号、覆盖归属、包映射）
- 基础配置：`data/config/base.json`（源码树、文件后缀、包前缀、基线、预算）
- 书籍风格：`data/config/style.json`（文案、骨架、图注词表、写作阈值、生成模板）

## 3. 单独调用某个门禁（调试用）

```bash
python books/src/python/_audit_links.py          # 链接与锚点解析
python books/src/python/_audit_ascii.py          # ASCII 图宽度/对齐（已知项走基线）
python books/src/python/_audit_captions.py       # 图注动宾结构（--threshold strict|normal|loose）
python books/src/python/_audit_figures.py        # 图号与引用一致性（--strict 才失败）
python books/src/python/_audit_crossrefs.py      # 章节互引准确性
python books/src/python/_audit_exercises.py      # 延伸思考题量与结构
python books/src/python/_audit_figure_clusters.py# 图簇桥接叙事
python books/src/python/_audit_index_xrefs.py    # 索引 see-also 可解析
python books/src/python/_audit_smart.py          # 图表覆盖与 fig-refs（--fig-refs）
python books/src/python/balance_check.py         # 章节均衡度量（--json / --baseline / --diff）
python books/src/python/check_style.py           # 写作风格审计（advisory）
python books/src/python/readability_check.py     # 可读性：长句、宽图、框线闭合
python books/src/python/source_freshness_check.py# 源码引用与 Class.method 断言
python books/src/python/final_check.py           # 汇总门禁（--gate-level p0|p1|p2）
```

维护型脚本（按需运行，会改写内容）：

```bash
python books/src/python/build_glossary.py        # 生成本术语表草稿（--check / --validate / --coverage）
python books/src/python/build_index.py           # 生成索引草稿（--hierarchy-check）
python books/src/python/_annotate_terms.py       # 给各章补术语参考行（--check / --report-missing / --check-related）
python books/src/python/cover_stats.py           # 刷新 cover.md 的统计数字
```

基线类脚本（把当前已知问题记账，避免每次升级都被卡）：

```bash
python books/src/python/_audit_ascii.py --update-baseline
python books/src/python/source_freshness_check.py --suggest          # 看改名建议
python books/src/python/source_freshness_check.py --update-baseline  # 复核后记账
```

## 4. PDF 与 EPUB（按需交付）

```bash
python books/src/python/make.py deliver
```

拆开执行：

```bash
python books/src/python/generate_pdf.py        # HTML → PDF（chromium）
python books/src/python/verify_pdf.py          # 交付校验（--require-toc-links 走交付口径）
python books/src/python/add_pdf_toc_links.py   # 给印刷 TOC 加可点击链接
python books/src/python/pdf_print_grade.py     # 印刷级 PDF（不覆盖标准 PDF）
python books/src/python/generate_epub.py       # EPUB（需要 pandoc）
python books/src/python/verify_epub.py         # EPUB 结构校验
```

产物全部在 `books/dist/`，均为 gitignored：

- `h2-source-code-analysis.html`
- `h2-source-code-analysis.pdf`
- `h2-source-code-analysis-print.pdf`
- `h2-source-code-analysis.epub`

## 5. 依赖

| 依赖 | 用途 | 缺失时 |
|------|------|--------|
| Python 3.11+ | 全部脚本（需要标准库 `tomllib`） | 无法运行 |
| `pypdf` | PDF 校验、TOC 链接 | PDF 校验跳过 |
| `playwright` + chromium | PDF 渲染 | 只能校验已有 PDF |
| `pandoc` | EPUB 生成 | `generate_epub.py` 直接报错退出 |
| `coverage` | `make.py cover` | 返回 2 并提示安装 |

`make.py doctor` 会逐项报告可用性。
