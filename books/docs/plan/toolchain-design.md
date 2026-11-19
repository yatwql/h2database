# 工具链设计（当前状态）

> 本文件描述工具链**现在**的结构与约定，不记录演进过程。
> 目录与归属见 `../managements/folder.md`；用法见 `../manuals/how-to-use.md`；
> 内容标准见 `../spec/analysis-doc-standard.md`。

## 1. 两段式流水线

```text
源码树 --stage 1（事实抽取）--> 手稿 data/manuscript --> stage 2（渲染与校验）--> dist/{md,html,pdf,epub}
```

| 阶段 | 脚本 | 输入 → 输出 |
| --- | --- | --- |
| stage 1 | `ingest/digest.py` | 源码树 → `data/state/source-inventory.json` |
| stage 1 | `ingest/outline.py` | inventory + 章节映射 → `data/state/outline.json`（含覆盖矩阵与归属冲突） |
| stage 1 | `ingest/chapters.py` | outline + 模板 → `data/manuscript/*.md` |
| stage 2 | `render/*` | 手稿 → 合并 Markdown / HTML / PDF / EPUB |
| 全程 | `audit/*`、`audit/source_refs.py` | 质量门禁与事实核验 |

## 2. 配置三层

| 层 | 文件 | 内容 |
| --- | --- | --- |
| 数据组织 | `data/tmpl/book.toml` | 书籍元信息、路径、章节清单、标题、H1 编号、覆盖归属、包映射 |
| 基础 | `data/config/base.json` | 源码树、文件后缀、包前缀、语言、基线路径、工具链预算 |
| 风格 | `data/config/style.json` | 展示文案、章节骨架、图注词表、写作阈值、生成能力与模板 |
| 语言包 | `data/language/<code>.json` | 章节骨架名、练习提示语、术语提示行 |

脚本只通过 `_config` 读取上述文件，不硬编码路径、阈值或文案。

## 3. 章节与包：单主责

`book.toml [chapters.packages]` 中每个源码包只归属一个章节。非主责章节通过
「跨章索引」指向主责章节，不重复描述同一个包。

## 4. 质量门禁

| 类别 | 脚本 | 判据 |
| --- | --- | --- |
| 结构 | `audit/structure.py` | 章节/图号/围栏/TOC/编码完整性 |
| 事实 | `audit/source_refs.py` | `Class.java:line` 与 `Class.method(` 可在源码中解析 |
| 图书质量 | `audit/book_quality.py` | 坐标密度、四层阶梯、章节长度、表格行数、重复度、术语与练习分布 |
| 文风 | `audit/prose_quality.py` | 句长、长句比、段长、列表占比、示例密度、小节深度、唯一性、表格卫生 |
| 交付 | `render/verify_pdf.py`、`render/verify_epub.py` | outline/字体/页内链接；EPUB 容器与 nav |

阈值与目标值在 `style.json`；已知问题基线在 `data/baselines/`。

## 5. 面向其他项目

改 `book.toml`（章节与包映射）与 `base.json`（源码树、后缀、包前缀）即可复用到
另一份源码树；`src/test/test_generic_source.py` 用一棵极简 Java 树守住这条约定。
