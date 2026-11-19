# books — 源代码分析 → 专业文档生成工具链

面向"读源码、出文档"的工程化工具链：把一份 Java 源码树，变成结构可校验、
事实可追溯、可交付为 Markdown / HTML / PDF / EPUB 的专业技术书。

当前实例是《H2 Database 源码分析》（中文），但流水线与具体项目无关：
换一份源码树、改一份章节映射，即可产出另一本书。

## 它解决什么问题

人工读几十万行源码写书，三个环节最易失控：**范围**（哪些包必须覆盖）、
**事实**（引用的类、方法、行号是否真实存在）、**一致性**（章节、图注、索引、
交叉引用、交付物是否对齐）。本工具链把这三件事都变成可执行、可复现的门禁。

## 两段式流水线

```text
源码树 ──stage 1: 事实抽取──▶ 手稿 (data/manuscript)
                                    │
                                    └──stage 2: 渲染与校验──▶ dist/{md,html,pdf,epub}
```

**stage 1（源码 → 手稿）**

| 步骤 | 脚本 | 产出 |
|------|------|------|
| 抽取版图 | `sources/digest_source.py` | 包/文件/行数、`package-info` 职责、核心类型、公开 API → `data/state/source-inventory.json` |
| 规划章节 | `sources/plan_outline.py` | 章节 → 包的映射与覆盖矩阵（缺包即报）→ `data/state/outline.json` |
| 渲染章节 | `sources/build_manuscript.py` | 每章的模块版图、核心类型、源码坐标、术语对照、小结、练习 |

**stage 2（手稿 → 文档）**

`render/` 负责合并、HTML、PDF、EPUB；`audit/` 是 14 道质量门禁
（结构、图注、链接、索引、术语、源码引用、可读性、ASCII 图宽度、交付物结构）。

## 5 分钟上手

```bash
# 1) 全部门禁（只读，不写产物）
python books/src/python/make.py check

# 2) 构建：封面统计 → 合并 Markdown → HTML
python books/src/python/make.py build

# 3) 测试（快速档 ~9s；含 chromium/pandoc 的全量档加 --full）
python books/src/python/make.py test

# 4) 按需交付 PDF + EPUB（带结构校验）
python books/src/python/make.py deliver
```

源码更新后重生成手稿：

```bash
python books/src/python/sources/digest_source.py
python books/src/python/sources/plan_outline.py
python books/src/python/sources/build_manuscript.py
```

## 目录一览

```text
books/
  data/      # 输入与状态：tmpl/book.toml（内容组织）、config/config.json（工具链策略）、
             # manuscript/（手稿）、baselines/（已知问题基线）、state/（抽取结果）
  src/
    python/  # 工具链：lib/ 公共库、sources/ 事实抽取、manuscript/ 手稿维护、
             # audit/ 质量门禁、render/ 交付渲染
    test/    # 单元 + 集成测试（BOOK_SLOW=1 打开慢速档）
  dist/      # 交付产物（HTML/PDF/EPUB，gitignored）
  docs/      # managements/ 项目管理文档、manuals/ 使用手册、plan/ 迭代设计、archive/ 归档
```

## 质量门禁（摘）

| 类别 | 门禁 | 脚本 |
|------|------|------|
| 结构 | 章节/段落/图号/围栏/TOC/UTF-8 完整性 | `audit/final_check.py` |
| 事实 | `Class.java:line` 与 `Class.method(` 断言核对源码 | `sources/source_freshness_check.py` |
| 一致性 | 链接与锚点、索引 see-also、术语覆盖、跨章引用 | `audit/_audit_links.py` 等 |
| 叙事 | 图注动宾、图簇桥接、长句与重复、ASCII 图宽度 | `audit/_audit_captions.py` 等 |
| 交付 | PDF outline/字体嵌入、EPUB 容器与 nav | `render/verify_pdf.py`、`render/verify_epub.py` |

配置分三类：`data/tmpl/book.toml`（数据组织：章节、标题、编号、包映射）、
`data/config/base.json`（基础：源码树、文件后缀、包前缀、基线、预算）、
`data/config/style.json`（风格：文案、骨架、图注词表、写作阈值、生成模板）、
`data/language/zh.json`（语言包：章节骨架名与提示语）、`data/tmpl/case-studies.toml`（案例流水线）。
脚本不硬编码任何路径、阈值或文案。

## 迁移到别的项目

1. 改 `data/tmpl/book.toml`：`[paths]`、`[chapters].files`、`[chapters.packages]`。
2. 改 `data/config/base.json`：`sources.src_main`、`file_suffix`、`package_prefix`。
3. 按需调 `data/config/style.json`（风格/阈值），重跑 stage 1 三步，再 `make.py check`。

## 进一步阅读

- 源码分析文档的通用规范：`docs/spec/analysis-doc-standard.md`
- 目录职责与归属规则：`docs/managements/folder.md`
- 脚本用法与交付步骤：`docs/manuals/how-to-use.md`
- 质量门禁与验证命令：`docs/managements/testplan.md`
- 写作与格式规范：`docs/managements/style-guide.md`
- 迭代设计（重生成与十轮质量复盘）：`docs/plan/2026-06-16-001-manuscript-regeneration.md`
