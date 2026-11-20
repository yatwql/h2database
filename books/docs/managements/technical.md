# 工具链架构约束

> 本文件是工具链的**架构约束**（可机检的部分由 `audit/check_architecture.py` 守卫）。
> 目录职责见 `../managements/folder.md`；用法见 `../manuals/how-to-use.md`；
> 内容标准见 `analysis-doc-standard.md`。

## 1. 分层、依赖与渠道纯净

### 1.1 层与职责

| 层 | 职责 | 可写 | 可导入 |
| --- | --- | --- | --- |
| `lib/` | 配置读取、文件读写原语、Markdown/HTML 工具。不决定写什么、写哪里 | 仅经调用方 | 无（只用标准库） |
| `core/` | 领域层：`actions`（动作执行）、`settings`（可改配置）、`menu`（菜单模型与运行回报）、`scaffold`（新书脚手架） | 经 `actions` 触发 | `lib` |
| `ingest/` | 源码 → 手稿：读源码树，写 `data/state` 与 `data/manuscript` | `data/state`、手稿 | `lib` |
| `manuscript/` | 手稿维护：术语、索引、封面、案例 | 手稿、`data/state` | `lib` |
| `audit/` | 质量门禁：只读，报告到 stdout（基线类脚本仅写 `data/baselines/`） | 基线除外不写 | `lib` |
| `render/` | 交付渲染：写 `dist/` | `dist/` | `lib` |
| `app/` | 渠道层：`cli` / `tui` / `web` / `keys`，只做渲染与按键分发 | 不写 | `lib`、`core`、`app` |

### 1.2 依赖矩阵（唯一权威）

| 从 \ 到 | lib | core | ingest | manuscript | audit | render | app |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lib | – | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| core | ✓ | – | ✗ | ✗ | ✗ | ✗ | ✗ |
| ingest | ✓ | ✗ | – | ✗ | ✗ | ✗ | ✗ |
| manuscript | ✓ | ✗ | ✗ | – | ✗ | ✗ | ✗ |
| audit | ✓ | ✗ | ✗ | ✗ | – | ✗ | ✗ |
| render | ✓ | ✗ | ✗ | ✗ | ✗ | – | ✗ |
| app | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |

同层之间不得互相 import；唯一的上行边是 `app → core`。矩阵写在
`audit/check_architecture.py` 的 `DEPENDENCY_MATRIX`，新增边必须先改矩阵。

### 1.3 渠道纯净

`app/` 只做四件事：渲染界面、读按键、调 `core.actions`、把 `core.menu` 的结论
打印出来。因此渠道内**禁止**：

- import `ingest/manuscript/audit/render`，也禁止直接驱动 `make.py`；
- 出现 `subprocess`、`write_text`、写模式 `open`（写文件属于 `core` / engine）；
- 持有业务规则：动作表、确认策略、菜单模型、默认光标、LLM 判定一律在
  `core/menu.py`；可改配置项与校验在 `core/settings.py`；动作执行在
  `core/actions.py`。

三个渠道共用 `core/actions.py`，所以 CLI / TUI / Web 的行为天然一致。

### 1.4 门禁只读与维护开关

`audit/` 的脚本默认只读；唯一允许写入的是基线类脚本（`--update-baseline`
等显式开关写 `data/baselines/`）。`make.py check` 永远不带这些开关。

### 1.5 每条规则由谁机检

| 规则 | 判据 | 机检 |
| --- | --- | --- |
| A1 依赖矩阵 | 只允许矩阵内的边 | `check_architecture.DEPENDENCY_MATRIX` |
| A2 渠道纯净 | 渠道无引擎 import、无 `subprocess`/写文件 | `check_architecture`（`CHANNEL_*`） |
| A3 领域不反向依赖 | `core` 不 import `app`（矩阵已覆盖，规则单独报错） | `check_architecture`（DIRECTION） |
| A4 门禁只读 | `audit/` 无写调用（基线除外） | `check_architecture`（WRITE） |
| A5 无硬编码路径 | 除 `lib` 外不得出现仓库路径字面量 | `check_architecture`（CONFIG） |
| A6 命名 | 不与标准库同名、无 `check_*`/`_audit_*` 冗余前缀、入口不加下划线 | `check_architecture`（NAMING） |
| A7 模块 docstring | 每个模块首行说明自身职责 | `check_architecture`（DOCSTRING） |
| A8 报告脚本 `--json` | `audit/` 中带 argparse 的报告须支持 `--json` | `check_architecture`（EXIT） |
| A9 配置/文档分离 | `style.json` 不含模板与展示文案 | `style_schema` |
| A10 LLM 使用边界 | 只有 `core`/`ingest` 可调用 LLM | `llm_policy` |
| A11 入口契约 | docstring + `main()`/守卫 + 退出码 + 库模块豁免 | `script_contract` |
| A12 文件规模 | 源码/测试/文档/附录行数上限 | `file_length` |

规则与文档条目一一对应：新增规则要同时改本节、`check_architecture.py` 与
`testplan.md`。

## 2. 配置与常量

- 路径、阈值、文案、词表、模板只来自 `_config`（`book.toml` + `base.json` +
  `style.json` + `language/*.json`）。
- 脚本内不得出现仓库路径字面量（`books/…`、`data/manuscript`）、阈值数字或书名文案。
- 已知问题只记入 `data/baselines/`，不得散落在代码或文档注释里。

## 3. 命名

- 目录定类别，文件名写对象：`audit/links.py` 而不是 `audit/audit_links.py`。
- 下划线前缀只表示"内部模块"（`lib/_config.py`）；CLI 入口不加下划线。
- 文件名不得与标准库模块同名（避免与标准库同名的模块遮蔽）。
- 同一目录内不得混用 `check_*` / `*_check` / `_audit_*` 三套风格。

## 4. 入口契约

- 每个入口脚本：模块 docstring + `main(argv)`（或在 `__main__` 下执行）。
- 退出码语义：`0` 通过、`1` 门禁失败、`2` 使用/配置错误。
- 报告类脚本必须支持 `--json`（供 `make.py` 与 CI 汇总）；`main()` 形态的脚本
  一律遵守，脚本形态（import 即执行，如 `style.py`、`smart.py`）不强制。
- `main(argv)` 必须接受可选 argv（`argv=None` 时用 `sys.argv[1:]`），便于内嵌调用。

## 5. 事实与内容

- 手稿中的源码引用必须可解析（`Class.java:行号`、`Class.method(`）。
- 每个源码包只有一个主责章节（`book.toml [chapters.packages]`）。
- 手稿不写过程性记录；版本历史只在 `changelog.md`。

## 6. 规模与复杂度

- 文件行数上限：源码 900、测试 1200、文档 1200、手稿附录 2000（含提醒线）。
- 单函数以"一屏可读"为目标；超长逻辑拆成具名步骤。

## 7. 测试

- fixture 书覆盖 stage 1 与 stage 2；`test_generic_source` 用第二份源码树守住通用性。
- 快慢分档：`make.py test` 默认快速档，`--full` 加 chromium/pandoc 档。

## 8. 门禁

- `make.py check` 是唯一入口；新增门禁必须同时登记 `testplan.md`，由
  `audit/gate_trace.py` 校验双向可追溯。
- 门禁只读；任何会改仓库的动作都属于 `manuscript/` 或 `render/`，不进 `check`。
- 例外只允许“显式维护开关”：`--update-baseline` / `--fix` 之类写 `data/baselines/`
  或手稿的动作，必须在文档写明且默认关闭，`check` 永远不带这些开关。

## 9. 日志

- 位置：`books/logs/books.log`，按天回滚（`books.log.YYYY-MM-DD`），默认保留 14 天。
- 级别：`BOOK_LOG_LEVEL` 环境变量 > `data/config/base.json [logging].level` > INFO；DEBUG 记录每步参数、耗时与计数。
- 出口：文件记录全部（INFO 起），控制台只输出 WARNING 及以上，避免刷屏。
- 实现：`lib/_log.py`（DailyRotatingHandler 幂等初始化），入口（`make.py`、`core/actions.py`、`ingest/*`）只调用 `_log.get_logger(...)`。

## 10. 环境与依赖

**被分析的源码是外部输入**：本仓库不包含、也不依赖某一份具体源码树。`base.json
[sources]` 指向它（`src_main` 可以是任意路径），`version` 固定本次分析的快照；
两者都可以在换书/换版本时改配置，不需要改代码。源码树缺失时，读取它的门禁
（源码坐标、章节生成）按"未配置"处理，其余门禁照常运行。


- 运行环境：`books/.venv`（由 `scripts/bootstrap.sh|ps1` 创建），启动脚本优先使用它。
- 依赖清单：`requirements.txt`（运行时可选）与 `requirements-dev.txt`（开发/CI）；
  文档与代码不再各自列依赖表。
- 核心链路（ingest/audit 结构门禁）只依赖标准库；PDF/EPUB 相关脚本在缺少
  `pypdf`/`playwright`/`pandoc` 时必须以清晰信息退出（码 2），不得抛裸 traceback。

## 11. LLM 使用边界（用在刀刃上）

- **允许**：散文生成与评审（`chapter-draft`、`chapter-polish`、`summary`、`review`）。
- **禁止**：任何事实与结构判断——章节结构、源码坐标、跨章引用、链接、重复度、
  文风度量、图注、索引、术语、表格，全部保持确定性。
- **执行**：`audit/llm_policy.py` 检查只有 `app/` 与 `ingest/` 可导入 `lib._llm`，
  `audit/` 门禁一律不得调用；策略清单在 `llm_settings.json [policy]`。
- **强度**：路由可按场景/书籍/章节指定 `thinking`（`off|low|medium|high`），
  缺省 `low`；强度随请求传为 `reasoning_effort`。

## 12. 三个版本

| 版本 | 来源 | 含义 | 谁改 |
| ------ | ------ | ------ | ------ |
| 工具版本 | `lib/_version.py`（或被 `[sources].tool_version` 覆盖） | 工具链自身 | 改工具的开发者，semver |
| 源码版本 | `[sources].version`，否则读源码清单（pom.xml / pyproject.toml / Cargo.toml） | 被分析的那份源码 | 上游升级时自动变化 |
| 文档版本 | `book.toml [book].version` | 这本书/这份手稿 | 内容迭代时 |

约束：

- 合并 Markdown 首行写 manifest：`<!-- versions: tool=… source=… doc=… -->`；
  该行与空白分隔不计入手稿行数（`structure.py` 已排除）。
- 管理文档头 `> 版本：vX` 必须等于文档版本。
- `audit/version_consistency.py` 校验三者可解析且一致；`make.py check` 必跑。
- `app/cli.py status` 与 TUI 顶部同时显示三者：`工具 / 源码 / 文档`。

## 13. 文件职责分类（权威定义）

工具链只通过 `lib/_config.py` 读配置，但"配置"与"文档"严格分开，且"文档"里
还要再分**结构 / 表述 / 名词**。下表是唯一权威定义，其他文档只做引用。

| 文件 | 回答的问题 | 内容 | 归类 | 读取方 | 改错的后果 |
| ------ | ----------- | ------ | ------ | -------- | ----------- |
| `data/tmpl/book.toml` | 这本书**是什么、怎么组织** | 书名/版本/产物名、`[project]` 展示文案、目录、章节清单与顺序、每条 H1 标题、H1 编号、覆盖归属、包→章节映射 | 文档·结构 | 规划期（outline）与全部阶段 | 章节/编号/索引/跨章引用错位，结构门禁直接拦 |
| `data/tmpl/templates.toml` | 这本书**怎么表述** | 版图/类型/入口/路径四段引言 + 深读要点，含 `{num}{pkgs}{top}{dep}{share}` 占位符 | 文档·表述 | `ingest/chapters.py` 渲染章节时 | 措辞变化，不影响判定；占位符写错会被 `style_schema.py` 拒绝 |
| `data/language/<code>.json` | 章节与练习的**名词与提示语** | 本章导读/小结/延伸思考/延展阅读的名字、`提示`/`回顾` 前缀、术语行与术语表链接 | 文档·名词 | 门禁匹配与生成器 | 门禁找不到段落，判为缺失 |
| `data/config/style.json` | **判定规则与阈值** | 图注词表与预设、图示标记、质量/文风阈值、禁用语、必备段落名、篇幅预算、生成数量上限、`style_rules`（术语一致性/排版） | 配置·规则 | 全部门禁 | 阈值失效或误报；`style_schema.py` 先校验结构 |
| `data/config/base.json` | **基础设施** | 源码树、语言与后缀、包前缀、状态/基线路径、日志、PDF/EPUB/ASCII/覆盖率预算 | 配置·基础 | 全部门禁与入口 | 找不到源码或产物路径 |
| `data/config/llm_*.json` | **模型路由与参数** | provider、模型、场景/书籍/章节路由、thinking 强度、密钥环境变量名 | 配置·外部服务 | `lib/_llm.py` 与 `app/` | 调用越界或被 `llm_policy.py` 拦下 |

记忆法：**结构看 `book.toml`，说法看 `templates.toml`，名词看语言包，判分看 `style.json`，
找源码看 `base.json`，找模型看 `llm_*.json`。**

边界由两道门禁强制：

- `audit/style_schema.py`：`style.json` 不得含 `generation.templates` 或 `project`；
  `templates.toml` 只允许已知键、占位符合法。
- `audit/check_architecture.py`：脚本不得硬编码仓库路径，一律经 `_config` 取。

## 14. 内容深度（可机检的四项）

| 检查 | 判据 | 例外 |
|------|------|------|
| 前向引用（PREREQ） | 本章提到由**后续章节**拥有的类型时，行内必须点名该章（`第N章`），否则视为缺少指引 | 类型名须以行内代码形式出现，避免误判普通单词 |
| 术语覆盖（GLOSSARY） | 正文出现次数 ≥ `glossary_min_uses` 的类型必须在术语表有条目 | `glossary_ignore` 列出通用名（File/Header/Undo…） |
| 摘录新鲜度（EXCERPT） | 代码摘录首行标注 `File.java:LINE` 时，其后若干行必须与源码对应行一致 | 源码中找不到文件则单独报 MISSING |
| 练习指向（EXERCISE） | 每道练习题要么点名本章关键类型，要么给出 `§X.Y` 锚点 | 无 |

判定配置在 `style.json [content_depth]`；门禁为 `audit/content_depth.py`，
接入 `make.py check`。

## 15. 产品标识

- 名称与版本只有一处定义：`lib/_version.py`（`APP_NAME` / `APP_TITLE` /
  `TOOL_VERSION`，当前 `bookwright 0.1`），通过 `_config.app_name()` 与
  `_config.app_title()` 暴露。
- 显示面必须一致：CLI `status`、TUI 顶部横幅、Web 页面标题、日志根 logger 与
  日志文件名（`logs/<name>.log`）都读同一来源。
- 与“三版本”的关系：`TOOL_VERSION` 是工具版本，源码版本与文档版本分别由
  `base.json`/源码清单与 `book.toml` 决定（见 §12）。
