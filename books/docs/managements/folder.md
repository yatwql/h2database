# 目录结构（books/）

> 本文是 `books/` 下目录与文件职责的唯一说明。`CLAUDE.md` 只保留指向本文的链接，
> 结构与归属变更时只改这一份。

## 1. 顶层结构

```text
books/
  data/                      # 输入数据：配置 + 手稿 + 机器维护的状态
    tmpl/
      book.toml              # 文档·结构：身份、路径、章节顺序、标题与编号、包映射
      case-studies.toml      # 文档·案例：案例流水线（scenario -> steps）
      templates.toml         # 文档·表述：四段引言与深读要点模板（占位符不可改）
    config/
      base.json              # 配置·基础：源码树、语言与后缀、包前缀、基线路径、预算、日志
      style.json             # 配置·规则：图注词表、质量/文风阈值、禁用语、必备段落、预算上限
    language/
      zh.json                # 文档·名词：章节骨架名、练习提示语、术语行
    baselines/                 # 机器维护的已知问题账本（非人写文档）
      ascii-baseline.json    # ASCII 图已知问题基线（--update-baseline 生成）
      source-symbol-baseline.json  # 源码符号漂移基线
    manuscript/              # 手稿（唯一可编辑的内容源）
      cover.md
      front/                 # 前件：序、版权、阅读指南
      ch1-2-architecture.md
      ch3-packages.md
      ch4-5-modules-processes.md
      ch6-1-data-structures.md
      ch6-2-storage-algorithms.md
      ch6-3-query-algorithms.md
      ch7-sql-execution.md
      ch8-query-optimizer.md
      ch9-10-persistence-locking.md
      ch11-12-guide-summary.md
      appendix-a-case-studies.md
      appendix-b-version-changes.md
      back/                  # 后件：glossary.md / references.md / index.md
  src/
    python/                  # 工具链：lib/ ingest/ manuscript/ audit/ render/ app/ + make.py
    test/                    # unittest 测试套件（单元 + 集成 + 真实书稿回归）
  logs/                      # 运行日志（按天回滚，gitignored）
  dist/                      # 交付产物（生成物，gitignored）
    h2-source-code-analysis.md
    h2-source-code-analysis.html
    h2-source-code-analysis.pdf
    h2-source-code-analysis-print.pdf
    h2-source-code-analysis.epub
  docs/
    managements/             # 项目管理文档 + 通用规范（见 §2）
    manuals/                 # 使用手册（how-to-use.md：脚本用法唯一说明）
    plan/                    # 带日期的计划文档
```

## 2. 管理文档

```text
books/docs/managements/
  README.md                  # 索引与职责说明
  requirements.md            # 当前范围与交付物
  plan.md                    # 工作流、维护策略、风险、后续工作
  testplan.md                # 质量门禁与验证命令（验证的唯一权威）
  changelog.md               # 版本历史
  folder.md                  # 本文件：目录结构
  technical.md               # 工具链架构约束（可机检部分由 check_architecture 守卫）
  analysis-doc-standard.md   # 源码分析文档的通用内容标准与验收清单
  tui-interaction.md         # TUI 交互设计契约（键位/反馈/确认/光标）
```

## 2.1 配置分三类

| 类别 | 文件 | 放什么 | 换项目是否要改 |
| --- | --- | --- | --- |
| 数据组织 | `data/tmpl/book.toml` | 书名/版本、路径、章节清单、标题、编号、覆盖归属、包映射 | 是（每个项目不同） |
| 基础配置 | `data/config/base.json` | 源码树位置、文件后缀、包前缀、语言、基线与状态路径、PDF/EPUB/ASCII/覆盖率预算 | 部分（指向新源码树） |
| 书籍风格 | `data/config/style.json` | 展示文案、章节骨架、图注词表与预设、图示标记、写作阈值、生成能力与模板 | 通常否 |

## 3. 归属规则

- **文档与配置分离**：判定规则/阈值在 `style.json`，叙述模板在 `templates.toml`，
  名称与提示语在 `language/`，书籍身份与展示文案在 `book.toml`。
- **配置分两层、只有一个入口**：内容组织看 `data/tmpl/book.toml`，工具链策略看
  `data/config/config.json`；脚本统一通过 `_config` 读取，禁止硬编码。
- **基线与状态归 data**：`data/baselines/` 存放机器维护的已知问题记账，不放人写文档。
- **手稿只在 `data/manuscript/`**：`dist/` 里的合并 Markdown 是生成物，不手改。
- **产物只在 `dist/`**：`*.html`、`*.pdf`、`*.epub`、`*.log` 全部 gitignored，
  由 `make.py build` / `make.py deliver` 重新生成。
- **工具链只在 `src/python/`**：正式交付脚本；临时脚本不得入库。
- **测试只在 `src/test/`**：`make.py test` 跑全部；`make.py cover` 带覆盖率棘轮。
- **管理文档只在 `docs/managements/`**：需求、计划、测试、变更各一份，互不重复。

## 4. 常用入口

```bash
python books/src/python/make.py check      # 全部质量门禁（不写产物）
python books/src/python/make.py build      # cover 统计 + 合并 md + HTML
python books/src/python/make.py test       # 单元 + 集成测试
python books/src/python/make.py cover      # 覆盖率（带棘轮阈值）
python books/src/python/make.py deliver    # build + PDF + verify + EPUB（按需）
python books/src/python/make.py doctor     # 可选依赖（pandoc / playwright / pypdf）
```

## 5. 不入库的临时产物

临时修复脚本、压缩包、`__pycache__`、过程性产物一律不入库：正式脚本只进
`src/python/`，仓库级会话产物只进 `.claude/`。
