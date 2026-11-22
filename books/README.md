# bookwright v0.1 — 源码分析成书工具

把一个源码仓库变成一本可交付的技术书：读源码 → 生成手稿 → 出 Markdown/HTML/PDF/EPUB，
全程由门禁把关（结构、事实、文风、交付）。

书名与章节映射都来自 `books/data/config/book/book.toml`；工具链与具体项目无关，换一份源码树与章节映射
即可生成另一本书。支持 Java / Python / Rust / Kotlin / Go 源码（可多语言混跑）。

## 能做什么

| 能力 | 说明 |
| ------ | ------ |
| 源码 → 手稿 | 抽取包/模块版图、核心类型、公开 API、依赖方向，按章节映射生成手稿 |
| 手稿 → 文档 | 合并 Markdown、HTML（侧边栏 TOC）、PDF（大纲/页内目录）、EPUB |
| 质量门禁 | 全部门禁（清单见 [`scripts-and-reference.md`](docs/manuals/scripts-and-reference.md) §8）：结构完整性、源码坐标可核验、链接锚点、图注、术语/索引、文风评分、交付校验 |
| 多入口 | CLI、TUI、Web 控制台共用同一套动作 |
| 可配置 | 数据组织 / 基础 / 风格三层加语言包（共四层，见 `docs/managements/technical.md` §3.1）+ LLM provider 路由 |

## 快速开始

```bash
books/scripts/bootstrap.sh     # 创建 books/.venv 并装依赖（Windows: bootstrap.ps1）

books/scripts/bookctl status        # 最短路径：cloak 掉 python 路径，直接跑动作
books/scripts/bookctl check         # 全部门禁
books/scripts/bookctl build         # 手稿 → 合并 Markdown + HTML
books/scripts/bookctl test          # 测试（--full 含 chromium/pandoc 档）
python books/src/python/test_report.py run   # 跑测试并留报告（books/test-reports/），last 解出失败用例
books/scripts/bookctl doctor        # 依赖与环境

books/scripts/launch.sh        # TUI 菜单
books/scripts/launch.sh cli    # CLI（与 bookctl 等价，可带子命令）
books/scripts/launch.sh web    # Web 控制台
```

`build` 与 `deliver` 结束时会把手稿与产物各存一份到 `books/data/archive/<书>/<日期>/`
（保留窗口取配置，缺省 45 天）。

`bookctl` 是薄封装：解析解释器（`books/.venv` → `$PYTHON` → `python3`）后转发到
`app/cli.py`；`bookctl make <args>` 直接透传 `make.py`。Windows 用 `bookctl.ps1`。

不用启动脚本时：

```bash
python books/src/python/make.py check   # 全部门禁（只读）
python books/src/python/make.py build   # 手稿 → 合并 Markdown + HTML
python books/src/python/make.py test    # 测试（快档；--full 含 chromium/pandoc 档）
python books/src/python/make.py deliver # 按需：PDF + EPUB + 校验
```

源码更新后重生成手稿：

```bash
python books/src/python/ingest/digest.py     # 源码 → data/state/source-inventory.json
python books/src/python/ingest/outline.py    # 章节大纲 + 覆盖矩阵
python books/src/python/ingest/chapters.py   # 渲染章节
```

## 目录

```text
books/
  data/      # 输入与状态：tmpl/（书与章节组织）、config/（基础与风格）、
             # language/（语言包）、manuscript/（手稿）、baselines/、state/
  src/
    python/  # lib/ 公共库、ingest/ 源码抽取（languages/ 分语言分析器）、
             # manuscript/ 手稿维护、audit/ 门禁、render/ 交付、app/ 入口
    test/    # 单元 + 集成 + 通用性回归
  scripts/   # launch.sh/.ps1（启动）、bootstrap.sh/.ps1（环境）
  dist/      # 产物（gitignored）
  logs/      # 运行日志（gitignored）
  docs/      # 用户文档 / 管理文档 / 规范 / 设计
```

## 文档索引

**用户文档（`docs/manuals/`）**

| 文档 | 内容 |
| ------ | ------ |
| [how-to-new-book.md](docs/manuals/how-to-new-book.md) | 新建/翻译一本书：四份文件的职责与脚手架 |
| [how-to-config.md](docs/manuals/how-to-config.md) | 如何配置：数据组织、基础、风格、语言包、LLM |
| [how-to-use-cli.md](docs/manuals/how-to-use-cli.md) | CLI 用法、动作、退出码 |
| [how-to-use-tui.md](docs/manuals/how-to-use-tui.md) | TUI 菜单与 `--once` 脚本化 |
| [how-to-use-web.md](docs/manuals/how-to-use-web.md) | Web 控制台与 JSON API |
| [faq.md](docs/manuals/faq.md) | 常见问题（环境、配置、门禁、交付、日志、LLM） |
| [how-to-use.md](docs/manuals/how-to-use.md) | 门禁与脚本速查（面向开发者） |
| [scripts-and-reference.md](docs/manuals/scripts-and-reference.md) | 全部脚本清单：命名约定、日常封装、各层入口、门禁→脚本对照 |

**规范与设计（`docs/managements/`）**

| 文档 | 内容 |
| ------ | ------ |
| [analysis-doc-standard.md](docs/managements/analysis-doc-standard.md) | 内容标准（跨项目复用） |
| [technical.md](docs/managements/technical.md) | 工具链架构约束；§13 是文件职责分类的权威定义（结构/表述/名词 vs 规则/基础/外部服务） |

**管理文档（`docs/managements/`）**

| 文档 | 内容 |
| ------ | ------ |
| [folder.md](docs/managements/folder.md) | 目录结构与文件归属 |
| [requirements.md](docs/managements/requirements.md) | 范围与交付物 |
| [plan.md](docs/managements/plan.md) | 工作流、维护策略、在建项、风险 |
| [testplan.md](docs/managements/testplan.md) | 质量门禁与验证命令（验证唯一权威） |
| [changelog.md](docs/managements/changelog.md) | 版本历史 |
| [style-guide.md](docs/managements/style-guide.md) | 写作与格式规范 |
| [DESIGN.md](docs/managements/DESIGN.md) | 设计契约总纲（三界面共有规则） |
| [DESIGN-TUI.md](docs/managements/DESIGN-TUI.md) | 终端交互契约 |
| [DESIGN-WEB.md](docs/managements/DESIGN-WEB.md) | 网页控制台契约 |
| [README.md](docs/managements/README.md) | 管理文档索引 |
