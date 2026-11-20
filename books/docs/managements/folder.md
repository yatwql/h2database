# 目录结构（books/）

> 软件：bookwright — 源码分析成书工具 v0.1
> 版本：v0.1
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
      *-baseline.json          # 各类已评审存量：ASCII 图、符号漂移、风格、体积
      *-findings.json          # 已评审的图注与深度存量
      snapshot-<快照>.json     # 历史快照的体积基线（比对用）
    state/                     # 机器维护的派生状态（ingest 重建，不入库）
      source-inventory.json    # 被分析源码的快照事实
      outline.json             # 章节与主题的派生大纲
    tmp/                       # 一次性脚本与临时文件（不入库）
    snapshots/                 # 只读历史快照：别的书的稿子，仅供比对，不参与构建
      <日期>-<标签>/
        manifest.json        # 来源压缩包哈希、逐文件字节/行数/哈希
        manuscript/          # 快照正文
    manuscript/              # 手稿（唯一可编辑的内容源）
      cover.md
      front/                 # 前件：序、版权、阅读指南
      ch1-2-architecture.md
      ch3-packages.md
      ch4-5-modules-processes.md
      ch6-1-data-structures.md
      ch6-2-storage-algorithms.md
      ch6-3-query-algorithms.md
      ch7-8-sql-optimizer.md
      ch9-10-persistence-locking.md
      ch11-12-guide-summary.md
      appendix-a-case-studies.md
      appendix-b-version-changes.md
      back/                  # 后件：glossary.md / references.md / index.md
  src/
    python/                  # 工具链：lib/ core/ ingest/ manuscript/ audit/ render/ app/
                             #   + make.py（单入口）、check_runner.py（档位编排）、release.py
    test/                    # unittest 测试套件（单元 + 集成 + 真实书稿回归）
  logs/                      # 运行日志（按天回滚，gitignored）
  dist/                      # 交付产物（生成物，gitignored）
    h2-source-code-analysis.md
    h2-source-code-analysis.html
    h2-source-code-analysis.pdf
    h2-source-code-analysis-print.pdf
    h2-source-code-analysis.epub
  docs/
    managements/             # 全部管理与规范文档（见 §2）
    manuals/                 # 使用手册（scripts-and-reference.md：全部脚本清单）
```

## 2. 管理文档

```text
books/docs/managements/
  README.md                  # 索引与职责说明
  requirements.md            # 当前范围与交付物
  plan.md                    # 计划项清单（plan-N，按 P1–P4 分档，每项现状/动作/验收/事实位）
  review-findings.md         # 问题记录（rf-N，待处理 / 已修摘要 / 文件膨胀登记）
  testplan.md                # 质量门禁与验证命令（验证的唯一权威；门禁级别只在 §2.1/§2.2 声明）
  quality-model.md           # 质量策略（判定分工、三种起点、基线生命周期、复核成本）
  changelog.md               # 版本历史
  folder.md                  # 本文件：目录结构
  technical.md               # 工具链架构约束（可机检部分由 check_architecture 守卫）
  analysis-doc-standard.md   # 内容标准（跨项目复用）
  DESIGN.md                  # 设计契约总纲（三界面共有规则）
  DESIGN-TUI.md              # 终端交互契约
  DESIGN-WEB.md              # 网页控制台契约
```

## 2.1 配置分四层

| 类别 | 文件 | 放什么 | 换项目是否要改 |
| --- | --- | --- | --- |
| 数据组织 | `data/tmpl/book.toml` | 书名/版本、路径、章节清单、标题、编号、覆盖归属、包映射 | 是（每个项目不同） |
| 基础配置 | `data/config/base.json` | 源码树位置、文件后缀、包前缀、基线与状态路径、PDF/EPUB/ASCII/覆盖率预算 | 部分（指向新源码树） |
| 书籍风格 | `data/config/style.json` | 展示文案、章节骨架、图注词表与预设、图示标记、写作阈值、生成能力与模板 | 通常否 |
| 语言资源 | `data/language/zh.json` | 章节骨架名、练习提示语、术语行 | 否（加语种时新增一份） |

## 3. 归属规则

- **文档与配置分离**：判定规则/阈值在 `style.json`，叙述模板在 `templates.toml`，
  名称与提示语在 `language/`，书籍身份与展示文案在 `book.toml`。
- **配置分四层**：内容组织 `data/tmpl/book.toml`、基础设施 `data/config/base.json`、
  写作规则 `data/config/style.json`、语言资源 `data/language/zh.json`。合并规则只在
  `technical.md` §3.1 定义；脚本统一通过 `_config` 读取，禁止硬编码。
- **基线与状态归 data**：`data/baselines/` 存放机器维护的已知问题记账，不放人写文档。
- **手稿只在 `data/manuscript/`**：`dist/` 里的合并 Markdown 是生成物，不手改。
- **产物只在 `dist/`**：`*.html`、`*.pdf`、`*.epub`、`*.log` 全部 gitignored，
  由 `make.py build` / `make.py deliver` 重新生成。
- **被分析的源码是外部输入**：由 `base.json [sources]` 指向，仓库里不需要它。
- **工具链只在 `src/python/`**：正式交付脚本；临时脚本不得入库。
- **测试只在 `src/test/`**：`make.py test` 跑全部；`make.py cover` 带覆盖率棘轮。
- **管理文档只在 `docs/managements/`**：需求、计划、测试、变更各一份，互不重复。

## 4. 常用入口

入口清单只有两份：使用者看 [`books/README.md`](../../README.md) 的快速开始，验证命令
看 [`testplan.md`](testplan.md) §1。本文不重复命令。

## 5. 不入库的临时产物

临时修复脚本、压缩包、`__pycache__`、过程性产物一律不入库：正式脚本只进
`src/python/`，一次性脚本与会话产物只进 `data/tmp/`（已 gitignore）。

历史手稿不进 `data/manuscript/`：用 `src/python/manuscript/snapshot.py` 导入到
`data/snapshots/<日期>-<标签>/`，生成 manifest 后即可用
`snapshot.py baseline` 出体积基线。快照只读，门禁不扫描它。
