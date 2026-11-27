# 新建一本书（含翻译版）

> 维度：**换项目——用同一套工具做另一本书或另一个语言版本**
> 软件：bookwright — 源码分析成书工具 v0.2

一条命令搭好骨架，再按四份文件的职责分别填内容。

```bash
books/scripts/bookctl new ../my-book --title "我的书"
books/scripts/bookctl new ../my-book-en --lang en --title "My Book"
books/scripts/bookctl new ../copy --title "副本" --from-manuscript   # 连章节一起复制
```

脚手架会生成下面这些文件，**它们职责不同、不能互相顶替**：

| 文件 | 回答的问题 | 内容 | 新建/翻译时怎么改 |
| ------ | ----------- | ------ | ------------------ |
| `book.toml` | 这本书**是什么、怎么组织** | 书名/版本/产物名、展示文案、目录、章节清单与顺序、每条 H1 标题、H1 编号、覆盖归属、包→章节映射 | 保留结构，把 `titles`、`[project]` 换成新语言；`version` 从 0.1 起 |
| `templates.toml` | 这本书**怎么表述** | 5 条叙述模板：版图/类型/入口/路径引言 + 深读要点 | 逐条翻译；**占位符 `{num} {pkgs} {top} {dep} {share}` 必须原样保留** |
| `language/<code>.json` | 章节与练习的**名词与提示语** | 本章导读/小结/延伸思考/延展阅读的名字、`提示`/`回顾` 前缀、术语行 | 翻译成目标语言；用 `BOOK_LANGUAGE=en` 选中 |
| `config/style.json` | **判定规则与阈值** | 图注词表与预设、图示标记、质量/文风阈值、禁用语、篇幅预算、生成数量上限 | 一般整份复用；目标语言不同时只调整词表与阈值 |

一句话记法：**结构看 `book.toml`，说法看 `templates.toml`，名词看语言包，判分看 `style.json`。**
拷错方向会被门禁拦下：`style_schema.py` 拒绝 `style.json` 里出现叙述模板或展示文案。

## 生成

```bash
books/scripts/new-book.sh ../my-book --title "My Book"
books/scripts/new-book.sh ../translation --lang en --title "My Book (EN)"
books/scripts/new-book.sh ../copy --from-manuscript   # 连章节一起复制
```

`style.json` 不是原样复制：结构（键、章节骨架）沿用当前书的 schema，保证
`style_schema` 门禁直接通过；**内容按目标语言重新派生**——句长锚点按 CJK / 拉丁
字系取不同值，术语表同义词、禁用链接文案、图注动词表、`glossary_ignore` 与逐书
`limits` 全部清空，避免把上一本书的词表带进新书。

## 脚手架之后

1. 改 `data/config/base.json`：`sources.src_main` 指向新源码树，`languages` 选 `java|python|rust|kotlin|go|c`。
2. `bookctl analyze` 生成版图与章节；`bookctl check` 跑全部门禁。
3. 手写正文仍是人最值钱的部分：`data/manuscript/ch*.md`。
4. 可选的书级文件按需添加：`data/book/glossary.toml`（术语别名）、`case-studies.toml`（案例流水线）；
   编辑风格档与 LLM 起草契约是 `book.toml` 里的 `[editing]` / `[llm_tasks]` 表，缺表即按默认档。
5. 第一次 `bookctl check` 若报 `editorial` 或体量/基线类问题，按[使用手册](how-to-use.md) §6.1 判断
   「先改内容还是先记账」。

## 如果要做翻译版

- 复制同一份 `book.toml` 结构，只翻译 `titles` 与 `[project]`；
- `templates.toml` 与语言包整体翻译（占位符不动）；
- 术语表与索引要跟着翻译，但**索引的 `§X.Y` 锚点不改**——它们指向章节编号。

## 范例：本仓库里的那份分析

工具链与内容没有绑定关系，本仓库自带的 H2 分析可以直接当模板对照着看：

| 想看什么 | 看哪里 |
| --- | --- |
| 书的身份、章节顺序、包归属 | `data/book/book.toml`（`[book]`、`[chapters]`） |
| 分析口径（源码树、包前缀、语言） | `data/config/base.json`（`[sources]`） |
| 已写成的手稿：章节、附录、前件后件 | `data/manuscript/` |
| 交付产物长什么样 | `books/dist/h2-source-code-analysis.{md,html,pdf,epub}` 与 `-print.pdf` |

这一份是**示例**，不是工具链的依赖：删掉它、换一棵源码树，命令与检查都不变。
