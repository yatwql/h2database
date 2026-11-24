# bookwright v0.1 — 源码分析成书工具

> **一套源码树，换来一本读得下去的技术书。**

bookwright（源码分析成书工具）是一套本地工具链：把它指向一个源码仓库，它交回一本书。

面向「读懂别人的代码」的本地工具链：吃进一个源码仓库，吐出包与模块的版图、核心类型、
公开入口、依赖方向与阅读路径，再把它们做成一本 Markdown → HTML → PDF → EPUB 的书。
全程跑在自己的机器上，源码不出本机；换一份源码树，就是换一本书。

**为什么是「书」而不是文档站点？** 因为读源码的人要的不是接口清单，而是一条能走完的路线：
先看版图知道有哪些组件，再看类型知道谁在干活，再顺着入口走到关键路径，最后沿依赖方向判断
「改这里会碰到谁」。书是按这个顺序写的，章节之间靠跨章引用接起来，每一步都能回到源码坐标。

## 能做什么

| 能力 | 说明 |
| --- | --- |
| 源码 → 手稿 | 抽取包/模块版图、核心类型、公开 API、依赖方向，按 `book.toml` 的章节映射生成手稿骨架 |
| 手稿 → 交付 | 合并 Markdown、单页 HTML（侧边栏目录 + 印刷目录）、PDF（大纲 + 页内目录 + 印刷版）、EPUB |
| 质量门禁 | 结构完整性、源码坐标可核验、链接与锚点、图注与图簇、术语与索引、文风评分、交付校验（33 道门禁，见 `testplan.md`） |
| 判定与生成分离 | 脚本判定可枚举的部分，模型只做语义与措辞；模型产出必须再过一遍脚本 |
| 三个入口一套动作 | CLI、TUI、Web 控制台共用同一份动作与状态，结果一致 |
| 换书只换配置 | 书的身份、章节、包归属在 `data/book/book.toml`，分析口径与预算在 `data/config/`，代码不动 |

支持 Java / Python / Rust / Kotlin / Go 源码，可多语言混跑。

## 快速开始

```bash
books/scripts/bootstrap.sh          # 建 books/.venv 并装依赖；Windows 用 bootstrap.ps1

books/scripts/bookctl status        # 现在是什么状态
books/scripts/bookctl check         # 全部门禁（只读）
books/scripts/bookctl build         # 手稿 → 合并 Markdown + HTML
books/scripts/bookctl deliver       # 按需：PDF + EPUB + 校验
books/scripts/bookctl test          # 测试（--full 含 chromium/pandoc 档）
books/scripts/bookctl doctor        # 依赖与环境

books/scripts/launch.sh             # TUI：1 源码→手稿 · 3 手稿→文档 · 6 一次出全部产物
books/scripts/launch.sh web         # Web 控制台
```

`bookctl` 只是薄封装：解析解释器（`books/.venv` → `$PYTHON` → `python3`）后转发到
`app/cli.py`；`bookctl make <args>` 直接透传 `make.py`。不用启动脚本时：

```bash
python books/src/python/make.py check     # 全部门禁（只读）
python books/src/python/make.py build     # 手稿 → 合并 Markdown + HTML
python books/src/python/make.py deliver   # 交付：PDF + EPUB + 校验
```

源码更新后重生成手稿：`ingest/digest.py` → `ingest/outline.py` → `ingest/chapters.py`
（默认只刷新事实块，正文不动；`--force` 才整篇重写）。

## 文档总索引

目录结构、文件归属与清理规则只看 [`folder.md`](docs/managements/folder.md)；本节只登记"哪份文档负责什么"。

文档按三个轴分工：**要求**（要交付什么、内容必须有什么）、**判定**（谁判、判在几级、基线怎么记）、
**做法**（系统怎么实现、怎么写、怎么用）。同一件事只在一份文档里定义。

| 类别 | 文档 | 职责 |
| --- | --- | --- |
| 要求 | [requirements.md](docs/managements/requirements.md) | 本项目的需求与验收：FR / IR / NFR |
| 要求 | [content-standard.md](docs/managements/content-standard.md) | 内容标准（跨项目复用）：信息阶梯、事实要求、章节骨架、图示与练习 |
| 判定 | [testplan.md](docs/managements/testplan.md) | 判据与级别：每道门禁判什么、几级、怎么跑（验证的唯一权威） |
| 判定 | [content-quality-policy.md](docs/managements/content-quality-policy.md) | 内容质量方针：谁判、什么时候判、基线怎么记、代价多少 |
| 做法 | [technical.md](docs/managements/technical.md) | 技术设计：分层、依赖矩阵、配置合并、关键决策、扩展点 |
| 做法 | [folder.md](docs/managements/folder.md) | 目录与文件归属（结构只有这一处权威） |
| 做法 | [DESIGN.md](docs/managements/DESIGN.md) · [DESIGN-TUI.md](docs/managements/DESIGN-TUI.md) · [DESIGN-WEB.md](docs/managements/DESIGN-WEB.md) | 三个界面的呈现契约与键位 |
| 做法 | [how-to-use.md](docs/manuals/how-to-use.md) | 日常怎么干：改正文、加章节、交付一版、提交前的顺序 |
| 做法 | [how-to-new-book.md](docs/manuals/how-to-new-book.md) | 换项目：新建或翻译一本书，四份配置的职责 |
| 做法 | [how-to-config.md](docs/manuals/how-to-config.md) | 配置：改哪个文件、每个键是什么意思、改错会怎样 |
| 做法 | [how-to-write.md](docs/manuals/how-to-write.md) | 写作手法：句式、段落、图注、题目、引用、标点 |
| 做法 | [how-to-use-cli.md](docs/manuals/how-to-use-cli.md) · [how-to-use-tui.md](docs/manuals/how-to-use-tui.md) · [how-to-use-web.md](docs/manuals/how-to-use-web.md) | 三个入口怎么用、退出码、键位、JSON 接口 |
| 参考 | [scripts-and-reference.md](docs/manuals/scripts-and-reference.md) | 全部可执行入口与参数的唯一清单 |
| 参考 | [faq.md](docs/manuals/faq.md) | 排障：按症状查原因与处理动作 |
| 记录 | [plan.md](docs/managements/plan.md) | 在办事项：时机档、逐项验收 |
| 记录 | [review-findings.md](docs/managements/review-findings.md) | 问题台账：`rf-N` 编号与修复结论 |
| 记录 | [changelog.md](docs/managements/changelog.md) | 版本变更记录 |
| 记录 | [docs/plan/](docs/plan/) | 单项迭代的设计与实施计划（一个主题一个目录） |

`build` 与 `deliver` 结束时会把手稿与产物各存一份到 `books/data/archive/<书>/<日期>/`
（保留窗口取配置，缺省 45 天）。
