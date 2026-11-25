# 立项：工具链通用化（去 H2 特化，成为通用源码分析出版工具）

> 版本：0.1 · 2026-06-16 · 状态：进行中（第 1 批已落地）
> 关联：`plan.md` §9、`books/README.md`

## 1. 现状盘点（脚本内与具体源码/书名绑定的位置）

| 文件 | 特化内容 | 现状 |
|------|----------|------|
| `render/generate_html.py` | 15 处 `H2` 字面量（页面标题、面包屑、封面文案） | 待迁到 `[project]` |
| `render/generate_epub.py` / `pdf_print_grade.py` | H2 标题、作者、页眉页脚 | 待迁到 `[project]` |
| `render/verify_pdf.py` | 期望标题来源 | 已读 HTML，无需改 |
| `sources/source_freshness_check.py` | 23 处 `h2`、`org/h2` 前缀、`.java` 后缀 | 部分迁到 `[sources]` |
| `sources/build_case_study_outline.py` | 1065 行中文字面场景（专为 H2 案例编写） | 待改为数据文件 |
| `sources/build_manuscript.py` | 章节号/标题/附录、中文章节骨架文案 | **已迁到 `book.toml` + 模板** |
| `audit/balance_check.py` | 章节→章节号硬编码 | **已迁到 `[chapters.coverage]`** |
| `audit/_audit_exercises.py` / `check_style.py` / `_annotate_terms.py` | 中文写作规则、术语提示语 | 待抽成 `[language.zh]` 语言包 |

已完成的第 3 批（配置分三类）：`base.json` 与 `style.json` 从原 `config.json` 拆分，
`_config` 合并为同一视图并保留对旧单文件的兼容；文档（`folder.md`、`README.md`、
`how-to-use.md`）与测试 fixture 同步更新。

已完成的第 1 批：

- `[chapters.titles]` / `[chapters.numbering]` / `[chapters.coverage]` 三张表进 `book.toml`，
  章节号与标题不再写死在脚本里；`balance_check`、`build_manuscript` 改为读取配置。
- 生成文案（四段引言、深读要点）进 `config.json [generation.templates]`。
- 度量与阈值进 `config.json [quality]`。

## 2. 目标模型（第 3 批已落地前三层）

```text
data/tmpl/book.toml        数据组织：书籍元信息、路径、章节、标题、编号、包映射
data/config/base.json      基础配置：源码树、文件后缀、包前缀、语言、状态/基线、工具链预算
data/config/style.json     书籍风格：展示文案、章节骨架、图注词表、写作阈值、生成模板
language/<code>.json       语言包（待建）：中文写作规则与提示语
project/<name>.toml        项目档案（待建）：把上述 base/style 组合成一个命名档案
```

脚本只依赖这四个入口；换项目时只改 `project/*.toml` + `language/*.json`。

## 3. 迁移顺序（按风险从低到高）

1. `[project]` 渲染文案：页面标题、作者、页眉页脚、EPUB 元数据（`render/*`）。
2. `[sources]` 语言/扩展名：`.java`、包前缀、类后缀（`sources/source_freshness_check.py`）。
3. ~~`language/zh.json`：把中文写作规则从 `audit/*` 抽出~~（已完成：`data/language/zh.json`
   驱动 `_audit_exercises` 的章节名/提示语与 `_annotate_terms` 的术语提示行）。
4. ~~`build_case_study_outline.py` 的场景表改成 `data/tmpl/case-studies.toml`~~（已完成）。
5. ~~增加"无源码书目"回归：`src/test/` 用第二份极简源码树跑通 stage 1~~（已完成：
   `test_generic_source.py` + `fixtures/mini-java`）。

## 4. 验收

- `grep -c 'org\.h2' books/src/python/**/*.py` 归零（配置除外）；
- 第二份源码树（任意 Java 项目）能在不改代码的前提下生成手稿；
- 现有 H2 产物不回归：门禁、质量度量、221 测试全绿。
