# 新建一本书（含翻译版）

一条命令搭好骨架，再按四份文件的职责分别填内容。

```bash
books/scripts/bookctl new ../my-book --title "我的书"
books/scripts/bookctl new ../my-book-en --lang en --title "My Book"
books/scripts/bookctl new ../copy --title "副本" --from-manuscript   # 连章节一起复制
```

脚手架会生成下面这些文件，**它们职责不同、不能互相顶替**（权威定义见
[`technical.md §13`](../spec/technical.md)）：

| 文件 | 回答的问题 | 内容 | 新建/翻译时怎么改 |
|------|-----------|------|------------------|
| `book.toml` | 这本书**是什么、怎么组织** | 书名/版本/产物名、展示文案、目录、章节清单与顺序、每条 H1 标题、H1 编号、覆盖归属、包→章节映射 | 保留结构，把 `titles`、`[project]` 换成新语言；`version` 从 0.1 起 |
| `templates.toml` | 这本书**怎么表述** | 5 条叙述模板：版图/类型/入口/路径引言 + 深读要点 | 逐条翻译；**占位符 `{num} {pkgs} {top} {dep} {share}` 必须原样保留** |
| `language/<code>.json` | 章节与练习的**名词与提示语** | 本章导读/小结/延伸思考/延展阅读的名字、`提示`/`回顾` 前缀、术语行 | 翻译成目标语言；用 `BOOK_LANGUAGE=en` 选中 |
| `config/style.json` | **判定规则与阈值** | 图注词表与预设、图示标记、质量/文风阈值、禁用语、篇幅预算、生成数量上限 | 一般整份复用；目标语言不同时只调整词表与阈值 |

一句话记法：**结构看 `book.toml`，说法看 `templates.toml`，名词看语言包，判分看 `style.json`。**
拷错方向会被门禁拦下：`style_schema.py` 拒绝 `style.json` 里出现叙述模板或展示文案。

## 脚手架之后

1. 改 `data/config/base.json`：`sources.src_main` 指向新源码树，`languages` 选 `java|python|rust`。
2. `bookctl analyze` 生成版图与章节；`bookctl check` 跑全部门禁。
3. 手写正文仍是人最值钱的部分：`data/manuscript/ch*.md`。

## 如果要做翻译版

- 复制同一份 `book.toml` 结构，只翻译 `titles` 与 `[project]`；
- `templates.toml` 与语言包整体翻译（占位符不动）；
- 术语表与索引要跟着翻译，但**索引的 `§X.Y` 锚点不改**——它们指向章节编号。
